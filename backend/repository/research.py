"""MTA-SIM research history and the editable master objects beside it.

Two kinds of record share this snapshot key, and the difference between them
is the point of the module. Generated observations -- what a simulation run
delivered, spent, and earned -- are immutable: rewriting one would silently
change the evidence a published result was drawn from. Master and
configuration objects describe what a *future* run should do, so they are
editable, and they are stored separately in `dashboard_master_object` rather
than by mutating history in place.

The `mta_sim_*` tables are the one place this service reads a table
`dashboard/models.py` does not define. They belong to the external simulator
repository at `external/mta_sim_dataset/`, which owns their schema; copying
their definitions here would create a second declaration free to disagree with
the one that actually writes them. They are therefore probed with
`table_exists()` and read reflectively, and their absence falls back to the
committed reports rather than failing.

Data flow:
    MTA_SIM_DATA_DIR/&#42;.json  -.
                               +-> here -> /api/dashboard (simulationResearch)
    mta_sim_&#42; + master table -'
"""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping

from backend.config import simulator_data_directory, use_database
from backend.database import execute, sql, table_exists
from backend.repository.coercion import (
    dates,
    format_date,
    numeric,
    read_json,
    split_touchpoint,
)
from backend.repository.master_data import derive_master_data

#: The seven entity kinds a future-run draft may describe. The database CHECK
#: constraint below repeats this set, so a draft of an unknown kind is refused
#: by the schema as well as by the service.
MASTER_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "provider",
        "product",
        "campaign",
        "ad_group",
        "touchpoint",
        "product_economics",
        "generation_config",
    }
)

HISTORY_NUMERIC = (
    "budget_level",
    "configured_budget",
    "actual_spend",
    "total_units",
    "total_revenue",
    "expected_organic_units",
    "expected_organic_revenue",
    "incremental_units",
    "incremental_revenue",
    "contribution_profit",
)

DELIVERY_NUMERIC = (
    "impressions",
    "clicks",
    "cost",
    "reported_purchases",
    "reported_sales",
)

EMPTY_RESEARCH: dict[str, Any] = {
    "runs": [],
    "providers": [],
    "products": [],
    "campaigns": [],
    "adGroups": [],
    "touchpoints": [],
    "productEconomics": [],
    "campaignProductLinks": [],
    "history": [],
    "delivery": [],
    "generationConfigs": [],
    "touchpointObservations": [],
    "masterObjects": [],
}


def _availability_for(value: Any, explicit: Any) -> str:
    """An explicit availability marker, or one inferred from the value."""
    if explicit is not None:
        return explicit
    return "NOT_PROVIDED" if value is None else "AVAILABLE"


def _local_touchpoint_configurations(configuration: Mapping[str, Any]) -> list[dict]:
    """The touchpoint catalogue a simulator configuration file declares."""
    records = []
    for item in configuration.get("touchpoints") or []:
        fmt = item.get("format")
        if fmt is None:
            fmt = (
                item.get("inventory_type")
                if item.get("ad_product") == "AMAZON_DSP"
                else item.get("ad_type")
            )
        creative = item.get("creative") or item.get("creative_type")
        availability = item.get("field_availability") or {}
        interactions = []
        if item.get("impression_enabled") is not False:
            interactions.append("IMPRESSION")
        if item.get("click_enabled") is not False:
            interactions.append("CLICK")
        base = ":".join(
            [
                str(item.get("ad_product")),
                str(fmt),
                item.get("placement") or "UNSPECIFIED",
                creative or "UNSPECIFIED",
            ]
        )
        billing = item.get("billing_type") or item.get("cost_type")
        if billing is None:
            billing = "CPC" if item.get("cost_per_click") is not None else "CPM"
        records.append(
            {
                "identifier": item.get("identifier"),
                "provider": item.get("provider") or "AMAZON_ADS",
                "ad_product": item.get("ad_product"),
                "format": fmt,
                "placement": item.get("placement"),
                "placement_availability": _availability_for(
                    item.get("placement"), availability.get("placement")
                ),
                "creative": creative,
                "creative_availability": _availability_for(
                    creative, availability.get("creative")
                ),
                "interaction_type_availability": availability.get("interaction_type")
                or "AVAILABLE",
                "supported_interactions": interactions,
                "impression_enabled": "IMPRESSION" in interactions,
                "click_enabled": "CLICK" in interactions,
                "billing_type": billing,
                "cost_per_click": item.get("cost_per_click"),
                "cost_per_thousand_impressions": item.get(
                    "cost_per_thousand_impressions"
                ),
                "base_impressions": item.get("base_impressions"),
                "click_through_rate": item.get("click_through_rate"),
                "platform_conversion_rate": item.get("platform_conversion_rate"),
                "conversion_log_odds_effect": item.get("conversion_log_odds_effect"),
                "compatibility_keys": [
                    f"{base}:{interaction}" for interaction in interactions
                ],
                "active": True,
            }
        )
    return records


def _flatten_observation(item: Mapping[str, Any]) -> dict:
    """Flatten a nested observation's reporting scope and touchpoint."""
    scope = item.get("reporting_scope") or {}
    touchpoint = item.get("touchpoint") or {}
    field_availability = touchpoint.get("field_availability") or {}
    flattened = {**item, **scope}
    flattened["provider"] = touchpoint.get("provider") or item.get("provider")
    flattened["touchpoint"] = (
        ":".join(
            [
                str(touchpoint.get("ad_product")),
                str(touchpoint.get("format")),
                touchpoint.get("placement") or "UNSPECIFIED",
                touchpoint.get("creative") or "UNSPECIFIED",
                str(touchpoint.get("interaction_type")),
            ]
        )
        if touchpoint.get("ad_product")
        else item.get("touchpoint_key")
    )
    flattened["interaction_type"] = touchpoint.get("interaction_type")
    flattened["placement_availability"] = field_availability.get(
        "placement"
    ) or item.get("placement_availability")
    flattened["creative_availability"] = field_availability.get("creative") or item.get(
        "creative_availability"
    )
    flattened["interaction_type_availability"] = field_availability.get(
        "interaction_type"
    ) or item.get("interaction_type_availability")
    flattened["report_date"] = scope.get("report_start_date") or item.get("report_date")
    return flattened


def _derived_master_data() -> dict:
    """The master catalogue implied by the committed platform reports.

    Read whenever no research sidecar is configured, which is every default
    deployment. The reports are tracked, so the entity sections describe the
    account in every deployment rather than standing empty and inviting the
    reader to believe the dashboard is broken.
    """
    from backend.repository.history import ads_daily, entity_bridge
    from backend.repository.strategy import strategy_request

    return derive_master_data(ads_daily(), entity_bridge(), strategy_request())


def _local_simulation_research(*, include_observations: bool = True) -> dict:
    """Research history read from a configured MTA-SIM run, or from the reports."""
    directory = simulator_data_directory()
    if directory is None:
        return {**EMPTY_RESEARCH, **_derived_master_data()}

    research = read_json(directory / "simulation_research.json")
    configuration = read_json(directory / "effective_configuration.json")
    runs = research.get("simulation_runs") or []
    run = runs[0] if runs else {}
    budget = (research.get("budget_observations") or []) if include_observations else []
    evaluations = (
        (research.get("evaluation_outcome_observations") or [])
        if include_observations
        else []
    )

    outcomes = {}
    for item in evaluations:
        scope = item.get("reporting_scope") or {}
        key = "|".join(
            str(part)
            for part in (
                item.get("campaign_id"),
                scope.get("marketplace"),
                scope.get("report_start_date"),
                item.get("budget_level"),
            )
        )
        outcomes[key] = _flatten_observation(item)

    history = []
    for item in budget:
        row = _flatten_observation(item)
        key = "|".join(
            str(part)
            for part in (
                item.get("campaign_id"),
                row.get("marketplace"),
                row.get("report_date"),
                item.get("budget_level"),
            )
        )
        history.append(
            {
                **row,
                **outcomes.get(key, {}),
                "configured_budget": item.get("configured_budget"),
                "actual_spend": item.get("actual_spend"),
                "budget_level": item.get("budget_level"),
            }
        )

    return {
        "runs": runs,
        "providers": [
            {**item, "active": True} for item in (run.get("providers") or [])
        ],
        "products": run.get("products") or [],
        "campaigns": run.get("campaigns") or [],
        "adGroups": run.get("ad_groups") or [],
        "touchpoints": _local_touchpoint_configurations(configuration),
        "productEconomics": run.get("product_economics") or [],
        "campaignProductLinks": run.get("campaign_product_links") or [],
        "history": history,
        "delivery": (
            [
                _flatten_observation(item)
                for item in (research.get("delivery_observations") or [])
            ]
            if include_observations
            else []
        ),
        "generationConfigs": [
            {
                "run_id": item.get("run_id"),
                "seed": item.get("seed"),
                "configuration_sha256": item.get("configuration_sha256"),
                "effective_configuration": item.get("effective_configuration"),
            }
            for item in runs
        ],
        "touchpointObservations": (
            research.get("touchpoint_observations") or []
            if include_observations
            else []
        ),
        "masterObjects": [],
    }


def _database_simulation_research(*, include_observations: bool = True) -> dict:
    """Research history read from the external simulator's own tables."""
    if not table_exists("mta_simulation_run"):
        return {
            **_local_simulation_research(include_observations=include_observations),
            "masterObjects": master_objects(),
        }

    runs = sql(
        "select run_id, seed, configuration_sha256, effective_configuration "
        "from mta_simulation_run order by run_id"
    )
    providers = sql(
        "select *, true as active from mta_sim_provider order by run_id, provider"
    )
    products = sql("select * from mta_sim_product order by run_id, product_id")
    campaigns = sql("select * from mta_sim_campaign order by run_id, campaign_id")
    ad_groups = sql(
        "select * from mta_sim_ad_group order by run_id, campaign_id, ad_group_id"
    )
    # The interaction suffixes are escaped as `\:IMPRESSION` and `\:CLICK`
    # because `sql()` wraps the statement in SQLAlchemy's `text()`, which reads
    # a bare `:NAME` as a bind parameter even inside a quoted SQL literal.
    # Unescaped, every database-mode snapshot fails with "A value is required
    # for bind parameter 'IMPRESSION'" before any row is read. The backslash is
    # consumed by the parser, so PostgreSQL still receives `:IMPRESSION`.
    touchpoints = sql(
        r"""
        select *, array_remove(array[
          case when impression_enabled then concat(ad_product, ':', format, ':',
            coalesce(placement, 'UNSPECIFIED'), ':',
            coalesce(creative, 'UNSPECIFIED'), '\:IMPRESSION') end,
          case when click_enabled then concat(ad_product, ':', format, ':',
            coalesce(placement, 'UNSPECIFIED'), ':',
            coalesce(creative, 'UNSPECIFIED'), '\:CLICK') end
        ], null) as compatibility_keys
        from mta_sim_touchpoint order by run_id, identifier
        """
    )
    product_economics = sql(
        "select * from mta_sim_product_economics order by run_id, product_id, currency"
    )
    campaign_product_links = sql(
        "select * from mta_sim_campaign_product_link "
        "order by run_id, campaign_id, product_id"
    )
    history = []
    delivery = []
    if include_observations:
        history = sql(
            """
            select b.run_id, b.campaign_id, b.marketplace, b.advertiser_id,
                   b.currency, b.report_date, b.budget_level, b.configured_budget,
                   b.actual_spend, o.product_id, o.total_units, o.total_revenue,
                   o.expected_organic_units, o.expected_organic_revenue,
                   o.incremental_units, o.incremental_revenue, o.contribution_profit
              from mta_sim_budget_observation b
              left join mta_sim_outcome_observation o
                on o.run_id = b.run_id and o.campaign_id = b.campaign_id
               and o.marketplace = b.marketplace and o.report_date = b.report_date
               and o.budget_level = b.budget_level and o.evaluation_only = true
             order by b.run_id, b.report_date, b.campaign_id, b.budget_level
            """
        )
        delivery = sql(
            "select * from mta_sim_delivery_observation "
            "order by run_id, report_date, campaign_id, id"
        )

    dates(history, ["report_date"])
    dates(delivery, ["report_date"])
    for row in delivery:
        row["touchpoint"] = row.get("touchpoint_key")
    split_touchpoint(delivery)
    numeric(history, HISTORY_NUMERIC)
    numeric(delivery, DELIVERY_NUMERIC)

    return {
        "runs": runs,
        "providers": providers,
        "products": products,
        "campaigns": campaigns,
        "adGroups": ad_groups,
        "touchpoints": touchpoints,
        "productEconomics": product_economics,
        "campaignProductLinks": campaign_product_links,
        "history": history,
        "delivery": delivery,
        "generationConfigs": runs,
        "touchpointObservations": [],
        "masterObjects": master_objects(),
    }


def simulation_research() -> dict:
    """Immutable MTA-SIM history and editable master/configuration entities."""
    return (
        _database_simulation_research()
        if use_database()
        else _local_simulation_research()
    )


def simulation_research_core() -> dict:
    """Research metadata and catalogues without observation-heavy arrays."""
    if use_database():
        return _database_simulation_research(include_observations=False)
    return _local_simulation_research(include_observations=False)


def history_window_bounds() -> dict:
    """The first and last observed `report_date`, or nulls when there are none.

    Read separately from the observations so a window-limited request can still
    tell the reader what lies outside it. This is two aggregates over an indexed
    column rather than a scan of the rows themselves, so it stays cheap enough
    to answer beside every history load.
    """
    if not use_database() or not table_exists("mta_simulation_run"):
        research = _local_simulation_research()
        observed = sorted(
            {
                row.get("report_date")
                for row in (research.get("history") or [])
                if row.get("report_date")
            }
        )
        return {
            "earliest": observed[0] if observed else None,
            "latest": observed[-1] if observed else None,
        }
    rows = sql(
        "select min(report_date) as earliest, max(report_date) as latest "
        "from mta_sim_budget_observation"
    )
    first = rows[0] if rows else {}
    return {
        "earliest": format_date(first.get("earliest")),
        "latest": format_date(first.get("latest")),
    }


def _within_window(rows: list[dict], window: Mapping[str, Any] | None) -> list[dict]:
    """Keep the rows whose `report_date` falls inside an inclusive window.

    Applied to locally read history, which arrives whole because it is one
    file. The database path pushes the same bounds into SQL instead, so this
    filter never runs against a full table read.
    """
    if not window:
        return rows
    start = window.get("start")
    end = window.get("end")
    if not start and not end:
        return rows
    kept = []
    for row in rows:
        value = row.get("report_date")
        if not value:
            continue
        if start and value < start:
            continue
        if end and value > end:
            continue
        kept.append(row)
    return kept


def simulation_research_history(
    progress: Callable[[int, str], None] | None = None,
    window: Mapping[str, Any] | None = None,
) -> dict:
    """Load only observation arrays, reporting real database query phases.

    `window` optionally bounds `report_date` inclusively as `{start, end}`.
    Both bounds are already validated `YYYY-MM-DD` strings by the time they
    arrive, and they are bound as SQL parameters rather than interpolated.
    """
    report = progress or (lambda _percent, _phase: None)
    bounds = {"start": (window or {}).get("start"), "end": (window or {}).get("end")}
    if not use_database() or not table_exists("mta_simulation_run"):
        report(48, "Reading local Campaign history")
        research = _local_simulation_research()
        report(84, "Normalizing Campaign history")
        return {
            "history": _within_window(research.get("history") or [], bounds),
            "delivery": _within_window(research.get("delivery") or [], bounds),
            "touchpointObservations": research.get("touchpointObservations") or [],
        }

    # Built by appending whole predicates rather than by formatting values in:
    # the bounds still travel as bound parameters, and a bound that was not
    # requested contributes no clause at all.
    clauses = ""
    if bounds["start"]:
        clauses += " and b.report_date >= :start"
    if bounds["end"]:
        clauses += " and b.report_date <= :end"
    parameters = {key: value for key, value in bounds.items() if value}

    report(42, "Querying budget and outcome observations")
    history = sql(
        f"""
        select b.run_id, b.campaign_id, b.marketplace, b.advertiser_id,
               b.currency, b.report_date, b.budget_level, b.configured_budget,
               b.actual_spend, o.product_id, o.total_units, o.total_revenue,
               o.expected_organic_units, o.expected_organic_revenue,
               o.incremental_units, o.incremental_revenue, o.contribution_profit
          from mta_sim_budget_observation b
          left join mta_sim_outcome_observation o
            on o.run_id = b.run_id and o.campaign_id = b.campaign_id
           and o.marketplace = b.marketplace and o.report_date = b.report_date
           and o.budget_level = b.budget_level and o.evaluation_only = true
         where true{clauses}
         order by b.run_id, b.report_date, b.campaign_id, b.budget_level
        """,
        parameters,
    )
    report(66, "Querying delivery observations")
    delivery = sql(
        f"select * from mta_sim_delivery_observation b where true{clauses} "
        "order by run_id, report_date, campaign_id, id",
        parameters,
    )
    report(84, "Normalizing Campaign history")
    dates(history, ["report_date"])
    dates(delivery, ["report_date"])
    for row in delivery:
        row["touchpoint"] = row.get("touchpoint_key")
    split_touchpoint(delivery)
    numeric(history, HISTORY_NUMERIC)
    numeric(delivery, DELIVERY_NUMERIC)
    return {
        "history": history,
        "delivery": delivery,
        "touchpointObservations": [],
    }


# ---------------------------------------------------------------------------
# Editable future-run master objects
# ---------------------------------------------------------------------------


def ensure_master_object_table() -> None:
    """Create the drafts table when it is missing.

    Created on demand rather than by the import command because a draft is
    dashboard state rather than pipeline output: a database populated by
    `script/import_to_database.py` has no reason to carry the table until
    someone edits something, and a deployment that never edits never gets it.
    """
    execute(
        """
        create table if not exists dashboard_master_object (
            entity_type text not null,
            entity_id text not null,
            payload jsonb not null,
            active boolean not null default true,
            updated_at timestamptz not null default now(),
            primary key (entity_type, entity_id),
            check (entity_type in ('provider', 'product', 'campaign', 'ad_group',
              'touchpoint', 'product_economics', 'generation_config'))
        )
        """
    )


def master_objects() -> list[dict]:
    """Every stored future-run draft, or an empty list before any exists."""
    if not use_database() or not table_exists("dashboard_master_object"):
        return []
    return sql(
        "select entity_type, entity_id, payload, active, updated_at "
        "from dashboard_master_object order by entity_type, entity_id"
    )


class MasterObjectError(ValueError):
    """A draft that cannot be stored, with the reason a reader can act on."""


def _validate(entity_type: str, entity_id: str, payload: Any) -> None:
    """Reject a draft the schema would refuse, naming what is wrong."""
    if entity_type not in MASTER_ENTITY_TYPES:
        raise MasterObjectError(f"unsupported master entity type: {entity_type}")
    if not str(entity_id or "").strip():
        raise MasterObjectError("entity_id is required")
    if not isinstance(payload, dict):
        raise MasterObjectError("payload must be a JSON object")


def save_master_object(entity_type: str, entity_id: str, payload: Any) -> dict:
    """Store a future-run draft without mutating generated history."""
    if not use_database():
        raise MasterObjectError("Master editing requires DATABASE=true")
    _validate(entity_type, entity_id, payload)
    ensure_master_object_table()
    rows = execute(
        """
        insert into dashboard_master_object
            (entity_type, entity_id, payload, active, updated_at)
        values (:entity_type, :entity_id, cast(:payload as jsonb), true, now())
        on conflict (entity_type, entity_id) do update
            set payload = excluded.payload, active = true, updated_at = now()
        returning entity_type, entity_id, payload, active, updated_at
        """,
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": json.dumps(payload),
        },
    )
    return rows[0] if rows else {}


def archive_master_object(entity_type: str, entity_id: str) -> dict | None:
    """Archive a future-run draft; generated observations remain immutable."""
    if not use_database():
        raise MasterObjectError("Master editing requires DATABASE=true")
    _validate(entity_type, entity_id, {})
    ensure_master_object_table()
    rows = execute(
        """
        update dashboard_master_object set active = false, updated_at = now()
         where entity_type = :entity_type and entity_id = :entity_id
        returning entity_type, entity_id, payload, active, updated_at
        """,
        {"entity_type": entity_type, "entity_id": entity_id},
    )
    return rows[0] if rows else None
