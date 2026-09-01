"""Discover and materialize server-owned datasets for runnable model stages.

The browser receives opaque identifiers and human-readable labels, never a
filesystem path, schema name, or query fragment.  A submitted identifier is
resolved again immediately before a run, then the selected database scope is
written below ``PIPELINE_OUTPUT_DIR`` in the file contract expected by the
existing command-line stage.

Data flow:
    selected database schema -> dataset descriptor -> stage input files
      -> backend.services.jobs -> script/* model command
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.config import pipeline_output_directory
from backend.database import sql, table_exists
from modules.mta_attribution.src.synthetic_event_pipeline import ADS_FIELDS
from modules.mta_standard.src.dataloader import MTA_SIM_PATH_REPORT_FIELDS


class DatasetError(ValueError):
    """A missing, stale, or incompatible server-issued dataset selection."""


@dataclass(frozen=True)
class PreparedDataset:
    """Paths and scope values a stage command consumes."""

    dataset_id: str
    marketplace: str
    path_report: Path | None = None
    performance_report: Path | None = None
    research_snapshot: Path | None = None


def datasets_for(stage: str) -> list[dict[str, str]]:
    """Return compatible database scopes for one model stage."""
    if stage == "attribution":
        return _attribution_datasets()
    if stage in {"optimization", "evaluation"}:
        return _research_datasets()
    return []


def resolve_dataset(stage: str, dataset_id: str | None) -> dict[str, str]:
    """Revalidate one opaque identifier against the database's current state."""
    selected = str(dataset_id or "").strip()
    if not selected:
        raise DatasetError("datasetId is required for every model run.")
    for dataset in datasets_for(stage):
        if dataset["id"] == selected:
            return dataset
    raise DatasetError(
        "The selected dataset is no longer available for this model. "
        "Refresh the page and choose one of the datasets reported by the server."
    )


def prepare_dataset(stage: str, dataset: dict[str, str]) -> PreparedDataset:
    """Materialize a revalidated selection below the configured runtime root."""
    runtime = pipeline_output_directory()
    if runtime is None:
        raise DatasetError(
            "PIPELINE_OUTPUT_DIR must name a writable directory before models "
            "can prepare database inputs."
        )
    target = runtime / "datasets" / stage
    target.mkdir(parents=True, exist_ok=True)
    if stage == "attribution":
        path_report = target / "path_report.csv"
        performance = target / "amazon_ads_report.csv"
        _write_attribution_inputs(dataset, path_report, performance)
        return PreparedDataset(
            dataset_id=dataset["id"],
            marketplace=dataset["marketplace"],
            path_report=path_report,
            performance_report=performance,
        )
    if stage in {"optimization", "evaluation"}:
        snapshot = target / "simulation_research.json"
        _write_research_snapshot(dataset, snapshot)
        return PreparedDataset(
            dataset_id=dataset["id"],
            marketplace=dataset["marketplace"],
            research_snapshot=snapshot,
        )
    raise DatasetError(f"Unknown model stage: {stage}.")


def _attribution_datasets() -> list[dict[str, str]]:
    required = ("path_report", "ads_daily_performance", "touchpoint")
    if not all(table_exists(name) for name in required):
        return []
    rows = sql(
        """
        select p.report_start_date, p.report_end_date, p.marketplace,
               p.advertiser_id, count(*)::int as path_count
          from path_report p
         where exists (
               select 1 from ads_daily_performance a
                where a.report_date between p.report_start_date and p.report_end_date
                  and a.marketplace = p.marketplace
                  and a.account_id = p.advertiser_id
         )
         group by p.report_start_date, p.report_end_date, p.marketplace,
                  p.advertiser_id
         order by p.report_end_date desc, p.marketplace, p.advertiser_id
        """
    )
    return [
        {
            "id": "attribution|{}|{}|{}|{}".format(
                _text(row["report_start_date"]),
                _text(row["report_end_date"]),
                row["marketplace"],
                row["advertiser_id"],
            ),
            "label": (
                f"{row['marketplace']} · {row['advertiser_id']} · "
                f"{_text(row['report_start_date'])} to "
                f"{_text(row['report_end_date'])}"
            ),
            "description": f"{int(row['path_count']):,} aggregated paths",
            "marketplace": str(row["marketplace"]),
            "advertiserId": str(row["advertiser_id"]),
            "reportStartDate": _text(row["report_start_date"]),
            "reportEndDate": _text(row["report_end_date"]),
        }
        for row in rows
    ]


def _research_datasets() -> list[dict[str, str]]:
    required = (
        "mta_simulation_run",
        "mta_sim_provider",
        "mta_sim_product",
        "mta_sim_product_economics",
        "mta_sim_campaign",
        "mta_sim_ad_group",
        "mta_sim_campaign_product_link",
        "mta_sim_delivery_observation",
        "mta_sim_budget_observation",
        "mta_sim_outcome_observation",
    )
    if not all(table_exists(name) for name in required):
        return []
    rows = sql(
        """
        select b.run_id, b.marketplace, min(b.report_date) as report_start_date,
               max(b.report_date) as report_end_date,
               count(*)::int as observation_count
          from mta_sim_budget_observation b
         where exists (
               select 1 from mta_sim_outcome_observation o
                where o.run_id = b.run_id
                  and o.marketplace = b.marketplace
                  and o.evaluation_only = false
         )
         group by b.run_id, b.marketplace
         order by b.run_id, b.marketplace
        """
    )
    return [
        {
            "id": f"research|{row['run_id']}|{row['marketplace']}",
            "label": (
                f"{row['marketplace']} · run {row['run_id']} · "
                f"{_text(row['report_start_date'])} to "
                f"{_text(row['report_end_date'])}"
            ),
            "description": f"{int(row['observation_count']):,} budget observations",
            "runId": str(row["run_id"]),
            "marketplace": str(row["marketplace"]),
            "reportStartDate": _text(row["report_start_date"]),
            "reportEndDate": _text(row["report_end_date"]),
        }
        for row in rows
    ]


def _write_attribution_inputs(
    dataset: dict[str, str], path_report: Path, performance_report: Path
) -> None:
    parameters = {
        "start": dataset["reportStartDate"],
        "end": dataset["reportEndDate"],
        "marketplace": dataset["marketplace"],
        "advertiser": dataset["advertiserId"],
    }
    paths = sql(
        """
        select report_start_date, report_end_date, marketplace, advertiser_id,
               path, users, converted_users, purchase_count, revenue
          from path_report
         where report_start_date = :start and report_end_date = :end
           and marketplace = :marketplace and advertiser_id = :advertiser
         order by path
        """,
        parameters,
    )
    performance = sql(
        """
        select a.report_date as "reportDate", a.marketplace,
               a.account_id as "accountId", t.ad_product as "adProduct",
               t.format as "adType", t.creative as "creativeType",
               case when t.ad_product = 'AMAZON_DSP' then t.format else null end
                 as "inventoryType",
               t.placement, t.interaction_type, t.cost_type,
               t.touchpoint_key as "normalizedTouchpoint",
               a.currency as "currencyCode", a.impressions, a.clicks, a.cost,
               a.purchases, a.sales
          from ads_daily_performance a
          join touchpoint t on t.id = a.touchpoint_pk
         where a.report_date between :start and :end
           and a.marketplace = :marketplace and a.account_id = :advertiser
         order by a.report_date, t.touchpoint_key
        """,
        parameters,
    )
    if not paths or not performance:
        raise DatasetError("The selected attribution dataset became empty.")
    _write_csv(path_report, list(MTA_SIM_PATH_REPORT_FIELDS), paths)
    _write_csv(performance_report, list(ADS_FIELDS), performance)


def _write_research_snapshot(dataset: dict[str, str], destination: Path) -> None:
    run = dataset["runId"]
    marketplace = dataset["marketplace"]
    run_parameters = {"run": run}
    scope_parameters = {"run": run, "marketplace": marketplace}
    runs = sql(
        "select run_id, seed, configuration_sha256, effective_configuration "
        "from mta_simulation_run where run_id = :run",
        run_parameters,
    )
    if not runs:
        raise DatasetError("The selected research run no longer exists.")
    scope_rows = sql(
        "select advertiser_id, currency, min(report_date) as report_start_date, "
        "max(report_date) as report_end_date from mta_sim_budget_observation "
        "where run_id = :run and marketplace = :marketplace "
        "group by advertiser_id, currency order by advertiser_id, currency",
        scope_parameters,
    )
    if len(scope_rows) != 1:
        raise DatasetError(
            "A research dataset must contain exactly one advertiser and currency scope."
        )
    run_scope = {
        "marketplace": marketplace,
        "advertiser_id": str(scope_rows[0]["advertiser_id"]),
        "currency": str(scope_rows[0]["currency"]),
        "report_start_date": _text(scope_rows[0]["report_start_date"]),
        "report_end_date": _text(scope_rows[0]["report_end_date"]),
    }
    campaigns = _without_internal_id(
        sql(
            "select * from mta_sim_campaign where run_id = :run order by campaign_id",
            run_parameters,
        )
    )
    for campaign in campaigns:
        campaign["reporting_scope"] = run_scope
    nested = {
        "providers": _without_internal_id(
            sql(
                "select * from mta_sim_provider where run_id = :run order by provider",
                run_parameters,
            )
        ),
        "products": _without_internal_id(
            sql(
                "select * from mta_sim_product where run_id = :run order by product_id",
                run_parameters,
            )
        ),
        "product_economics": _without_internal_id(
            sql(
                "select * from mta_sim_product_economics where run_id = :run "
                "order by product_id, currency",
                run_parameters,
            )
        ),
        "campaigns": campaigns,
        "ad_groups": _without_internal_id(
            sql(
                "select * from mta_sim_ad_group where run_id = :run "
                "order by campaign_id, ad_group_id",
                run_parameters,
            )
        ),
        "campaign_product_links": _without_internal_id(
            sql(
                "select * from mta_sim_campaign_product_link where run_id = :run "
                "order by campaign_id, product_id",
                run_parameters,
            )
        ),
    }
    simulation_run = {**runs[0], **nested}
    budgets = _observations(
        sql(
            "select * from mta_sim_budget_observation where run_id = :run "
            "and marketplace = :marketplace order by report_date, campaign_id, budget_level",
            scope_parameters,
        )
    )
    delivery = _observations(
        sql(
            "select * from mta_sim_delivery_observation where run_id = :run "
            "and marketplace = :marketplace order by report_date, campaign_id, id",
            scope_parameters,
        ),
        touchpoints=True,
    )
    outcomes = _observations(
        sql(
            "select * from mta_sim_outcome_observation where run_id = :run "
            "and marketplace = :marketplace and evaluation_only = false "
            "order by report_date, campaign_id, id",
            scope_parameters,
        ),
        touchpoints=True,
    )
    if not budgets or not outcomes:
        raise DatasetError("The selected research dataset has no observed model input.")
    payload = {
        "simulation_runs": [simulation_run],
        "budget_observations": budgets,
        "delivery_observations": delivery,
        "outcome_observations": outcomes,
        # Evaluation-only outcomes are deliberately not materialized into a
        # model runner's filesystem at all.
        "evaluation_outcome_observations": [],
        "data_lineage": [],
        "touchpoint_observations": [],
    }
    _write_json(destination, payload)


def _observations(
    rows: list[dict[str, Any]], *, touchpoints: bool = False
) -> list[dict]:
    prepared = []
    for source in rows:
        row = {
            key: value
            for key, value in source.items()
            if key not in {"id", "run_id", "evaluation_only"}
        }
        report_date = _text(row.pop("report_date"))
        row["reporting_scope"] = {
            "marketplace": row.pop("marketplace"),
            "advertiser_id": row.pop("advertiser_id"),
            "currency": row.pop("currency"),
            "report_start_date": report_date,
            "report_end_date": report_date,
        }
        if touchpoints:
            row["touchpoint"] = _touchpoint_from_key(
                str(row.pop("provider")),
                str(row.pop("touchpoint_key")),
                row.pop("placement_availability", "AVAILABLE"),
                row.pop("creative_availability", "AVAILABLE"),
                row.pop("interaction_type_availability", "AVAILABLE"),
            )
        prepared.append(row)
    return prepared


def _touchpoint_from_key(
    provider: str,
    key: str,
    placement_availability: str,
    creative_availability: str,
    interaction_availability: str,
) -> dict[str, Any]:
    parts = key.split(":")
    if len(parts) != 5:
        raise DatasetError(f"Research touchpoint key is not five-segment: {key!r}.")
    ad_product, fmt, placement, creative, interaction = parts
    placement_value = None if placement == "UNSPECIFIED" else placement
    creative_value = None if creative == "UNSPECIFIED" else creative
    return {
        "provider": provider,
        "ad_product": ad_product,
        "format": fmt,
        "placement": placement_value,
        "creative": creative_value,
        "interaction_type": interaction,
        "field_availability": {
            "placement": (
                "NOT_PROVIDED" if placement_value is None else placement_availability
            ),
            "creative": (
                "NOT_PROVIDED" if creative_value is None else creative_availability
            ),
            "interaction_type": interaction_availability,
        },
    }


def _without_internal_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if key not in {"id", "run_id"}}
        for row in rows
    ]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _text(row.get(field)) for field in fieldnames})
    temporary.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_value,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot encode {type(value).__name__} as JSON")
