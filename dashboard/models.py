"""Object-relational data model for the dashboard database.

This module is the single definition of the database schema. It sits at the
edge of the project: the attribution, standard, and strategy modules never
import it, because they read and write CSV and JSON files directly. The
dashboard uses these classes only when `DATABASE=true`; when `DATABASE=false`
the same information is read from those files instead.

Data flow:
    modules/*/data/simulated/*.csv   -.
    modules/*/outputs/**            --+-> script/import_to_database.py
    modules/*/data/simulated/*.json  -'        |
                                               v
                                        these tables
                                               |
                                               v
                                  dashboard/data_source.py -> views

The required classes are grouped into four layers, mirroring the project's own stages:

1. Entity        — the advertising hierarchy and the touchpoint vocabulary.
2. History       — what was observed: spend, paths, and events.
3. Model output  — what the attribution models concluded.
4. Strategy      — what the budget initializer recommended.

``ModelArtifact`` uses separate metadata because it is optional storage created
only by the dashboard's explicit validated-artifact import action.

Every table carries the report window and marketplace it belongs to, so a
second run over a different window can be loaded alongside the first without
overwriting it.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for every dashboard table."""


class ArtifactBase(DeclarativeBase):
    """Separate metadata for optional, explicitly imported artifact storage."""


# ---------------------------------------------------------------------------
# Layer 1 — Entity
# ---------------------------------------------------------------------------


class Advertiser(Base):
    """One advertising account in one marketplace.

    The root of the hierarchy. Every other entity row ultimately belongs to an
    advertiser, and one attribution run covers exactly one advertiser.
    """

    __tablename__ = "advertiser"

    id: Mapped[int] = mapped_column(primary_key=True)
    advertiser_id: Mapped[str] = mapped_column(String(64), unique=True)
    marketplace: Mapped[str] = mapped_column(String(8))
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    campaign_groups: Mapped[list["CampaignGroup"]] = relationship(
        back_populates="advertiser"
    )


class CampaignGroup(Base):
    """The top level of the advertising hierarchy.

    A Campaign Group holds one total daily budget, which the strategy module
    divides among its Campaigns.
    """

    __tablename__ = "campaign_group"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_group_id: Mapped[str] = mapped_column(String(64), unique=True)
    group_name: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(32), default="AMAZON")
    total_daily_budget: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    #: Identifiers of the strategy request this group was read from: which
    #: sample it came from, which candidate pool it was paired with, and which
    #: attribution batch supplied its evidence.
    sample_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    candidate_pool_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mta_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    advertiser_pk: Mapped[int] = mapped_column(ForeignKey("advertiser.id"))
    advertiser: Mapped[Advertiser] = relationship(back_populates="campaign_groups")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="campaign_group")


class Campaign(Base):
    """One Campaign, carrying exactly one ad product.

    Because a Campaign has a single `ad_product`, the ad product is the level
    at which attribution evidence is bridged into budget shares.
    """

    __tablename__ = "campaign"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), unique=True)
    campaign_name: Mapped[str] = mapped_column(String(255))
    ad_product: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="enabled")

    campaign_group_pk: Mapped[int] = mapped_column(ForeignKey("campaign_group.id"))
    campaign_group: Mapped[CampaignGroup] = relationship(back_populates="campaigns")
    ad_groups: Mapped[list["AdGroup"]] = relationship(back_populates="campaign")


class AdGroup(Base):
    """One Ad Group: the level at which budget is actually set.

    Historical Ad Groups appear in the entity bridge. New Ad Groups proposed by
    the strategy module are anonymous slots and live in `ad_group_budget_slot`
    instead, because they have no history yet.
    """

    __tablename__ = "ad_group"

    id: Mapped[int] = mapped_column(primary_key=True)
    ad_group_id: Mapped[str] = mapped_column(String(64), unique=True)

    campaign_pk: Mapped[int] = mapped_column(ForeignKey("campaign.id"))
    campaign: Mapped[Campaign] = relationship(back_populates="ad_groups")


class Touchpoint(Base):
    """The five-segment interaction key.

    `touchpoint_key` is the canonical
    `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` string. The
    segments are stored separately as well so the dashboard can group by any
    one of them without parsing the key.
    """

    __tablename__ = "touchpoint"

    id: Mapped[int] = mapped_column(primary_key=True)
    touchpoint_key: Mapped[str] = mapped_column(String(255), unique=True)
    ad_product: Mapped[str] = mapped_column(String(32))
    format: Mapped[str] = mapped_column(String(32))
    placement: Mapped[str] = mapped_column(String(32))
    creative: Mapped[str] = mapped_column(String(32))
    interaction_type: Mapped[str] = mapped_column(String(16))
    cost_type: Mapped[str | None] = mapped_column(String(16), nullable=True)


class TargetingCandidate(Base):
    """An eligible targeting object a new Ad Group could be built around.

    One row per Campaign per candidate kind. These counts drive the capacity
    calculation that decides how many new Ad Groups a Campaign can support.
    """

    __tablename__ = "targeting_candidate"
    __table_args__ = (UniqueConstraint("campaign_pk", "candidate_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_pool_id: Mapped[str] = mapped_column(String(64))
    candidate_kind: Mapped[str] = mapped_column(String(32))
    eligible_count: Mapped[int] = mapped_column(Integer, default=0)

    #: How the strategy module is permitted to consume the pool, carried from
    #: the source artifact so the dashboard states the policy it operated under
    #: rather than assuming one.
    candidate_usage_policy: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    sample_version: Mapped[str | None] = mapped_column(String(16), nullable=True)

    campaign_pk: Mapped[int] = mapped_column(ForeignKey("campaign.id"))
    campaign: Mapped[Campaign] = relationship()


# ---------------------------------------------------------------------------
# Layer 2 — History
# ---------------------------------------------------------------------------


class AdsDailyPerformance(Base):
    """One day of platform-reported performance for one touchpoint.

    Source of spend and of the report window itself: the pipeline infers the
    window from the earliest and latest `report_date` present here rather than
    from configuration. Cost per click belongs only to CLICK rows and cost per
    mille only to IMPRESSION rows, so spend is never double counted.
    """

    __tablename__ = "ads_daily_performance"
    __table_args__ = (UniqueConstraint("report_date", "touchpoint_pk"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    marketplace: Mapped[str] = mapped_column(String(8))
    account_id: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    purchases: Mapped[int] = mapped_column(Integer, default=0)
    sales: Mapped[float] = mapped_column(Float, default=0.0)

    touchpoint_pk: Mapped[int] = mapped_column(ForeignKey("touchpoint.id"))
    touchpoint: Mapped[Touchpoint] = relationship()


class PathReport(Base):
    """One anonymous aggregated conversion path.

    `path` is a `>`-joined sequence of five-segment touchpoints. Rows are
    already aggregated to satisfy privacy thresholds; no user-level detail is
    stored or implied.
    """

    __tablename__ = "path_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_start_date: Mapped[date] = mapped_column(Date)
    report_end_date: Mapped[date] = mapped_column(Date)
    marketplace: Mapped[str] = mapped_column(String(8))
    advertiser_id: Mapped[str] = mapped_column(String(64))

    path: Mapped[str] = mapped_column(Text)
    path_length: Mapped[int] = mapped_column(Integer, default=0)
    users: Mapped[int] = mapped_column(Integer, default=0)
    converted_users: Mapped[int] = mapped_column(Integer, default=0)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)


class TouchpointEntityBridge(Base):
    """Links a touchpoint to the Campaign and Ad Group that carried it.

    This is the join that lets touchpoint-level attribution become a
    Campaign-level budget share. The `assisted_*` columns are the weights the
    strategy module rolls up.
    """

    __tablename__ = "touchpoint_entity_bridge"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_start_date: Mapped[date] = mapped_column(Date)
    report_end_date: Mapped[date] = mapped_column(Date)
    marketplace: Mapped[str] = mapped_column(String(8))
    advertiser_id: Mapped[str] = mapped_column(String(64))

    campaign_group_id: Mapped[str] = mapped_column(String(64))
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    ad_group_id: Mapped[str] = mapped_column(String(64))
    keyword_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    keyword_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audience_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    advertised_asin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sku_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    unique_users: Mapped[int] = mapped_column(Integer, default=0)
    journey_count: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    assisted_converted_users: Mapped[float] = mapped_column(Float, default=0.0)
    assisted_purchase_count: Mapped[float] = mapped_column(Float, default=0.0)
    assisted_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    reported_purchases: Mapped[int] = mapped_column(Integer, default=0)
    reported_sales: Mapped[float] = mapped_column(Float, default=0.0)

    touchpoint_pk: Mapped[int] = mapped_column(ForeignKey("touchpoint.id"))
    touchpoint: Mapped[Touchpoint] = relationship()


class SyntheticUserEvent(Base):
    """One simulated advertising or purchase event.

    The single fact source every other simulated table is derived from. It is
    a local demonstration fixture and is not evidence that user-level events
    can be exported from a clean room. This is the largest table by far, so the
    dashboard samples or aggregates it rather than loading it whole.
    """

    __tablename__ = "synthetic_user_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    synthetic_user_id: Mapped[str] = mapped_column(String(64), index=True)
    journey_instance_id: Mapped[str] = mapped_column(String(64), index=True)
    event_id: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(32))
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    touch_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    marketplace: Mapped[str] = mapped_column(String(8))
    advertiser_id: Mapped[str] = mapped_column(String(64))
    campaign_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ad_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    cost: Mapped[float] = mapped_column(Float, default=0.0)
    converted: Mapped[bool] = mapped_column(Boolean, default=False)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)

    touchpoint_pk: Mapped[int | None] = mapped_column(
        ForeignKey("touchpoint.id"), nullable=True
    )
    touchpoint: Mapped[Touchpoint | None] = relationship()


# ---------------------------------------------------------------------------
# Layer 3 — Model output
# ---------------------------------------------------------------------------


class AttributionRun(Base):
    """One execution of the attribution pipeline over one window.

    Every model result, comparison, and recommendation row points back to a
    run, so two windows can coexist and be compared.
    """

    __tablename__ = "attribution_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), unique=True)
    report_start_date: Mapped[date] = mapped_column(Date)
    report_end_date: Mapped[date] = mapped_column(Date)
    marketplace: Mapped[str] = mapped_column(String(8))
    advertiser_id: Mapped[str] = mapped_column(String(64))
    max_touchpoint_gap_days: Mapped[int] = mapped_column(Integer, default=14)
    imported_at: Mapped[datetime] = mapped_column(DateTime)


class AttributionResult(Base):
    """One model's verdict for one touchpoint, with cost and efficiency.

    Mirrors the per-model result CSV. `attribution_model` is `markov` or
    `shapley`; the two are never averaged. Efficiency fields are null for
    zero-cost rows rather than zero.
    """

    __tablename__ = "attribution_result"
    __table_args__ = (UniqueConstraint("run_pk", "attribution_model", "touchpoint_pk"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attribution_model: Mapped[str] = mapped_column(String(32), index=True)

    converted_user_share: Mapped[float] = mapped_column(Float, default=0.0)
    purchase_count_share: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_share: Mapped[float] = mapped_column(Float, default=0.0)
    attributed_converted_users: Mapped[float] = mapped_column(Float, default=0.0)
    attributed_purchase_count: Mapped[float] = mapped_column(Float, default=0.0)
    attributed_revenue: Mapped[float] = mapped_column(Float, default=0.0)

    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    reported_purchases: Mapped[int] = mapped_column(Integer, default=0)
    reported_sales: Mapped[float] = mapped_column(Float, default=0.0)
    roas: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_converted_user: Mapped[float | None] = mapped_column(Float, nullable=True)

    run_pk: Mapped[int] = mapped_column(ForeignKey("attribution_run.id"))
    run: Mapped[AttributionRun] = relationship()
    touchpoint_pk: Mapped[int] = mapped_column(ForeignKey("touchpoint.id"))
    touchpoint: Mapped[Touchpoint] = relationship()


class ModelComparisonTouchpoint(Base):
    """Markov against Shapley for one touchpoint and one outcome.

    Carries the three reliability criteria. `reliability_status` is binary:
    all three must hold for RELIABLE.
    """

    __tablename__ = "model_comparison_touchpoint"
    __table_args__ = (UniqueConstraint("run_pk", "touchpoint_pk", "outcome"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    outcome: Mapped[str] = mapped_column(String(32), index=True)

    markov_share: Mapped[float] = mapped_column(Float, default=0.0)
    shapley_share: Mapped[float] = mapped_column(Float, default=0.0)
    gap_pp: Mapped[float] = mapped_column(Float, default=0.0)
    relative_gap: Mapped[float | None] = mapped_column(Float, nullable=True)

    raw_unique_paths: Mapped[int] = mapped_column(Integer, default=0)
    raw_converted_users: Mapped[int] = mapped_column(Integer, default=0)
    raw_purchase_count: Mapped[int] = mapped_column(Integer, default=0)

    calculation_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    data_support_sufficient: Mapped[bool] = mapped_column(Boolean, default=False)
    models_consistent: Mapped[bool] = mapped_column(Boolean, default=False)
    reliability_status: Mapped[str] = mapped_column(String(16))
    reliability_reason: Mapped[str] = mapped_column(String(128))

    run_pk: Mapped[int] = mapped_column(ForeignKey("attribution_run.id"))
    run: Mapped[AttributionRun] = relationship()
    touchpoint_pk: Mapped[int] = mapped_column(ForeignKey("touchpoint.id"))
    touchpoint: Mapped[Touchpoint] = relationship()


class ModelComparisonSummary(Base):
    """One whole-outcome diagnostic row.

    Total variation distance, Spearman correlation, and Top-K overlap are
    reported here only. They inform a reader; they never change reliability,
    which AND-aggregates the touchpoint booleans.
    """

    __tablename__ = "model_comparison_summary"
    __table_args__ = (UniqueConstraint("run_pk", "outcome"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    outcome: Mapped[str] = mapped_column(String(32))
    touchpoint_count: Mapped[int] = mapped_column(Integer, default=0)

    tvd: Mapped[float] = mapped_column(Float, default=0.0)
    spearman_rho: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_k_overlap_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    calculation_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    data_support_sufficient: Mapped[bool] = mapped_column(Boolean, default=False)
    models_consistent: Mapped[bool] = mapped_column(Boolean, default=False)
    reliability_status: Mapped[str] = mapped_column(String(16))
    reliability_reason: Mapped[str] = mapped_column(String(128))

    run_pk: Mapped[int] = mapped_column(ForeignKey("attribution_run.id"))
    run: Mapped[AttributionRun] = relationship()


class RecommendedAttribution(Base):
    """The governed view: official model, benchmark, and recommended value.

    `recommended_value` is a text union type. A RELIABLE row holds the Markov
    point as a string; an UNRELIABLE row holds the closed interval
    `[low,high]` between the two model shares. It is a governance output, not
    a third model, and grants no budgeting authority.
    """

    __tablename__ = "recommended_attribution"
    __table_args__ = (UniqueConstraint("run_pk", "touchpoint_pk", "outcome"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    outcome: Mapped[str] = mapped_column(String(32), index=True)

    official_model: Mapped[str] = mapped_column(String(32))
    official_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_value: Mapped[str] = mapped_column(String(64))
    benchmark_model: Mapped[str] = mapped_column(String(32))
    benchmark_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_gap: Mapped[float | None] = mapped_column(Float, nullable=True)

    calculation_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    data_support_sufficient: Mapped[bool] = mapped_column(Boolean, default=False)
    models_consistent: Mapped[bool] = mapped_column(Boolean, default=False)
    reliability_status: Mapped[str] = mapped_column(String(16))
    reliability_reason: Mapped[str] = mapped_column(String(128))

    run_pk: Mapped[int] = mapped_column(ForeignKey("attribution_run.id"))
    run: Mapped[AttributionRun] = relationship()
    touchpoint_pk: Mapped[int] = mapped_column(ForeignKey("touchpoint.id"))
    touchpoint: Mapped[Touchpoint] = relationship()


class ModelArtifact(ArtifactBase):
    """One validated model-output file explicitly imported by an operator.

    This table is optional and is not part of ``IMPORT_ORDER``. The artifact
    service creates it on the first explicit import so an older dashboard
    schema remains readable without an unrelated migration.
    """

    __tablename__ = "model_artifact"
    __table_args__ = (UniqueConstraint("stage", "filename"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    filename: Mapped[str] = mapped_column(String(128))
    media_type: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime)


# ---------------------------------------------------------------------------
# Layer 4 — Strategy
# ---------------------------------------------------------------------------


class BudgetRecommendationRun(Base):
    """One execution of the budget initializer.

    `is_optimized` is false for every current run: this is a deterministic
    seed derived from historical attribution, not an optimizer result.
    """

    __tablename__ = "budget_recommendation_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16))
    campaign_group_id: Mapped[str] = mapped_column(String(64))
    candidate_pool_id: Mapped[str] = mapped_column(String(64))
    mta_batch_id: Mapped[str] = mapped_column(String(64))

    #: Provenance of the attribution evidence this run consumed. The hashes
    #: identify the exact input files, so a recommendation can be traced back
    #: to the attribution output that justified it.
    source_report_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_report_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_marketplace: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source_advertiser_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_attribution_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    source_entity_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    recommendation_type: Mapped[str] = mapped_column(String(32))
    handoff_status: Mapped[str] = mapped_column(String(32))
    is_optimized: Mapped[bool] = mapped_column(Boolean, default=False)

    formula_version: Mapped[str] = mapped_column(String(64))
    normalization_universe: Mapped[str] = mapped_column(String(64))
    weight_converted_users: Mapped[float] = mapped_column(Float, default=0.0)
    weight_purchase_count: Mapped[float] = mapped_column(Float, default=0.0)
    weight_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    budget_seed_total: Mapped[float] = mapped_column(Float, default=0.0)
    imported_at: Mapped[datetime] = mapped_column(DateTime)


class CampaignBudgetRecommendation(Base):
    """One Campaign's score, new Ad Group count, and budget seed.

    `campaign_mta_score` is stored at full float precision, matching the JSON
    artifact; only money fields are rounded.
    """

    __tablename__ = "campaign_budget_recommendation"
    __table_args__ = (UniqueConstraint("run_pk", "campaign_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    recommended_ad_group_count: Mapped[int] = mapped_column(Integer, default=0)

    score_converted_users: Mapped[float] = mapped_column(Float, default=0.0)
    score_purchase_count: Mapped[float] = mapped_column(Float, default=0.0)
    score_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    campaign_mta_score: Mapped[float] = mapped_column(Float, default=0.0)
    budget_seed_share: Mapped[float] = mapped_column(Float, default=0.0)
    campaign_budget_seed: Mapped[float] = mapped_column(Float, default=0.0)
    minimum_required_daily_budget: Mapped[float] = mapped_column(Float, default=0.0)
    execution_status: Mapped[str] = mapped_column(String(32))

    count_formula_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capacity_required_count: Mapped[int] = mapped_column(Integer, default=0)
    bridge_historical_ad_group_count: Mapped[int] = mapped_column(Integer, default=0)
    bridge_touchpoint_count: Mapped[int] = mapped_column(Integer, default=0)
    bridge_fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)

    run_pk: Mapped[int] = mapped_column(ForeignKey("budget_recommendation_run.id"))
    run: Mapped[BudgetRecommendationRun] = relationship()


class AdGroupBudgetSlot(Base):
    """One anonymous new Ad Group slot and its daily budget.

    Slots are anonymous by design. Within a Campaign the seed is split equally,
    because new groups have no distinguishing history yet; `allocation_basis`
    records that rule.
    """

    __tablename__ = "ad_group_budget_slot"

    id: Mapped[int] = mapped_column(primary_key=True)
    ad_group_slot_id: Mapped[str] = mapped_column(String(64))
    allocation_basis: Mapped[str] = mapped_column(String(64))
    budget_seed_share: Mapped[float] = mapped_column(Float, default=0.0)
    initial_daily_budget: Mapped[float] = mapped_column(Float, default=0.0)

    campaign_recommendation_pk: Mapped[int] = mapped_column(
        ForeignKey("campaign_budget_recommendation.id")
    )
    campaign_recommendation: Mapped[CampaignBudgetRecommendation] = relationship()


#: Import order that satisfies every foreign key.
IMPORT_ORDER: tuple[type[Base], ...] = (
    Advertiser,
    CampaignGroup,
    Campaign,
    AdGroup,
    Touchpoint,
    TargetingCandidate,
    AdsDailyPerformance,
    PathReport,
    TouchpointEntityBridge,
    SyntheticUserEvent,
    AttributionRun,
    AttributionResult,
    ModelComparisonTouchpoint,
    ModelComparisonSummary,
    RecommendedAttribution,
    BudgetRecommendationRun,
    CampaignBudgetRecommendation,
    AdGroupBudgetSlot,
)
