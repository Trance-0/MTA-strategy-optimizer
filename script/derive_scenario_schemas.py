"""Derive the dashboard's tables from a simulator-populated schema.

`script/import_to_database.py` loads the committed fixture: one demo
advertiser, one marketplace, one quarter. A schema written by the external
simulator holds something else entirely -- its own advertisers, its own
marketplaces, and a full year of daily observations -- and the two must never
be mixed. Running the import command against a simulator schema would staple
`adv_demo_001` entities onto observations belonging to another account and
produce a dashboard describing a campaign group that does not exist.

So this command derives rather than imports. It reads the simulator's own
tables and computes the dashboard model from them, which is the calculation
the file pipeline performs with the database standing in for the CSVs at both
ends:

    mta_sim_* + amc_path_report + amazon_ads_daily_touchpoint_performance
      -> one scenario selected, one window aggregated
      -> run_markov_attribution / run_shapley_attribution
      -> compare_attribution_models
      -> the tables the dashboard reads

The attribution models and their comparison are imported from the modules that
own them rather than reimplemented, so a derived schema and a published
artifact are produced by the same code and cannot drift into disagreeing.

One scenario becomes one schema. The simulator writes three marketplaces into
a single schema, while the dashboard model holds one advertiser, one
marketplace, and one report window, and reads `attribution_run` as a single
row. Splitting on the way out keeps that contract intact and makes the schema
dropdown the scenario picker, rather than teaching every loader to filter.

Usage:
    uv run --extra dashboard python script/derive_scenario_schemas.py --list
    uv run --extra dashboard python script/derive_scenario_schemas.py \
        --source mta --marketplace US --schema mta_us --replace
    uv run --extra dashboard python script/derive_scenario_schemas.py \
        --source mta --all --replace
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import replace as dataclass_replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from dashboard import config  # noqa: E402
from dashboard.models import (  # noqa: E402
    AdGroup,
    AdsDailyPerformance,
    AttributionResult,
    AttributionRun,
    Base,
    ModelComparisonSummary,
    ModelComparisonTouchpoint,
    PathReport,
    RecommendedAttribution,
    TouchpointEntityBridge,
)
from modules.mta_attribution.src.attribution_contract import (  # noqa: E402
    aggregate_spend_by_touchpoint,
    result_rows,
)
from modules.mta_attribution.src.attribution_model_comparison import (  # noqa: E402
    compare_attribution_models,
)
from modules.mta_attribution.src.markov_attribution_model import (  # noqa: E402
    run_markov_attribution,
)
from modules.mta_attribution.src.shapley_attribution_model import (  # noqa: E402
    run_shapley_attribution,
)
from modules.mta_strategy_recommendation.src.budget_recommender import (  # noqa: E402
    SEARCH_AD_PRODUCTS,
    SUPPORTED_AD_PRODUCTS,
    BudgetRecommendationError,
    generate_budget_recommendation,
)
from script.import_to_database import (  # noqa: E402
    Importer,
    as_bool,
    as_date,
    as_float,
    as_int,
    ensure_schema,
)

#: The simulator tables a source schema must hold before anything can be
#: derived from it. The `mta_sim_*` tables carry the entity model; the two
#: stable report tables carry the observations the attribution models read.
SOURCE_TABLES: tuple[str, ...] = (
    "mta_simulation_run",
    "mta_sim_campaign",
    "mta_sim_ad_group",
    "mta_sim_touchpoint",
    "mta_sim_product",
    "mta_sim_campaign_product_link",
    "mta_sim_delivery_observation",
    "mta_sim_outcome_observation",
    "amc_path_report",
    "amazon_ads_daily_touchpoint_performance",
)

#: The outcome weights a derived strategy request is scored with, taken from
#: the committed request rather than invented here so a derived scenario and
#: the fixture are weighted identically.
OUTCOME_WEIGHTS: dict[str, float] = {
    "converted_users": 0.4,
    "purchase_count": 0.3,
    "revenue": 0.3,
}

#: Per-ad-product capacity rules, likewise carried from the committed request.
#: These are pipeline configuration rather than observed data -- the simulator
#: models delivery, not the targeting inventory a new Ad Group would be built
#: from -- so they are stated here rather than read from the source.
CAPACITY_RULES: dict[str, dict[str, Any]] = {
    "SPONSORED_PRODUCTS": {
        "max_keyword_units_per_ad_group": 50,
        "max_skus_per_ad_group": 20,
        "max_legal_pairs_per_ad_group": 100,
        "min_ad_groups": 1,
        "max_ad_groups": 10,
        "minimum_daily_budget_per_ad_group": 25.0,
    },
    "SPONSORED_BRANDS": {
        "max_keyword_units_per_ad_group": 50,
        "max_skus_per_ad_group": 20,
        "max_legal_pairs_per_ad_group": 100,
        "min_ad_groups": 1,
        "max_ad_groups": 10,
        "minimum_daily_budget_per_ad_group": 25.0,
    },
    "SPONSORED_DISPLAY": {
        "max_skus_per_ad_group": 20,
        "max_targets_per_ad_group": 50,
        "max_audiences_per_ad_group": 50,
        "min_ad_groups": 1,
        "max_ad_groups": 10,
        "minimum_daily_budget_per_ad_group": 25.0,
    },
    "AMAZON_DSP": {
        "max_skus_per_ad_group": 20,
        "max_targets_per_ad_group": 50,
        "max_audiences_per_ad_group": 50,
        "min_ad_groups": 1,
        "max_ad_groups": 10,
        "minimum_daily_budget_per_ad_group": 25.0,
    },
}

#: The simulator's own tables, copied into each derived schema so the Research
#: view has its history there. `backend/repository/research.py` reads these
#: reflectively through `search_path`, so a derived schema without them falls
#: back to the catalogue implied by the reports and shows no runs at all.
#: Every one carries `run_id`, and a scenario is exactly one run, so the copy
#: is an exact slice rather than a filtered approximation.
RESEARCH_TABLES: tuple[str, ...] = (
    "mta_simulation_run",
    "mta_sim_provider",
    "mta_sim_product",
    "mta_sim_campaign",
    "mta_sim_ad_group",
    "mta_sim_touchpoint",
    "mta_sim_product_economics",
    "mta_sim_campaign_product_link",
    "mta_sim_budget_observation",
    "mta_sim_outcome_observation",
    "mta_sim_delivery_observation",
)

#: The v4 candidate-count fields, in the exact set `recommend_ad_group_count()`
#: requires. Named here because a count the simulator does not model is written
#: as zero rather than omitted: an absent field is a schema error, while a zero
#: states that the scenario establishes no such inventory.
CANDIDATE_FIELDS: tuple[str, ...] = (
    "eligible_keyword_unit_count",
    "eligible_sku_count",
    "eligible_legal_pair_count",
    "eligible_target_count",
    "eligible_audience_count",
)


class DerivationError(RuntimeError):
    """A source schema that cannot be derived from, naming what is wrong."""


# ---------------------------------------------------------------------------
# Reading the source schema
# ---------------------------------------------------------------------------


def _quote(identifier: str) -> str:
    """Quote a schema name that `valid_schema_name()` has already accepted."""
    return '"' + identifier.replace('"', '""') + '"'


def read_source(connection, schema: str, statement: str, **parameters) -> list[dict]:
    """Run one read against the source schema, naming it explicitly.

    The schema is interpolated as a quoted identifier rather than reached
    through `search_path`, because this command writes into a different schema
    than it reads from. Leaving the source ambiguous is what would let a
    derivation quietly read its own half-built output.
    """
    resolved = statement.replace("{s}", _quote(schema))
    return [dict(row) for row in connection.execute(text(resolved), parameters).mappings()]


def missing_source_tables(connection, schema: str) -> list[str]:
    """Which of the required simulator tables the source schema lacks."""
    present = {
        row["table_name"]
        for row in read_source(
            connection,
            schema,
            "select table_name from information_schema.tables "
            "where table_schema = :target",
            target=schema,
        )
    }
    return [table for table in SOURCE_TABLES if table not in present]


def scenarios(connection, schema: str) -> list[dict]:
    """Every scenario the source schema holds, one per marketplace.

    Keyed on the marketplace rather than on `run_id`, because the two stable
    report tables carry no run identifier: they join to a scenario by scope,
    which is the only key both sides share.
    """
    return read_source(
        connection,
        schema,
        """
        select marketplace,
               min(advertiser_id) as advertiser_id,
               min(report_start_date) as report_start_date,
               max(report_end_date) as report_end_date,
               count(*) as path_rows,
               count(distinct path) as distinct_paths
          from {s}.amc_path_report
         group by marketplace
         order by marketplace
        """,
    )


def aggregate_paths(
    connection,
    schema: str,
    marketplace: str,
    advertiser: str,
    window: tuple[str, str],
) -> list[dict]:
    """One path report row per distinct path, summed over the whole window.

    The simulator writes a window per day. The dashboard shows a single
    attribution run, and `compare_attribution_models()` refuses a report
    carrying more than one window. Summing the daily rows per path is what
    turns 365 windows into the one the models read, and it uses every row
    rather than discarding all but a chosen day.

    Every row is stamped with the scenario's own window rather than with the
    first and last dates that path happened to appear on. Per-path extremes
    would produce as many windows as there are paths and fail the same check
    this aggregation exists to satisfy.

    The row-level invariants survive the sum: `converted_users <= users` and
    `purchase_count >= converted_users` hold termwise, so they hold for the
    totals. `users` counts journeys within a daily window, so its sum is
    journeys over the year rather than distinct people -- the same quantity the
    file pipeline aggregates, and the models use it only as a path weight.
    """
    rows = read_source(
        connection,
        schema,
        """
        select path,
               sum(users) as users,
               sum(converted_users) as converted_users,
               sum(purchase_count) as purchase_count,
               sum(revenue) as revenue
          from {s}.amc_path_report
         where marketplace = :marketplace and advertiser_id = :advertiser
         group by path
         order by path
        """,
        marketplace=marketplace,
        advertiser=advertiser,
    )
    start, end = window
    return [
        {
            "path": row["path"],
            "report_start_date": start,
            "report_end_date": end,
            "marketplace": marketplace,
            "advertiser_id": advertiser,
            "users": as_int(str(row["users"])),
            "converted_users": as_int(str(row["converted_users"])),
            "purchase_count": as_int(str(row["purchase_count"])),
            "revenue": round(float(row["revenue"] or 0.0), 2),
        }
        for row in rows
    ]


def ads_rows(connection, schema: str, marketplace: str, advertiser: str) -> list[dict]:
    """Daily platform performance for one scenario, shaped like the Ads report.

    Two columns the report has and the simulator's table does not are restored
    here. `interaction_type` is the fifth segment of `normalizedTouchpoint`, so
    it is read back off the key the simulator already wrote rather than
    guessed; `touchpoint_key_from_ads_row()` then rebuilds the key from the
    other columns and verifies it against that stored value, which is what
    catches a key and its columns disagreeing.

    `cost_type` follows from the interaction by the project's own rule: a click
    is billed CPC and an impression CPM. That is the pairing
    `aggregate_spend_by_touchpoint()` enforces, and the committed fixture
    contains no other combination. It describes the row rather than the
    touchpoint: a CPM-billed touchpoint's CLICK rows carry no cost in this
    data, so labelling them CPC moves no money and leaves each touchpoint's
    spend counted exactly once.
    """
    rows = read_source(
        connection,
        schema,
        """
        select "reportDate", marketplace, "accountId", "adProduct", "adType",
               "creativeType", "inventoryType", placement, "normalizedTouchpoint",
               "currencyCode", impressions, clicks, cost, purchases, sales
          from {s}.amazon_ads_daily_touchpoint_performance
         where marketplace = :marketplace and "accountId" = :advertiser
         order by "reportDate", "normalizedTouchpoint"
        """,
        marketplace=marketplace,
        advertiser=advertiser,
    )
    for row in rows:
        key = str(row.get("normalizedTouchpoint") or "")
        interaction = key.rsplit(":", 1)[-1] if ":" in key else ""
        row["interaction_type"] = interaction
        row["cost_type"] = "CPC" if interaction == "CLICK" else "CPM"
    return rows


def simulator_entities(connection, schema: str, marketplace: str) -> dict[str, Any]:
    """The run, campaigns, ad groups, products, and delivery of one scenario.

    The run is located through the delivery observations, which record the
    marketplace they were produced for. Joining on observed data rather than on
    the run's declared configuration ties the entity model and the observations
    together by the same evidence.
    """
    runs = read_source(
        connection,
        schema,
        "select distinct run_id from {s}.mta_sim_delivery_observation "
        "where marketplace = :marketplace order by run_id",
        marketplace=marketplace,
    )
    if not runs:
        raise DerivationError(
            f"{marketplace}: no simulation run delivered into this marketplace, "
            "so its entity model cannot be joined to its observations"
        )
    if len(runs) > 1:
        names = ", ".join(str(row["run_id"]) for row in runs)
        raise DerivationError(
            f"{marketplace}: {len(runs)} simulation runs share this marketplace "
            f"({names}); the dashboard model holds one run, so the source must "
            "be split before deriving"
        )
    run_id = runs[0]["run_id"]

    return {
        "run_id": run_id,
        "campaigns": read_source(
            connection,
            schema,
            "select campaign_id, campaign_name, provider, ad_product, status, "
            "baseline_daily_budget from {s}.mta_sim_campaign "
            "where run_id = :run order by campaign_id",
            run=run_id,
        ),
        "ad_groups": read_source(
            connection,
            schema,
            "select ad_group_id, campaign_id from {s}.mta_sim_ad_group "
            "where run_id = :run order by campaign_id, ad_group_id",
            run=run_id,
        ),
        "links": read_source(
            connection,
            schema,
            """
            select link.campaign_id, link.product_id, product.sku_id,
                   product.provider_ad_identifiers
              from {s}.mta_sim_campaign_product_link as link
              join {s}.mta_sim_product as product
                on product.run_id = link.run_id
               and product.product_id = link.product_id
             where link.run_id = :run and link.link_status = 'ACTIVE'
             order by link.campaign_id, link.product_id
            """,
            run=run_id,
        ),
        "delivery": read_source(
            connection,
            schema,
            """
            select campaign_id, touchpoint_key,
                   sum(impressions) as impressions, sum(clicks) as clicks,
                   sum(cost) as cost, sum(reported_purchases) as reported_purchases,
                   sum(reported_sales) as reported_sales
              from {s}.mta_sim_delivery_observation
             where run_id = :run and marketplace = :marketplace
             group by campaign_id, touchpoint_key
             order by campaign_id, touchpoint_key
            """,
            run=run_id,
            marketplace=marketplace,
        ),
        "outcomes": read_source(
            connection,
            schema,
            """
            select campaign_id, touchpoint_key, product_id,
                   sum(total_units) as total_units,
                   sum(total_revenue) as total_revenue
              from {s}.mta_sim_outcome_observation
             where run_id = :run and marketplace = :marketplace
               and product_id is not null
             group by campaign_id, touchpoint_key, product_id
             order by campaign_id, touchpoint_key, product_id
            """,
            run=run_id,
            marketplace=marketplace,
        ),
    }


def copy_research_tables(connection, source: str, target: str, run_id: str) -> dict[str, int]:
    """Copy one run's simulator tables from the source schema into the target.

    The Research view reads the `mta_sim_*` tables reflectively through
    `search_path`, because the external simulator repository owns their schema
    and redeclaring it here would create a second definition free to disagree
    with the one that writes them. That same reflection is why the tables have
    to exist in the schema being read: a derived schema without them shows no
    runs, no budget response curves, and no per-currency product economics,
    even though the source holds all three.

    Copied rather than derived, and sliced by `run_id` rather than filtered by
    marketplace, because a scenario is exactly one run. The result is the run's
    own rows, byte for byte, with no aggregation to disagree with the source.

    `create table as select` carries the column types across but not the
    constraints, which is what the reflective reader needs and all it needs.
    """
    copied: dict[str, int] = {}
    for table in RESEARCH_TABLES:
        exists = connection.execute(
            text(
                "select 1 from information_schema.tables "
                "where table_schema = :schema and table_name = :table"
            ),
            {"schema": source, "table": table},
        ).first()
        if not exists:
            continue
        connection.execute(text(f"drop table if exists {_quote(target)}.{_quote(table)}"))
        connection.execute(
            text(
                f"create table {_quote(target)}.{_quote(table)} as "
                f"select * from {_quote(source)}.{_quote(table)} where run_id = :run"
            ),
            {"run": run_id},
        )
        copied[table] = connection.execute(
            text(f"select count(*) from {_quote(target)}.{_quote(table)}")
        ).scalar_one()
    return copied


# ---------------------------------------------------------------------------
# Deriving the dashboard model
# ---------------------------------------------------------------------------


def derive_attribution(
    paths: Sequence[Mapping[str, Any]], ads: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Run both models, join spend, and compare -- the file pipeline's stage two.

    Reuses the published implementations rather than restating them, so a
    derived schema and a published CSV are two renderings of one calculation.
    """
    spend = aggregate_spend_by_touchpoint(ads)
    markov = result_rows("markov", run_markov_attribution(paths), spend)
    shapley = result_rows("shapley", run_shapley_attribution(paths), spend)
    comparison = compare_attribution_models(markov, shapley, amc_rows=list(paths))
    return {
        "markov": markov,
        "shapley": shapley,
        "touchpoints": comparison.touchpoints,
        "summary": comparison.summary,
        "recommended": comparison.recommended,
    }


def _point_estimate(row: Mapping[str, Any]) -> float:
    """The single share a recommended-attribution row stands behind.

    Mirrors the strategy module's own reading of the field: a reliable row
    states a number, an unreliable one states a `[low,high]` range whose
    midpoint is used, and an outcome with no volume states the empty string.
    `recommended_value` rather than `official_share` because only the former
    is defined for every row.
    """
    value = row.get("recommended_value")
    if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
        low, _, high = value[1:-1].partition(",")
        try:
            return (float(low) + float(high)) / 2.0
        except ValueError:
            return 0.0
    return as_float(str(value)) or 0.0


def journeys_by_touchpoint(paths: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Journeys touched by each touchpoint, summed over the paths containing it.

    A path's `users` counts the journeys that took it, so a touchpoint's
    journey count is the total over every path it appears in. A journey that
    met the same touchpoint twice is counted once for that path, which is what
    makes this a count of journeys rather than of touches.
    """
    totals: dict[str, int] = defaultdict(int)
    for row in paths:
        users = int(row.get("users") or 0)
        for key in {part.strip() for part in str(row["path"]).split(">")}:
            if key and key != "Null":
                totals[key] += users
    return dict(totals)


def product_weights(entities: Mapping[str, Any]) -> dict[tuple[str, str], list[tuple[str, float]]]:
    """How each Campaign's touchpoint outcomes divide across its Products.

    The simulator records revenue per Campaign, touchpoint, and Product, which
    is direct evidence of the split and is used wherever it exists. Touchpoints
    with no product-level outcome -- the impression legs, which sell nothing
    themselves -- fall back to the Campaign's own split across its other
    touchpoints, so an impression's attributed credit lands on the Products
    that Campaign actually sells rather than being spread evenly over its
    catalogue. A Campaign with no product evidence at all divides equally over
    the Products it is linked to, and one with no links produces a single row
    carrying no Product, so its spend is still reported.

    Weights are returned per `(campaign_id, touchpoint_key)` and always sum to
    one, which is what keeps the split from changing any total.
    """
    linked: dict[str, list[str]] = defaultdict(list)
    for row in entities["links"]:
        linked[str(row["campaign_id"])].append(str(row["product_id"]))

    by_pair: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_campaign: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in entities["outcomes"]:
        campaign = str(row["campaign_id"])
        product = str(row["product_id"])
        revenue = float(row.get("total_revenue") or 0.0)
        units = float(row.get("total_units") or 0.0)
        # Revenue where there is any, units otherwise: a Product that sold at a
        # zero recorded price still took part in the outcome.
        value = revenue if revenue > 0 else units
        by_pair[(campaign, str(row["touchpoint_key"]))][product] += value
        by_campaign[campaign][product] += value

    def normalize(shares: Mapping[str, float]) -> list[tuple[str, float]]:
        total = sum(shares.values())
        if total <= 0:
            return []
        return [(product, value / total) for product, value in sorted(shares.items())]

    weights: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for row in entities["delivery"]:
        pair = (str(row["campaign_id"]), str(row["touchpoint_key"]))
        resolved = normalize(by_pair.get(pair, {})) or normalize(by_campaign.get(pair[0], {}))
        if not resolved:
            products = linked.get(pair[0]) or []
            resolved = (
                [(product, 1.0 / len(products)) for product in products]
                if products
                else [("", 1.0)]
            )
        weights[pair] = resolved
    return weights


def bridge_rows(
    entities: Mapping[str, Any],
    derived: Mapping[str, Any],
    paths: Sequence[Mapping[str, Any]],
    scenario: Mapping[str, Any],
) -> list[dict]:
    """The touchpoint-to-campaign-to-product bridge.

    The one derived quantity with no direct source. The simulator records
    delivery per Campaign and per touchpoint; attribution produces an outcome
    per touchpoint across all Campaigns. The bridge needs the outcome per
    Campaign, which neither side states on its own.

    Where a touchpoint was delivered by a single Campaign -- the shape of every
    scenario this has been run against -- the whole attributed outcome belongs
    to that Campaign and nothing is assumed. Where several Campaigns share one
    touchpoint, the outcome is split between them in proportion to their share
    of that touchpoint's cost, which does assume that two Campaigns spending
    equally on the same touchpoint earned equally from it. Cost is the right
    splitter because it is the quantity the strategy module reallocates;
    delivery volume alone would credit a cheap high-impression Campaign over an
    expensive converting one. Campaigns that all spent nothing split evenly,
    since with no cost to weight by none has a stronger claim.

    Each Campaign's share is then divided across the Products it advertised on
    that touchpoint, so the Products and Product Economics sections describe
    the scenario's own catalogue. Delivery is divided by the same weights,
    which keeps cost and outcome attributed to the same Product.

    A touchpoint that took delivery but appears in no path still gets its rows,
    carrying zero assisted outcomes, so its spend is reported rather than
    dropped.
    """
    totals = {
        "converted_users": float(scenario["converted_users"]),
        "purchase_count": float(scenario["purchase_count"]),
        "revenue": float(scenario["revenue"]),
    }
    share_of: dict[str, dict[str, float]] = {outcome: {} for outcome in totals}
    for row in derived["recommended"]:
        outcome = str(row.get("outcome") or "")
        if outcome in share_of:
            share_of[outcome][str(row["touchpoint"])] = _point_estimate(row)

    cost_by_touchpoint: dict[str, float] = defaultdict(float)
    campaigns_by_touchpoint: dict[str, list[str]] = defaultdict(list)
    for row in entities["delivery"]:
        key = str(row["touchpoint_key"])
        cost_by_touchpoint[key] += float(row.get("cost") or 0.0)
        campaigns_by_touchpoint[key].append(str(row["campaign_id"]))

    ad_group_of: dict[str, str] = {}
    for row in entities["ad_groups"]:
        ad_group_of.setdefault(str(row["campaign_id"]), str(row["ad_group_id"]))
    sku_of = {str(row["product_id"]): row.get("sku_id") for row in entities["links"]}
    asin_of = {
        str(row["product_id"]): (row.get("provider_ad_identifiers") or {})
        for row in entities["links"]
    }
    provider_of = {
        str(row["campaign_id"]): str(row.get("provider") or "") for row in entities["campaigns"]
    }
    journeys = journeys_by_touchpoint(paths)
    weights = product_weights(entities)

    rows: list[dict] = []
    for row in entities["delivery"]:
        key = str(row["touchpoint_key"])
        campaign_id = str(row["campaign_id"])
        campaign_cost = float(row.get("cost") or 0.0)
        touchpoint_cost = cost_by_touchpoint[key]
        peers = campaigns_by_touchpoint[key]
        campaign_share = (
            campaign_cost / touchpoint_cost if touchpoint_cost > 0 else 1.0 / len(peers)
        )
        for product_id, product_share in weights[(campaign_id, key)]:
            share = campaign_share * product_share
            identifiers = asin_of.get(product_id) or {}
            rows.append(
                {
                    "report_start_date": scenario["report_start_date"],
                    "report_end_date": scenario["report_end_date"],
                    "marketplace": scenario["marketplace"],
                    "advertiser_id": scenario["advertiser_id"],
                    "campaign_group_id": scenario["campaign_group_id"],
                    "campaign_id": campaign_id,
                    "ad_group_id": ad_group_of.get(campaign_id, f"{campaign_id}_ad_group_1"),
                    "sku_id": sku_of.get(product_id) or None,
                    "advertised_asin": identifiers.get(provider_of.get(campaign_id, "")),
                    "touchpoint": key,
                    "unique_users": 0,
                    "journey_count": int(round(journeys.get(key, 0) * share)),
                    "impressions": int(round(float(row.get("impressions") or 0) * share)),
                    "clicks": int(round(float(row.get("clicks") or 0) * share)),
                    "cost": round(campaign_cost * product_share, 2),
                    "assisted_converted_users": round(
                        share_of["converted_users"].get(key, 0.0)
                        * totals["converted_users"]
                        * share,
                        4,
                    ),
                    "assisted_purchase_count": round(
                        share_of["purchase_count"].get(key, 0.0)
                        * totals["purchase_count"]
                        * share,
                        4,
                    ),
                    "assisted_revenue": round(
                        share_of["revenue"].get(key, 0.0) * totals["revenue"] * share, 2
                    ),
                    "reported_purchases": int(
                        round(float(row.get("reported_purchases") or 0) * share)
                    ),
                    "reported_sales": round(
                        float(row.get("reported_sales") or 0.0) * share, 2
                    ),
                }
            )
    return rows


def candidate_counts(entities: Mapping[str, Any], campaign_id: str) -> dict[str, int]:
    """Eligible targeting inventory for one Campaign, as the scenario states it.

    The simulator models delivery and outcomes, not the targeting objects a new
    Ad Group would be built around. The one count it does establish is the
    number of Products linked to the Campaign, which becomes the SKU count. The
    keyword, legal-pair, target, and audience counts are written as zero rather
    than as a plausible number, because the scenario provides no evidence for
    any value and a fabricated one would flow straight into a recommended Ad
    Group count.
    """
    counts = {field: 0 for field in CANDIDATE_FIELDS}
    counts["eligible_sku_count"] = sum(
        1 for row in entities["links"] if str(row["campaign_id"]) == campaign_id
    )
    return counts


def _digest(rows: Sequence[Mapping[str, Any]]) -> str:
    """A stable SHA-256 over derived rows, standing in for a file digest."""
    payload = json.dumps(
        [dict(sorted(row.items())) for row in rows],
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def strategy_documents(
    entities: Mapping[str, Any],
    scenario: Mapping[str, Any],
    derived: Mapping[str, Any],
    bridge: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The strategy request and candidate pool describing this scenario.

    Assembled in memory rather than written under `data/simulated/`, because
    the committed pair describes the demo account and must not be overwritten
    by a derivation of a different one.

    `mta_source` records lineage the way the committed request does, with the
    digests taken over the derived rows themselves. There is no file to hash
    here, so hashing the exact rows that were used states what a file digest
    states: which inputs produced this recommendation.
    """
    campaigns = [
        {
            "campaign_id": str(row["campaign_id"]),
            "campaign_name": str(row.get("campaign_name") or row["campaign_id"]),
            "ad_product": str(row["ad_product"]),
            "status": "enabled",
        }
        for row in entities["campaigns"]
    ]
    total_budget = sum(
        float(row.get("baseline_daily_budget") or 0.0) for row in entities["campaigns"]
    )
    pool_id = f"pool_{scenario['marketplace'].lower()}_derived"
    request = {
        "sample_version": "4.0",
        "candidate_pool_id": pool_id,
        "mta_batch_id": scenario["batch_id"],
        "mta_source": {
            "report_start_date": scenario["report_start_date"],
            "report_end_date": scenario["report_end_date"],
            "marketplace": scenario["marketplace"],
            "advertiser_id": scenario["advertiser_id"],
            "attribution_file": f"{scenario['source_schema']}.amc_path_report",
            "attribution_sha256": _digest(derived["recommended"]),
            "entity_file": f"{scenario['source_schema']}.mta_sim_delivery_observation",
            "entity_sha256": _digest(bridge),
            "available_touchpoint_count": len(
                {str(row["touchpoint"]) for row in derived["recommended"]}
            ),
            "entity_row_count": len(bridge),
        },
        "campaign_group": {
            "campaign_group_id": scenario["campaign_group_id"],
            "group_name": f"{scenario['advertiser_id']} {scenario['marketplace']}",
            "platform": "AMAZON",
            "marketplace": scenario["marketplace"],
            "advertiser_id": scenario["advertiser_id"],
            "currency": scenario["currency"],
            "total_daily_budget": round(total_budget, 2),
        },
        "campaigns": campaigns,
        "outcome_weights": dict(OUTCOME_WEIGHTS),
        "capacity_rules": {
            product: dict(CAPACITY_RULES[product]) for product in SUPPORTED_AD_PRODUCTS
        },
    }
    pool = {
        "sample_version": "4.0",
        "candidate_pool_id": pool_id,
        "campaign_group_id": scenario["campaign_group_id"],
        "candidate_usage_policy": "USE_ALL_ELIGIBLE",
        "campaign_candidate_counts": [
            {
                "campaign_id": campaign["campaign_id"],
                **candidate_counts(entities, campaign["campaign_id"]),
            }
            for campaign in campaigns
        ],
    }
    return request, pool


def budget_blockers(request: Mapping[str, Any], pool: Mapping[str, Any]) -> list[str]:
    """Why this scenario cannot produce a budget recommendation, if it cannot.

    `generate_budget_recommendation()` models a Campaign Group of exactly four
    Campaigns, one per Amazon ad product, because it bridges attribution into
    budget *through* the ad product: a touchpoint names an ad product, and that
    ad product has to name one Campaign for the evidence to land anywhere. It
    then sizes each Campaign from its eligible targeting inventory, and refuses
    a zero count rather than recommending an Ad Group with nothing to put in
    it.

    Both are checked before calling rather than after failing, so the message
    names the property of the scenario rather than the contract clause it
    tripped. Reporting every blocker at once matters here: fixing the Campaign
    shape alone would not make a recommendation possible while the inventory
    counts are still absent.
    """
    reasons: list[str] = []
    campaigns = list(request["campaigns"])
    products = [campaign["ad_product"] for campaign in campaigns]
    duplicated = sorted({product for product in products if products.count(product) > 1})
    if duplicated:
        reasons.append(
            f"{len(campaigns)} campaigns share ad product(s) {', '.join(duplicated)}, "
            "and the strategy module reaches a campaign only through its ad product"
        )
    elif len(campaigns) != len(SUPPORTED_AD_PRODUCTS):
        reasons.append(
            f"{len(campaigns)} campaigns, but the strategy module models a group "
            f"of {len(SUPPORTED_AD_PRODUCTS)}, one per ad product"
        )

    by_campaign = {
        entry["campaign_id"]: entry for entry in pool["campaign_candidate_counts"]
    }
    for campaign in campaigns:
        counts = by_campaign[campaign["campaign_id"]]
        required = (
            ("eligible_keyword_unit_count", "eligible_sku_count", "eligible_legal_pair_count")
            if campaign["ad_product"] in SEARCH_AD_PRODUCTS
            else ("eligible_sku_count", "eligible_target_count", "eligible_audience_count")
        )
        absent = [field for field in required if not counts[field]]
        if absent:
            reasons.append(
                f"{campaign['campaign_id']} establishes no {', '.join(absent)}; "
                "the simulator models delivery, not targeting inventory"
            )
    return reasons


def budget_layer(
    request: Mapping[str, Any],
    pool: Mapping[str, Any],
    derived: Mapping[str, Any],
    bridge: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """The budget recommendation, when the scenario has the shape it requires.

    Skipped with a stated reason rather than forced: a rearranged Campaign list
    and invented inventory counts would produce a confident number about a
    Campaign Group that was never run. Everything else in the schema is derived
    either way, so the Budget Manager's recommendation section stands empty
    while every other view is complete.
    """
    reasons = budget_blockers(request, pool)
    if reasons:
        return None, "; ".join(reasons)
    try:
        document = generate_budget_recommendation(
            request,
            pool,
            [dict(row) for row in derived["recommended"]],
            [dict(row) for row in bridge],
        )
    except BudgetRecommendationError as error:
        return None, str(error)
    return document, ""


# ---------------------------------------------------------------------------
# Writing the derived schema
# ---------------------------------------------------------------------------


class SimulatorImporter(Importer):
    """Writes a derived scenario using the file importer's own row builders.

    Subclasses rather than duplicates `Importer`, so the entity and touchpoint
    handling -- which decides how a five-segment key becomes a `Touchpoint`
    row, and how a candidate count becomes a `TargetingCandidate` -- exists
    once and cannot drift between the two commands.
    """

    def import_derived_entities(
        self,
        request: Mapping[str, Any],
        pool: Mapping[str, Any],
        entities: Mapping[str, Any],
    ) -> None:
        """Advertiser, group, campaigns, candidate counts, and ad groups."""
        self.import_entities(dict(request), dict(pool))
        seen: set[str] = set()
        for row in entities["ad_groups"]:
            campaign = self.campaigns.get(str(row["campaign_id"]))
            ad_group_id = str(row["ad_group_id"])
            if campaign is None or ad_group_id in seen:
                continue
            self.session.add(AdGroup(ad_group_id=ad_group_id, campaign=campaign))
            seen.add(ad_group_id)
        self.record("ad_group", len(seen))

    def import_derived_ads(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """Daily platform performance, one row per date and touchpoint."""
        for row in rows:
            self.session.add(
                AdsDailyPerformance(
                    report_date=as_date(str(row["reportDate"])),
                    marketplace=str(row["marketplace"]),
                    account_id=str(row["accountId"]),
                    currency=str(row.get("currencyCode") or "USD"),
                    impressions=as_int(str(row.get("impressions") or 0)),
                    clicks=as_int(str(row.get("clicks") or 0)),
                    cost=float(row.get("cost") or 0.0),
                    purchases=as_int(str(row.get("purchases") or 0)),
                    sales=float(row.get("sales") or 0.0),
                    touchpoint=self.touchpoint(
                        str(row["normalizedTouchpoint"]), row.get("cost_type")
                    ),
                )
            )
        self.record("ads_daily_performance", len(rows))

    def import_derived_paths(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """The aggregated path report, one row per distinct path."""
        for row in rows:
            path = str(row["path"])
            self.session.add(
                PathReport(
                    report_start_date=as_date(str(row["report_start_date"])),
                    report_end_date=as_date(str(row["report_end_date"])),
                    marketplace=str(row["marketplace"]),
                    advertiser_id=str(row["advertiser_id"]),
                    path=path,
                    path_length=path.count(">") + 1,
                    users=row["users"],
                    converted_users=row["converted_users"],
                    purchase_count=row["purchase_count"],
                    revenue=row["revenue"],
                )
            )
        self.record("path_report", len(rows))

    def import_derived_bridge(self, rows: Sequence[Mapping[str, Any]]) -> None:
        """The touchpoint-to-entity bridge."""
        for row in rows:
            self.session.add(
                TouchpointEntityBridge(
                    report_start_date=as_date(str(row["report_start_date"])),
                    report_end_date=as_date(str(row["report_end_date"])),
                    marketplace=row["marketplace"],
                    advertiser_id=row["advertiser_id"],
                    campaign_group_id=row["campaign_group_id"],
                    campaign_id=row["campaign_id"],
                    ad_group_id=row["ad_group_id"],
                    sku_id=row["sku_id"],
                    advertised_asin=row["advertised_asin"],
                    unique_users=row["unique_users"],
                    journey_count=row["journey_count"],
                    impressions=row["impressions"],
                    clicks=row["clicks"],
                    cost=row["cost"],
                    assisted_converted_users=row["assisted_converted_users"],
                    assisted_purchase_count=row["assisted_purchase_count"],
                    assisted_revenue=row["assisted_revenue"],
                    reported_purchases=row["reported_purchases"],
                    reported_sales=row["reported_sales"],
                    touchpoint=self.touchpoint(row["touchpoint"]),
                )
            )
        self.record("touchpoint_entity_bridge", len(rows))

    def import_derived_attribution(
        self, derived: Mapping[str, Any], scenario: Mapping[str, Any]
    ) -> None:
        """The attribution run and the four model-output tables."""
        summary = derived["summary"]
        run = AttributionRun(
            batch_id=scenario["batch_id"],
            report_start_date=as_date(str(scenario["report_start_date"])),
            report_end_date=as_date(str(scenario["report_end_date"])),
            marketplace=scenario["marketplace"],
            advertiser_id=scenario["advertiser_id"],
            max_touchpoint_gap_days=as_int(
                str(summary[0].get("max_touchpoint_gap_days") if summary else 14)
            )
            or 14,
            imported_at=datetime.now(),
        )
        self.session.add(run)
        self.record("attribution_run", 1)

        results = 0
        for model in ("markov", "shapley"):
            for row in derived[model]:
                self.session.add(
                    AttributionResult(
                        attribution_model=row["attribution_model"],
                        converted_user_share=as_float(str(row["converted_user_share"])) or 0.0,
                        purchase_count_share=as_float(str(row["purchase_count_share"])) or 0.0,
                        revenue_share=as_float(str(row["revenue_share"])) or 0.0,
                        attributed_converted_users=as_float(
                            str(row["attributed_converted_users"])
                        )
                        or 0.0,
                        attributed_purchase_count=as_float(
                            str(row["attributed_purchase_count"])
                        )
                        or 0.0,
                        attributed_revenue=as_float(str(row["attributed_revenue"])) or 0.0,
                        impressions=as_int(str(row.get("impressions") or 0)),
                        clicks=as_int(str(row.get("clicks") or 0)),
                        cost=as_float(str(row.get("cost") or 0)) or 0.0,
                        reported_purchases=as_int(str(row.get("reported_purchases") or 0)),
                        reported_sales=as_float(str(row.get("reported_sales") or 0)) or 0.0,
                        roas=as_float(str(row.get("roas"))),
                        roi=as_float(str(row.get("roi"))),
                        cpa=as_float(str(row.get("cpa"))),
                        cost_per_converted_user=as_float(
                            str(row.get("cost_per_converted_user"))
                        ),
                        run=run,
                        touchpoint=self.touchpoint(row["touchpoint"]),
                    )
                )
                results += 1
        self.record("attribution_result", results)

        for row in derived["touchpoints"]:
            self.session.add(
                ModelComparisonTouchpoint(
                    outcome=row["outcome"],
                    markov_share=as_float(str(row["markov_share"])) or 0.0,
                    shapley_share=as_float(str(row["shapley_share"])) or 0.0,
                    gap_pp=as_float(str(row["gap_pp"])) or 0.0,
                    relative_gap=as_float(str(row.get("relative_gap"))),
                    raw_unique_paths=as_int(str(row.get("raw_unique_paths") or 0)),
                    raw_converted_users=as_int(str(row.get("raw_converted_users") or 0)),
                    raw_purchase_count=as_int(str(row.get("raw_purchase_count") or 0)),
                    calculation_valid=as_bool(str(row.get("calculation_valid"))),
                    data_support_sufficient=as_bool(str(row.get("data_support_sufficient"))),
                    models_consistent=as_bool(str(row.get("models_consistent"))),
                    reliability_status=row["reliability_status"],
                    reliability_reason=row["reliability_reason"],
                    run=run,
                    touchpoint=self.touchpoint(row["touchpoint"]),
                )
            )
        self.record("model_comparison_touchpoint", len(derived["touchpoints"]))

        for row in summary:
            self.session.add(
                ModelComparisonSummary(
                    outcome=row["outcome"],
                    touchpoint_count=as_int(str(row.get("touchpoint_count") or 0)),
                    tvd=as_float(str(row.get("tvd") or 0)) or 0.0,
                    spearman_rho=as_float(str(row.get("spearman_rho"))),
                    top_k_overlap_rate=as_float(str(row.get("top_k_overlap_rate"))),
                    calculation_valid=as_bool(str(row.get("calculation_valid"))),
                    data_support_sufficient=as_bool(str(row.get("data_support_sufficient"))),
                    models_consistent=as_bool(str(row.get("models_consistent"))),
                    reliability_status=row["reliability_status"],
                    reliability_reason=row["reliability_reason"],
                    run=run,
                )
            )
        self.record("model_comparison_summary", len(summary))

        for row in derived["recommended"]:
            self.session.add(
                RecommendedAttribution(
                    outcome=row["outcome"],
                    official_model=row["official_model"],
                    official_share=as_float(str(row.get("official_share"))),
                    recommended_value=str(row.get("recommended_value") or ""),
                    benchmark_model=row["benchmark_model"],
                    benchmark_share=as_float(str(row.get("benchmark_share"))),
                    gap_pp=as_float(str(row.get("gap_pp"))),
                    relative_gap=as_float(str(row.get("relative_gap"))),
                    calculation_valid=as_bool(str(row.get("calculation_valid"))),
                    data_support_sufficient=as_bool(str(row.get("data_support_sufficient"))),
                    models_consistent=as_bool(str(row.get("models_consistent"))),
                    reliability_status=row["reliability_status"],
                    reliability_reason=row["reliability_reason"],
                    run=run,
                    touchpoint=self.touchpoint(row["touchpoint"]),
                )
            )
        self.record("recommended_attribution", len(derived["recommended"]))


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def derive_scenario(
    connection,
    session: Session,
    source: str,
    listing: Mapping[str, Any],
) -> tuple[dict[str, int], str, str]:
    """Derive one scenario into the session's schema.

    Returns the row counts written, the reason a budget recommendation was
    skipped if it was, and the run the scenario came from.
    """
    marketplace = str(listing["marketplace"])
    advertiser = str(listing["advertiser_id"])
    window = (str(listing["report_start_date"]), str(listing["report_end_date"]))

    entities = simulator_entities(connection, source, marketplace)
    paths = aggregate_paths(connection, source, marketplace, advertiser, window)
    ads = ads_rows(connection, source, marketplace, advertiser)
    if not paths:
        raise DerivationError(f"{marketplace}: the source schema holds no path rows")
    if not ads:
        raise DerivationError(f"{marketplace}: the source schema holds no Ads rows")

    scenario = {
        "marketplace": marketplace,
        "advertiser_id": advertiser,
        "currency": str(ads[0].get("currencyCode") or "USD"),
        "campaign_group_id": f"CG_{marketplace.upper()}",
        "source_schema": source,
        "batch_id": f"mta_{marketplace.lower()}_{entities['run_id']}",
        "report_start_date": window[0],
        "report_end_date": window[1],
        "converted_users": sum(row["converted_users"] for row in paths),
        "purchase_count": sum(row["purchase_count"] for row in paths),
        "revenue": sum(row["revenue"] for row in paths),
    }

    try:
        derived = derive_attribution(paths, ads)
    except ValueError as error:
        raise DerivationError(f"{marketplace}: attribution failed: {error}") from error

    bridge = bridge_rows(entities, derived, paths, scenario)
    request, pool = strategy_documents(entities, scenario, derived, bridge)
    budget, skipped = budget_layer(request, pool, derived, bridge)

    importer = SimulatorImporter(session)
    importer.import_derived_entities(request, pool, entities)
    importer.import_derived_ads(ads)
    importer.import_derived_paths(paths)
    importer.import_derived_bridge(bridge)
    importer.import_derived_attribution(derived, scenario)
    if budget is not None:
        importer.import_budget(budget)
    importer.record("touchpoint", len(importer.touchpoints))
    return importer.counts, skipped, str(entities["run_id"])


def _target_schema(source: str, marketplace: str, override: str | None) -> str:
    """The schema one scenario is written into."""
    return override or f"{source}_{marketplace.lower()}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="mta",
        help="Schema holding the simulator's tables. Defaults to 'mta'.",
    )
    parser.add_argument(
        "--marketplace",
        default=None,
        help="Which scenario to derive. Required unless --all or --list is given.",
    )
    parser.add_argument(
        "--all", action="store_true", help="Derive every scenario into its own schema."
    )
    parser.add_argument(
        "--schema",
        default=None,
        help=(
            "Target schema for a single derivation. Defaults to "
            "'<source>_<marketplace>'. Cannot be combined with --all, which "
            "names each target after its own scenario."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Report the scenarios the source schema holds and exit.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop and rebuild the dashboard tables in the target schema.",
    )
    args = parser.parse_args()

    if not config.valid_schema_name(args.source):
        print(f"INVALID: {args.source!r} is not a valid schema name.", file=sys.stderr)
        return 1

    settings = config.database_settings()
    print(f"Source: {settings.safe_summary()} schema={args.source}")
    # The reading connection is deliberately unpinned. Every source read names
    # its schema explicitly, and a `search_path` here would make which schema
    # was read depend on a setting rather than on the argument.
    reader = create_engine(settings.url(), connect_args={"connect_timeout": 20})
    notes: list[str] = []
    try:
        with reader.connect() as connection:
            missing = missing_source_tables(connection, args.source)
            if missing:
                print(
                    f"INVALID: schema {args.source!r} is missing the simulator "
                    f"table(s): {', '.join(missing)}",
                    file=sys.stderr,
                )
                return 1
            found = scenarios(connection, args.source)
            if not found:
                print(
                    f"INVALID: schema {args.source!r} holds no path report rows.",
                    file=sys.stderr,
                )
                return 1

            if args.list:
                print(f"\nScenarios in {args.source!r}:")
                for row in found:
                    target = _target_schema(args.source, str(row["marketplace"]), None)
                    print(
                        f"  {row['marketplace']:<8} {row['advertiser_id']:<34} "
                        f"{row['report_start_date']}..{row['report_end_date']}  "
                        f"{row['path_rows']:>6} rows / {row['distinct_paths']:>3} paths"
                        f"  -> {target}"
                    )
                return 0

            if args.all:
                selected = list(found)
            elif args.marketplace:
                selected = [
                    row
                    for row in found
                    if str(row["marketplace"]).upper() == args.marketplace.upper()
                ]
                if not selected:
                    print(
                        f"INVALID: no scenario for marketplace {args.marketplace!r}. "
                        f"Run with --list to see what {args.source!r} holds.",
                        file=sys.stderr,
                    )
                    return 1
            else:
                print("INVALID: give --marketplace, --all, or --list.", file=sys.stderr)
                return 1

            if args.schema and len(selected) > 1:
                print(
                    "INVALID: --schema names one target and cannot be combined "
                    "with --all.",
                    file=sys.stderr,
                )
                return 1

            for listing in selected:
                marketplace = str(listing["marketplace"])
                target = _target_schema(args.source, marketplace, args.schema)
                if not config.valid_schema_name(target):
                    print(
                        f"INVALID: {target!r} is not a valid schema name.",
                        file=sys.stderr,
                    )
                    return 1
                if target == args.source:
                    print(
                        f"INVALID: the target schema must differ from the source "
                        f"({args.source!r}); deriving in place would overwrite the "
                        "simulator's own tables.",
                        file=sys.stderr,
                    )
                    return 1

                target_settings = dataclass_replace(settings, schema=target)
                writer = create_engine(
                    target_settings.url(), connect_args=target_settings.connect_args()
                )
                try:
                    created = ensure_schema(writer, target)
                    print(
                        f"\n{marketplace} -> schema {target} "
                        f"({'created' if created else 'already present'})"
                    )
                    if args.replace:
                        Base.metadata.drop_all(writer)
                    Base.metadata.create_all(writer)
                    with Session(writer) as session:
                        counts, skipped, run_id = derive_scenario(
                            connection, session, args.source, listing
                        )
                        session.commit()
                    # Copied on the writer so the history lands in the same
                    # transaction lifecycle as the schema it belongs to.
                    with writer.begin() as writing:
                        research = copy_research_tables(
                            writing, args.source, target, run_id
                        )
                    counts.update(research)
                    for table in sorted(counts):
                        print(f"  {table:<34} {counts[table]:>7}")
                    if skipped:
                        notes.append(f"{marketplace}: no budget recommendation -- {skipped}")
                except DerivationError as error:
                    print(f"INVALID: {error}", file=sys.stderr)
                    return 1
                finally:
                    writer.dispose()
    finally:
        reader.dispose()

    if notes:
        print("\nDerived with gaps:")
        for note in notes:
            print(f"  - {note}")
    print("\nSelect a derived schema in the dashboard's settings to read it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
