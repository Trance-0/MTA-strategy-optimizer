"""Import the project's CSV and JSON artifacts into the dashboard database.

Reads the committed simulated inputs and reproducible outputs, then writes
them into the PostgreSQL schema defined in `dashboard/models.py`. The
dashboard uses that database when `DATABASE=true`; it reads the same files
directly when `DATABASE=false`, so this command is optional.

Data flow:
    modules/mta_attribution/data/simulated/*.csv      -.
    modules/mta_attribution/outputs/attribution/*.csv  +-> PostgreSQL tables
    modules/mta_strategy_recommendation/**/*.json     -'

The command refuses to overwrite a populated database unless `--replace` is
given, so an accidental run cannot destroy existing rows.

`--schema` chooses which schema of the instance receives the tables, so one
database can hold several scenarios side by side. It defaults to `PG_SCHEMA`
in `.env`, and to `public` when that is unset. A named schema is created if it
does not exist; `--replace` then drops and rebuilds the tables within it and
never touches another schema.

Usage:
    uv run --extra dashboard python script/import_to_database.py --dry-run
    uv run --extra dashboard python script/import_to_database.py
    uv run --extra dashboard python script/import_to_database.py --replace
    uv run --extra dashboard python script/import_to_database.py --schema mta --replace
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from dashboard import config  # noqa: E402
from dashboard.models import (  # noqa: E402
    Advertiser,
    AdGroup,
    AdGroupBudgetSlot,
    AdsDailyPerformance,
    AttributionResult,
    AttributionRun,
    Base,
    BudgetRecommendationRun,
    Campaign,
    CampaignBudgetRecommendation,
    CampaignGroup,
    ModelComparisonSummary,
    ModelComparisonTouchpoint,
    PathReport,
    RecommendedAttribution,
    SyntheticUserEvent,
    TargetingCandidate,
    Touchpoint,
    TouchpointEntityBridge,
)

#: Cap on synthetic events imported. The full table is 11,147 rows; the
#: dashboard only aggregates it, so a bounded sample keeps the import quick
#: while preserving the shape. Use --full-events to import every row.
DEFAULT_EVENT_LIMIT = 12_000


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read a project CSV, dropping the Chinese field-description row.

    Only `amazon_ads_report_sample.csv` and `amc_mta_path_report_raw_sample.csv`
    carry that row. The check matches its exact first-cell marker rather than
    guessing, because a heuristic would silently discard a real data row from
    the files that have no description row.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows and str(next(iter(rows[0].values()))) in config.DESCRIPTION_ROW_MARKERS:
        rows = rows[1:]
    return rows


def as_float(value: str | None) -> float | None:
    """Parse a float, returning None for blank or unparsable input."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def as_int(value: str | None) -> int:
    """Parse an integer, returning 0 for blank or unparsable input."""
    parsed = as_float(value)
    return int(parsed) if parsed is not None else 0


def as_bool(value: str | None) -> bool:
    """Parse the lowercase `true`/`false` strings the pipeline emits."""
    return str(value).strip().lower() == "true"


def as_date(value: str):
    """Parse an ISO date."""
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def as_optional_date(value: str | None):
    """Parse an ISO date, returning None for a missing or blank value."""
    if not value:
        return None
    return as_date(value)


def split_touchpoint(key: str) -> tuple[str, str, str, str, str]:
    """Split a five-segment key, padding a four-segment key with UNSPECIFIED."""
    parts = key.split(":")
    while len(parts) < 5:
        parts.append("UNSPECIFIED")
    return tuple(parts[:5])  # type: ignore[return-value]


class Importer:
    """Loads every artifact into the database within one transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.touchpoints: dict[str, Touchpoint] = {}
        self.campaigns: dict[str, Campaign] = {}
        self.counts: dict[str, int] = {}

    def record(self, table: str, count: int) -> None:
        self.counts[table] = self.counts.get(table, 0) + count

    # -- Layer 1 ----------------------------------------------------------

    def touchpoint(self, key: str, cost_type: str | None = None) -> Touchpoint:
        """Return the Touchpoint for a key, creating it on first sight."""
        existing = self.touchpoints.get(key)
        if existing is not None:
            if cost_type and not existing.cost_type:
                existing.cost_type = cost_type
            return existing

        ad_product, fmt, placement, creative, interaction = split_touchpoint(key)
        row = Touchpoint(
            touchpoint_key=key,
            ad_product=ad_product,
            format=fmt,
            placement=placement,
            creative=creative,
            interaction_type=interaction,
            cost_type=cost_type or None,
        )
        self.session.add(row)
        self.touchpoints[key] = row
        return row

    def import_entities(self, request: dict, pool: dict) -> None:
        """Create the advertiser, group, campaigns, and candidate counts."""
        group_data = request["campaign_group"]
        advertiser = Advertiser(
            advertiser_id=group_data["advertiser_id"],
            marketplace=group_data["marketplace"],
            currency=group_data.get("currency", "USD"),
        )
        self.session.add(advertiser)
        self.record("advertiser", 1)

        group = CampaignGroup(
            campaign_group_id=group_data["campaign_group_id"],
            group_name=group_data["group_name"],
            platform=group_data.get("platform", "AMAZON"),
            total_daily_budget=float(group_data.get("total_daily_budget", 0.0)),
            currency=group_data.get("currency", "USD"),
            sample_version=str(request.get("sample_version", "")) or None,
            candidate_pool_id=request.get("candidate_pool_id"),
            mta_batch_id=request.get("mta_batch_id"),
            advertiser=advertiser,
        )
        self.session.add(group)
        self.record("campaign_group", 1)

        for entry in request.get("campaigns", []):
            campaign = Campaign(
                campaign_id=entry["campaign_id"],
                campaign_name=entry["campaign_name"],
                ad_product=entry["ad_product"],
                status=entry.get("status", "enabled"),
                campaign_group=group,
            )
            self.session.add(campaign)
            self.campaigns[campaign.campaign_id] = campaign
        self.record("campaign", len(self.campaigns))

        pool_id = pool.get("candidate_pool_id", "")
        usage_policy = pool.get("candidate_usage_policy")
        pool_version = str(pool.get("sample_version", "")) or None
        candidates = 0
        for entry in pool.get("campaign_candidate_counts", []):
            campaign = self.campaigns.get(entry["campaign_id"])
            if campaign is None:
                continue
            for key, value in entry.items():
                if not key.startswith("eligible_"):
                    continue
                self.session.add(
                    TargetingCandidate(
                        candidate_pool_id=pool_id,
                        candidate_kind=key,
                        eligible_count=int(value),
                        candidate_usage_policy=usage_policy,
                        sample_version=pool_version,
                        campaign=campaign,
                    )
                )
                candidates += 1
        self.record("targeting_candidate", candidates)

    # -- Layer 2 ----------------------------------------------------------

    def import_ads_daily(self) -> None:
        rows = read_rows(config.SIMULATED_DIR / "amazon_ads_report_sample.csv")
        for row in rows:
            key = row["normalizedTouchpoint"]
            self.session.add(
                AdsDailyPerformance(
                    report_date=as_date(row["reportDate"]),
                    marketplace=row["marketplace"],
                    account_id=row["accountId"],
                    currency=row.get("currencyCode", "USD"),
                    impressions=as_int(row.get("impressions")),
                    clicks=as_int(row.get("clicks")),
                    cost=as_float(row.get("cost")) or 0.0,
                    purchases=as_int(row.get("purchases")),
                    sales=as_float(row.get("sales")) or 0.0,
                    touchpoint=self.touchpoint(key, row.get("cost_type")),
                )
            )
        self.record("ads_daily_performance", len(rows))

    def import_paths(self) -> None:
        rows = read_rows(config.SIMULATED_DIR / "amc_mta_path_report_raw_sample.csv")
        for row in rows:
            path = row["path"]
            self.session.add(
                PathReport(
                    report_start_date=as_date(row["report_start_date"]),
                    report_end_date=as_date(row["report_end_date"]),
                    marketplace=row["marketplace"],
                    advertiser_id=row["advertiser_id"],
                    path=path,
                    path_length=path.count(">") + 1,
                    users=as_int(row.get("users")),
                    converted_users=as_int(row.get("converted_users")),
                    purchase_count=as_int(row.get("purchase_count")),
                    revenue=as_float(row.get("revenue")) or 0.0,
                )
            )
        self.record("path_report", len(rows))

    def import_bridge(self) -> None:
        rows = read_rows(
            config.SIMULATED_DIR / "amc_touchpoint_entity_aggregate_sample.csv"
        )
        seen_ad_groups: set[str] = set()
        for row in rows:
            ad_group_id = row["ad_group_id"]
            campaign = self.campaigns.get(row["campaign_id"])
            if campaign is not None and ad_group_id not in seen_ad_groups:
                self.session.add(AdGroup(ad_group_id=ad_group_id, campaign=campaign))
                seen_ad_groups.add(ad_group_id)

            self.session.add(
                TouchpointEntityBridge(
                    report_start_date=as_date(row["report_start_date"]),
                    report_end_date=as_date(row["report_end_date"]),
                    marketplace=row["marketplace"],
                    advertiser_id=row["advertiser_id"],
                    campaign_group_id=row["campaign_group_id"],
                    campaign_id=row["campaign_id"],
                    ad_group_id=ad_group_id,
                    keyword_id=row.get("keyword_id") or None,
                    keyword_text=row.get("keyword_text") or None,
                    match_type=row.get("match_type") or None,
                    target_id=row.get("target_id") or None,
                    audience_id=row.get("audience_id") or None,
                    advertised_asin=row.get("advertised_asin") or None,
                    sku_id=row.get("sku_id") or None,
                    unique_users=as_int(row.get("unique_users")),
                    journey_count=as_int(row.get("journey_count")),
                    impressions=as_int(row.get("impressions")),
                    clicks=as_int(row.get("clicks")),
                    cost=as_float(row.get("cost")) or 0.0,
                    assisted_converted_users=as_float(
                        row.get("assisted_converted_users")
                    )
                    or 0.0,
                    assisted_purchase_count=as_float(row.get("assisted_purchase_count"))
                    or 0.0,
                    assisted_revenue=as_float(row.get("assisted_revenue")) or 0.0,
                    reported_purchases=as_int(row.get("reported_purchases")),
                    reported_sales=as_float(row.get("reported_sales")) or 0.0,
                    touchpoint=self.touchpoint(row["touchpoint"]),
                )
            )
        self.record("ad_group", len(seen_ad_groups))
        self.record("touchpoint_entity_bridge", len(rows))

    def import_events(self, limit: int | None) -> None:
        rows = read_rows(config.SIMULATED_DIR / "synthetic_user_events_sample.csv")
        if limit is not None:
            rows = rows[:limit]
        for row in rows:
            interaction = row.get("interaction_type") or ""
            key = None
            if row.get("ad_product") and interaction:
                key = ":".join(
                    [
                        row["ad_product"],
                        row.get("format") or "UNSPECIFIED",
                        row.get("placement") or "UNSPECIFIED",
                        row.get("creative") or "UNSPECIFIED",
                        interaction,
                    ]
                )
            self.session.add(
                SyntheticUserEvent(
                    synthetic_user_id=row["synthetic_user_id"],
                    journey_instance_id=row["journey_instance_id"],
                    event_id=row["event_id"],
                    event_type=row["event_type"],
                    event_time=datetime.fromisoformat(row["event_time"]),
                    touch_position=as_int(row.get("touch_position")) or None,
                    marketplace=row["marketplace"],
                    advertiser_id=row["advertiser_id"],
                    campaign_id=row.get("campaign_id") or None,
                    ad_group_id=row.get("ad_group_id") or None,
                    cost=as_float(row.get("cost")) or 0.0,
                    converted=as_bool(row.get("converted")),
                    purchase_count=as_int(row.get("purchase_count")),
                    revenue=as_float(row.get("revenue")) or 0.0,
                    touchpoint=self.touchpoint(key) if key else None,
                )
            )
        self.record("synthetic_user_event", len(rows))

    # -- Layer 3 ----------------------------------------------------------

    def import_model_output(self, request: dict) -> None:
        summary_rows = read_rows(
            config.ATTRIBUTION_OUTPUT_DIR / "amc_mta_model_comparison_summary.csv"
        )
        first = summary_rows[0]
        run = AttributionRun(
            batch_id=request.get("mta_batch_id", "mta_run"),
            report_start_date=as_date(first["report_start_date"]),
            report_end_date=as_date(first["report_end_date"]),
            marketplace=request["campaign_group"]["marketplace"],
            advertiser_id=request["campaign_group"]["advertiser_id"],
            max_touchpoint_gap_days=as_int(first.get("max_touchpoint_gap_days")) or 14,
            imported_at=datetime.now(),
        )
        self.session.add(run)
        self.record("attribution_run", 1)

        results = 0
        for model in ("markov", "shapley"):
            for row in read_rows(
                config.ATTRIBUTION_OUTPUT_DIR / f"amc_{model}_attribution_results.csv"
            ):
                self.session.add(
                    AttributionResult(
                        attribution_model=row["attribution_model"],
                        converted_user_share=as_float(row["converted_user_share"]) or 0.0,
                        purchase_count_share=as_float(row["purchase_count_share"]) or 0.0,
                        revenue_share=as_float(row["revenue_share"]) or 0.0,
                        attributed_converted_users=as_float(
                            row["attributed_converted_users"]
                        )
                        or 0.0,
                        attributed_purchase_count=as_float(
                            row["attributed_purchase_count"]
                        )
                        or 0.0,
                        attributed_revenue=as_float(row["attributed_revenue"]) or 0.0,
                        impressions=as_int(row.get("impressions")),
                        clicks=as_int(row.get("clicks")),
                        cost=as_float(row.get("cost")) or 0.0,
                        reported_purchases=as_int(row.get("reported_purchases")),
                        reported_sales=as_float(row.get("reported_sales")) or 0.0,
                        roas=as_float(row.get("roas")),
                        roi=as_float(row.get("roi")),
                        cpa=as_float(row.get("cpa")),
                        cost_per_converted_user=as_float(
                            row.get("cost_per_converted_user")
                        ),
                        run=run,
                        touchpoint=self.touchpoint(row["touchpoint"]),
                    )
                )
                results += 1
        self.record("attribution_result", results)

        comparisons = read_rows(
            config.ATTRIBUTION_OUTPUT_DIR / "amc_mta_model_comparison_touchpoints.csv"
        )
        for row in comparisons:
            self.session.add(
                ModelComparisonTouchpoint(
                    outcome=row["outcome"],
                    markov_share=as_float(row["markov_share"]) or 0.0,
                    shapley_share=as_float(row["shapley_share"]) or 0.0,
                    gap_pp=as_float(row["gap_pp"]) or 0.0,
                    relative_gap=as_float(row.get("relative_gap")),
                    raw_unique_paths=as_int(row.get("raw_unique_paths")),
                    raw_converted_users=as_int(row.get("raw_converted_users")),
                    raw_purchase_count=as_int(row.get("raw_purchase_count")),
                    calculation_valid=as_bool(row.get("calculation_valid")),
                    data_support_sufficient=as_bool(row.get("data_support_sufficient")),
                    models_consistent=as_bool(row.get("models_consistent")),
                    reliability_status=row["reliability_status"],
                    reliability_reason=row["reliability_reason"],
                    run=run,
                    touchpoint=self.touchpoint(row["touchpoint"]),
                )
            )
        self.record("model_comparison_touchpoint", len(comparisons))

        for row in summary_rows:
            self.session.add(
                ModelComparisonSummary(
                    outcome=row["outcome"],
                    touchpoint_count=as_int(row.get("touchpoint_count")),
                    tvd=as_float(row.get("tvd")) or 0.0,
                    spearman_rho=as_float(row.get("spearman_rho")),
                    top_k_overlap_rate=as_float(row.get("top_k_overlap_rate")),
                    calculation_valid=as_bool(row.get("calculation_valid")),
                    data_support_sufficient=as_bool(row.get("data_support_sufficient")),
                    models_consistent=as_bool(row.get("models_consistent")),
                    reliability_status=row["reliability_status"],
                    reliability_reason=row["reliability_reason"],
                    run=run,
                )
            )
        self.record("model_comparison_summary", len(summary_rows))

        recommended = read_rows(
            config.ATTRIBUTION_OUTPUT_DIR / "amc_mta_recommended_attribution.csv"
        )
        for row in recommended:
            self.session.add(
                RecommendedAttribution(
                    outcome=row["outcome"],
                    official_model=row["official_model"],
                    official_share=as_float(row.get("official_share")),
                    recommended_value=row.get("recommended_value", ""),
                    benchmark_model=row["benchmark_model"],
                    benchmark_share=as_float(row.get("benchmark_share")),
                    gap_pp=as_float(row.get("gap_pp")),
                    relative_gap=as_float(row.get("relative_gap")),
                    calculation_valid=as_bool(row.get("calculation_valid")),
                    data_support_sufficient=as_bool(row.get("data_support_sufficient")),
                    models_consistent=as_bool(row.get("models_consistent")),
                    reliability_status=row["reliability_status"],
                    reliability_reason=row["reliability_reason"],
                    run=run,
                    touchpoint=self.touchpoint(row["touchpoint"]),
                )
            )
        self.record("recommended_attribution", len(recommended))

    # -- Layer 4 ----------------------------------------------------------

    def import_budget(self, document: dict) -> None:
        derivation = document.get("budget_derivation", {})
        weights = derivation.get("outcome_weights", {})
        snapshot = document.get("mta_source_snapshot", {})
        run = BudgetRecommendationRun(
            schema_version=document.get("schema_version", ""),
            campaign_group_id=document.get("campaign_group_id", ""),
            candidate_pool_id=document.get("candidate_pool_id", ""),
            mta_batch_id=document.get("mta_batch_id", ""),
            source_report_start_date=as_optional_date(
                snapshot.get("report_start_date")
            ),
            source_report_end_date=as_optional_date(snapshot.get("report_end_date")),
            source_marketplace=snapshot.get("marketplace"),
            source_advertiser_id=snapshot.get("advertiser_id"),
            source_attribution_sha256=snapshot.get("attribution_sha256"),
            source_entity_sha256=snapshot.get("entity_sha256"),
            recommendation_type=document.get("recommendation_type", ""),
            handoff_status=document.get("handoff_status", ""),
            is_optimized=bool(document.get("is_optimized", False)),
            formula_version=derivation.get("formula_version", ""),
            normalization_universe=derivation.get("normalization_universe", ""),
            weight_converted_users=float(weights.get("converted_users", 0.0)),
            weight_purchase_count=float(weights.get("purchase_count", 0.0)),
            weight_revenue=float(weights.get("revenue", 0.0)),
            budget_seed_total=float(document.get("budget_seed_total", 0.0)),
            imported_at=datetime.now(),
        )
        self.session.add(run)
        self.record("budget_recommendation_run", 1)

        slots = 0
        campaigns = document.get("campaigns", [])
        for entry in campaigns:
            rationale = entry.get("count_rationale", {})
            contributions = entry.get("outcome_contributions", {})
            bridge = entry.get("bridge_summary", {})
            recommendation = CampaignBudgetRecommendation(
                campaign_id=entry["campaign_id"],
                recommended_ad_group_count=int(
                    entry.get("recommended_ad_group_count", 0)
                ),
                score_converted_users=float(contributions.get("converted_users", 0.0)),
                score_purchase_count=float(contributions.get("purchase_count", 0.0)),
                score_revenue=float(contributions.get("revenue", 0.0)),
                campaign_mta_score=float(entry.get("campaign_mta_score", 0.0)),
                budget_seed_share=float(entry.get("budget_seed_share", 0.0)),
                campaign_budget_seed=float(entry.get("campaign_budget_seed", 0.0)),
                minimum_required_daily_budget=float(
                    entry.get("minimum_required_daily_budget", 0.0)
                ),
                execution_status=entry.get("execution_status", ""),
                count_formula_version=rationale.get("count_formula_version"),
                capacity_required_count=int(
                    rationale.get("capacity_required_count", 0)
                ),
                bridge_historical_ad_group_count=int(
                    bridge.get("historical_ad_group_count", 0)
                ),
                bridge_touchpoint_count=int(bridge.get("touchpoint_count", 0)),
                bridge_fallback_used=bool(bridge.get("fallback_used", False)),
                run=run,
            )
            self.session.add(recommendation)

            for slot in entry.get("recommended_ad_groups", []):
                self.session.add(
                    AdGroupBudgetSlot(
                        ad_group_slot_id=slot["ad_group_slot_id"],
                        allocation_basis=slot.get("allocation_basis", ""),
                        budget_seed_share=float(slot.get("budget_seed_share", 0.0)),
                        initial_daily_budget=float(
                            slot.get("initial_daily_budget", 0.0)
                        ),
                        campaign_recommendation=recommendation,
                    )
                )
                slots += 1
        self.record("campaign_budget_recommendation", len(campaigns))
        self.record("ad_group_budget_slot", slots)


def existing_row_count(engine) -> int:
    """Return the number of attribution rows already present, or 0 if no schema."""
    try:
        with Session(engine) as session:
            return session.scalar(select(func.count()).select_from(AttributionResult)) or 0
    except Exception:  # noqa: BLE001 - table absent means an empty database
        return 0


def ensure_schema(engine, schema: str) -> bool:
    """Create the target schema when it is absent. Returns whether it was created.

    The name is quoted as an identifier rather than bound as a parameter,
    because it names an object. `config.valid_schema_name()` has already
    refused anything that is not a plain identifier, and the doubled quote
    handles the one character that could still close it early.
    """
    quoted = '"' + schema.replace('"', '""') + '"'
    with engine.begin() as connection:
        existing = connection.execute(
            text("select 1 from information_schema.schemata where schema_name = :name"),
            {"name": schema},
        ).scalar()
        if existing:
            return False
        connection.execute(text(f"create schema {quoted}"))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop and recreate every table before importing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be imported without connecting to write.",
    )
    parser.add_argument(
        "--full-events",
        action="store_true",
        help=f"Import every synthetic event rather than the first {DEFAULT_EVENT_LIMIT}.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help=(
            "Schema to create the tables in. Defaults to PG_SCHEMA from .env, "
            "and to 'public' when that is unset."
        ),
    )
    args = parser.parse_args()

    request_path = config.STRATEGY_INPUT_DIR / "strategy_request.json"
    pool_path = config.STRATEGY_INPUT_DIR / "candidate_pool.json"
    budget_path = config.STRATEGY_OUTPUT_DIR / "initial_budget_recommendation.json"
    for path in (request_path, pool_path, budget_path):
        if not path.exists():
            print(f"INVALID: required artifact missing: {path}", file=sys.stderr)
            return 1

    request = json.loads(request_path.read_text(encoding="utf-8"))
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    budget = json.loads(budget_path.read_text(encoding="utf-8"))

    if args.dry_run:
        print("Dry run: no connection opened.")
        for path in (
            config.SIMULATED_DIR / "amazon_ads_report_sample.csv",
            config.SIMULATED_DIR / "amc_mta_path_report_raw_sample.csv",
            config.SIMULATED_DIR / "amc_touchpoint_entity_aggregate_sample.csv",
            config.ATTRIBUTION_OUTPUT_DIR / "amc_mta_recommended_attribution.csv",
        ):
            print(f"  {path.name}: {len(read_rows(path))} rows")
        return 0

    settings = config.database_settings()
    if args.schema:
        settings = replace(settings, schema=args.schema.strip())
    if not config.valid_schema_name(settings.schema):
        print(
            f"INVALID: {settings.schema!r} is not a valid PostgreSQL schema name.",
            file=sys.stderr,
        )
        return 1

    print(f"Target: {settings.safe_summary()}")
    try:
        connect_args = settings.connect_args()
    except ValueError as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    engine = create_engine(settings.url(), connect_args=connect_args)

    # The schema has to exist before `search_path` can resolve to it, and a
    # connection carrying a path to a missing schema reports every table as
    # absent rather than saying the schema is not there. Creating it here is
    # what makes `--schema` able to build a new mirror rather than only write
    # into one that was prepared by hand.
    if settings.schema != config.DEFAULT_SCHEMA:
        created = ensure_schema(engine, settings.schema)
        print(f"Schema {settings.schema}: {'created' if created else 'already present'}")

    present = existing_row_count(engine)
    if present and not args.replace:
        print(
            f"INVALID: database already holds {present} attribution rows. "
            "Re-run with --replace to drop and rebuild every table.",
            file=sys.stderr,
        )
        return 1

    if args.replace:
        print("Dropping existing tables ...")
        Base.metadata.drop_all(engine)

    print("Creating tables ...")
    Base.metadata.create_all(engine)

    limit = None if args.full_events else DEFAULT_EVENT_LIMIT
    with Session(engine) as session:
        importer = Importer(session)
        importer.import_entities(request, pool)
        importer.import_ads_daily()
        importer.import_paths()
        importer.import_bridge()
        importer.import_events(limit)
        importer.import_model_output(request)
        importer.import_budget(budget)
        importer.record("touchpoint", len(importer.touchpoints))
        session.commit()

    print("\nImported:")
    for table in sorted(importer.counts):
        print(f"  {table:<34} {importer.counts[table]:>7}")
    print("\nSet DATABASE=true in .env to read the dashboard from this database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
