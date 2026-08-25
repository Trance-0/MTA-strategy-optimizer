"""Model output: what the attribution models concluded.

Four snapshot keys come from here. Each is read either from the four
attribution result files the pipeline publishes, or from the four tables
`script/import_to_database.py` loads them into, and both produce identical
rows.

The database statements are built from `dashboard/models.py` columns rather
than from statement text, so a renamed column fails at import rather than at
request time, and the schema keeps one definition.

Data flow:
    modules/mta_attribution/outputs/attribution/&#42;.csv  -.
                                                          +-> here -> /api/dashboard
    attribution_result, model_comparison_&#42;, recommended -'
"""

from __future__ import annotations

from sqlalchemy import select

from backend.config import ATTRIBUTION_OUTPUT_DIR, use_database
from backend.database import orm_rows
from backend.repository.coercion import (
    boolean,
    dates,
    numeric,
    project,
    read_csv,
    split_touchpoint,
)
from dashboard.models import (
    AttributionResult,
    AttributionRun,
    ModelComparisonSummary,
    ModelComparisonTouchpoint,
    RecommendedAttribution,
    Touchpoint,
)

ATTRIBUTION_FIELDS: tuple[str, ...] = (
    "attribution_model",
    "touchpoint",
    "ad_product",
    "format",
    "placement",
    "creative",
    "interaction_type",
    "converted_user_share",
    "purchase_count_share",
    "revenue_share",
    "attributed_converted_users",
    "attributed_purchase_count",
    "attributed_revenue",
    "impressions",
    "clicks",
    "cost",
    "reported_purchases",
    "reported_sales",
    "roas",
    "roi",
    "cpa",
    "cost_per_converted_user",
)

#: Everything from `converted_user_share` onward is numeric.
ATTRIBUTION_NUMERIC = ATTRIBUTION_FIELDS[7:]


def attribution_results() -> list[dict]:
    """Per-model attributed outcomes, cost, and efficiency for each touchpoint."""
    if use_database():
        statement = (
            select(
                AttributionResult.attribution_model,
                Touchpoint.touchpoint_key.label("touchpoint"),
                Touchpoint.interaction_type,
                Touchpoint.ad_product,
                Touchpoint.format,
                Touchpoint.placement,
                Touchpoint.creative,
                AttributionResult.converted_user_share,
                AttributionResult.purchase_count_share,
                AttributionResult.revenue_share,
                AttributionResult.attributed_converted_users,
                AttributionResult.attributed_purchase_count,
                AttributionResult.attributed_revenue,
                AttributionResult.impressions,
                AttributionResult.clicks,
                AttributionResult.cost,
                AttributionResult.reported_purchases,
                AttributionResult.reported_sales,
                AttributionResult.roas,
                AttributionResult.roi,
                AttributionResult.cpa,
                AttributionResult.cost_per_converted_user,
            )
            .join(Touchpoint, Touchpoint.id == AttributionResult.touchpoint_pk)
            .order_by(AttributionResult.attribution_model, Touchpoint.touchpoint_key)
        )
        rows = orm_rows(statement)
    else:
        rows = []
        for model in ("markov", "shapley"):
            rows.extend(
                read_csv(ATTRIBUTION_OUTPUT_DIR / f"amc_{model}_attribution_results.csv")
            )
        split_touchpoint(rows)
    return project(numeric(rows, ATTRIBUTION_NUMERIC), ATTRIBUTION_FIELDS)


COMPARISON_FIELDS: tuple[str, ...] = (
    "touchpoint",
    "outcome",
    "ad_product",
    "format",
    "placement",
    "creative",
    "interaction_type",
    "markov_share",
    "shapley_share",
    "gap_pp",
    "relative_gap",
    "raw_unique_paths",
    "raw_converted_users",
    "raw_purchase_count",
    "calculation_valid",
    "data_support_sufficient",
    "models_consistent",
    "reliability_status",
    "reliability_reason",
)

COMPARISON_NUMERIC = (
    "markov_share",
    "shapley_share",
    "gap_pp",
    "relative_gap",
    "raw_unique_paths",
    "raw_converted_users",
    "raw_purchase_count",
)


def comparison_touchpoints() -> list[dict]:
    """Markov against Shapley per touchpoint and outcome, with reliability."""
    if use_database():
        statement = (
            select(
                Touchpoint.touchpoint_key.label("touchpoint"),
                ModelComparisonTouchpoint.outcome,
                ModelComparisonTouchpoint.markov_share,
                ModelComparisonTouchpoint.shapley_share,
                ModelComparisonTouchpoint.gap_pp,
                ModelComparisonTouchpoint.relative_gap,
                ModelComparisonTouchpoint.raw_unique_paths,
                ModelComparisonTouchpoint.raw_converted_users,
                ModelComparisonTouchpoint.raw_purchase_count,
                ModelComparisonTouchpoint.calculation_valid,
                ModelComparisonTouchpoint.data_support_sufficient,
                ModelComparisonTouchpoint.models_consistent,
                ModelComparisonTouchpoint.reliability_status,
                ModelComparisonTouchpoint.reliability_reason,
                Touchpoint.ad_product,
                Touchpoint.format,
                Touchpoint.placement,
                Touchpoint.creative,
                Touchpoint.interaction_type,
            )
            .join(Touchpoint, Touchpoint.id == ModelComparisonTouchpoint.touchpoint_pk)
            .order_by(ModelComparisonTouchpoint.outcome, Touchpoint.touchpoint_key)
        )
        rows = orm_rows(statement)
    else:
        rows = read_csv(
            ATTRIBUTION_OUTPUT_DIR / "amc_mta_model_comparison_touchpoints.csv"
        )
        split_touchpoint(rows)
    numeric(rows, COMPARISON_NUMERIC)
    return project(boolean(rows), COMPARISON_FIELDS)


SUMMARY_FIELDS: tuple[str, ...] = (
    "outcome",
    "report_start_date",
    "report_end_date",
    "max_touchpoint_gap_days",
    "touchpoint_count",
    "tvd",
    "spearman_rho",
    "top_k_overlap_rate",
    "calculation_valid",
    "data_support_sufficient",
    "models_consistent",
    "reliability_status",
    "reliability_reason",
)

SUMMARY_NUMERIC = (
    "touchpoint_count",
    "tvd",
    "spearman_rho",
    "top_k_overlap_rate",
    "max_touchpoint_gap_days",
)


def comparison_summary() -> list[dict]:
    """One diagnostic row per outcome: TVD, Spearman, and Top-K overlap."""
    if use_database():
        statement = (
            select(
                ModelComparisonSummary.outcome,
                AttributionRun.report_start_date,
                AttributionRun.report_end_date,
                AttributionRun.max_touchpoint_gap_days,
                ModelComparisonSummary.touchpoint_count,
                ModelComparisonSummary.tvd,
                ModelComparisonSummary.spearman_rho,
                ModelComparisonSummary.top_k_overlap_rate,
                ModelComparisonSummary.calculation_valid,
                ModelComparisonSummary.data_support_sufficient,
                ModelComparisonSummary.models_consistent,
                ModelComparisonSummary.reliability_status,
                ModelComparisonSummary.reliability_reason,
            )
            .join(AttributionRun, AttributionRun.id == ModelComparisonSummary.run_pk)
            .order_by(ModelComparisonSummary.outcome)
        )
        rows = orm_rows(statement)
    else:
        rows = read_csv(
            ATTRIBUTION_OUTPUT_DIR / "amc_mta_model_comparison_summary.csv"
        )
    numeric(rows, SUMMARY_NUMERIC)
    return project(boolean(dates(rows)), SUMMARY_FIELDS)


RECOMMENDED_FIELDS: tuple[str, ...] = (
    "touchpoint",
    "outcome",
    "ad_product",
    "format",
    "placement",
    "creative",
    "interaction_type",
    "official_model",
    "official_share",
    "recommended_value",
    "benchmark_model",
    "benchmark_share",
    "gap_pp",
    "relative_gap",
    "calculation_valid",
    "data_support_sufficient",
    "models_consistent",
    "reliability_status",
    "reliability_reason",
)

RECOMMENDED_NUMERIC = ("official_share", "benchmark_share", "gap_pp", "relative_gap")


def recommended_attribution() -> list[dict]:
    """The governed view: official share, benchmark, and recommended value."""
    if use_database():
        statement = (
            select(
                Touchpoint.touchpoint_key.label("touchpoint"),
                RecommendedAttribution.outcome,
                Touchpoint.interaction_type,
                RecommendedAttribution.official_model,
                RecommendedAttribution.official_share,
                RecommendedAttribution.recommended_value,
                RecommendedAttribution.benchmark_model,
                RecommendedAttribution.benchmark_share,
                RecommendedAttribution.gap_pp,
                RecommendedAttribution.relative_gap,
                RecommendedAttribution.calculation_valid,
                RecommendedAttribution.data_support_sufficient,
                RecommendedAttribution.models_consistent,
                RecommendedAttribution.reliability_status,
                RecommendedAttribution.reliability_reason,
                Touchpoint.ad_product,
                Touchpoint.format,
                Touchpoint.placement,
                Touchpoint.creative,
            )
            .join(Touchpoint, Touchpoint.id == RecommendedAttribution.touchpoint_pk)
            .order_by(RecommendedAttribution.outcome, Touchpoint.touchpoint_key)
        )
        rows = orm_rows(statement)
    else:
        rows = read_csv(
            ATTRIBUTION_OUTPUT_DIR / "amc_mta_recommended_attribution.csv"
        )
        split_touchpoint(rows)
    numeric(rows, RECOMMENDED_NUMERIC)
    return project(boolean(rows), RECOMMENDED_FIELDS)
