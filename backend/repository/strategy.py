"""Strategy: what the budget initializer and the optimizer recommended.

Four snapshot keys come from here. Two of them are nested JSON documents in
file mode and relational tables in database mode, so the database branch
reassembles the artifact's own shape; a view then reads
`campaigns[i].recommended_ad_groups` without branching on mode.

One key has no database representation at all. `campaign_strategy.json` is
written by a research command rather than by the import pipeline, so a
database-mode run finds no table for it and returns the same empty object an
absent file returns. The Optimization Log reads that as "the optimizer has not
run", which is the honest reading in both modes.

Data flow:
    modules/mta_strategy_recommendation/outputs/&#42;.json  -.
                                                          +-> here -> /api/dashboard
    budget_recommendation_run + campaign + slot tables  -'
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sqlalchemy import select

from backend.config import (
    STRATEGY_INPUT_DIR,
    STRATEGY_OUTPUT_DIR,
    pipeline_artifact_path,
    use_database,
)
from backend.database import orm_rows
from backend.repository.coercion import format_date, read_json, to_number
from backend.services.model_outputs import restored_artifact_path
from dashboard.models import (
    AdGroupBudgetSlot,
    Advertiser,
    BudgetRecommendationRun,
    Campaign,
    CampaignBudgetRecommendation,
    CampaignGroup,
    TargetingCandidate,
)


def _float(value: Any) -> float:
    """Coerce to a float, treating an absent value as zero.

    Used only for the budget document's own numeric fields, every one of which
    the artifact always carries; a missing one is a defect in the import, not
    an expected absence, and zero is what the JSON artifact would have held.
    """
    number = to_number(value)
    return float(number) if number is not None else 0.0


def budget_recommendation() -> dict:
    """The canonical initial-budget recommendation, as a nested object."""
    if not use_database():
        return read_json(STRATEGY_OUTPUT_DIR / "initial_budget_recommendation.json")

    runs = orm_rows(
        select(BudgetRecommendationRun)
        .order_by(BudgetRecommendationRun.id.desc())
        .limit(1)
    )
    if not runs:
        return {}
    run = runs[0]

    # Ordered by the surrogate key, not by `campaign_id`. The importer inserts
    # campaigns in the artifact's own order, so `id` reproduces it; sorting by
    # the business key would sort alphabetically and put the Campaigns in a
    # different order than file mode returns them in.
    campaigns = orm_rows(
        select(CampaignBudgetRecommendation)
        .where(CampaignBudgetRecommendation.run_pk == run["id"])
        .order_by(CampaignBudgetRecommendation.id)
    )
    slots = orm_rows(
        select(
            AdGroupBudgetSlot.ad_group_slot_id,
            AdGroupBudgetSlot.allocation_basis,
            AdGroupBudgetSlot.budget_seed_share,
            AdGroupBudgetSlot.initial_daily_budget,
            CampaignBudgetRecommendation.campaign_id,
        )
        .join(
            CampaignBudgetRecommendation,
            CampaignBudgetRecommendation.id
            == AdGroupBudgetSlot.campaign_recommendation_pk,
        )
        .order_by(AdGroupBudgetSlot.id)
    )
    return rebuild_budget_document(run, campaigns, slots)


def rebuild_budget_document(
    run: Mapping[str, Any],
    campaigns: Sequence[Mapping[str, Any]],
    slots: Sequence[Mapping[str, Any]],
) -> dict:
    """Reassemble the JSON artifact's shape from three relational tables."""
    campaign_records = [
        {
            "campaign_id": row["campaign_id"],
            "recommended_ad_group_count": int(
                _float(row["recommended_ad_group_count"])
            ),
            "count_rationale": {
                "count_formula_version": row["count_formula_version"],
                "capacity_required_count": int(_float(row["capacity_required_count"])),
                "final_recommended_count": int(
                    _float(row["recommended_ad_group_count"])
                ),
            },
            "outcome_contributions": {
                "converted_users": _float(row["score_converted_users"]),
                "purchase_count": _float(row["score_purchase_count"]),
                "revenue": _float(row["score_revenue"]),
            },
            "campaign_mta_score": _float(row["campaign_mta_score"]),
            "bridge_summary": {
                "historical_ad_group_count": int(
                    _float(row["bridge_historical_ad_group_count"])
                ),
                "touchpoint_count": int(_float(row["bridge_touchpoint_count"])),
                "fallback_used": bool(row["bridge_fallback_used"]),
            },
            "budget_seed_share": _float(row["budget_seed_share"]),
            "minimum_required_daily_budget": _float(
                row["minimum_required_daily_budget"]
            ),
            "campaign_budget_seed": _float(row["campaign_budget_seed"]),
            "execution_status": row["execution_status"],
            "recommended_ad_groups": [
                {
                    "ad_group_slot_id": slot["ad_group_slot_id"],
                    "allocation_basis": slot["allocation_basis"],
                    "budget_seed_share": _float(slot["budget_seed_share"]),
                    "initial_daily_budget": _float(slot["initial_daily_budget"]),
                }
                for slot in slots
                if slot["campaign_id"] == row["campaign_id"]
            ],
        }
        for row in campaigns
    ]

    return {
        "schema_version": run["schema_version"],
        "campaign_group_id": run["campaign_group_id"],
        "candidate_pool_id": run["candidate_pool_id"],
        "mta_batch_id": run["mta_batch_id"],
        "mta_source_snapshot": {
            "report_start_date": format_date(run["source_report_start_date"]),
            "report_end_date": format_date(run["source_report_end_date"]),
            "marketplace": run["source_marketplace"],
            "advertiser_id": run["source_advertiser_id"],
            "attribution_sha256": run["source_attribution_sha256"],
            "entity_sha256": run["source_entity_sha256"],
        },
        "recommendation_type": run["recommendation_type"],
        "handoff_status": run["handoff_status"],
        "is_optimized": bool(run["is_optimized"]),
        "budget_derivation": {
            "formula_version": run["formula_version"],
            "normalization_universe": run["normalization_universe"],
            "outcome_weights": {
                "converted_users": _float(run["weight_converted_users"]),
                "purchase_count": _float(run["weight_purchase_count"]),
                "revenue": _float(run["weight_revenue"]),
            },
        },
        "campaigns": campaign_records,
        "budget_seed_total": _float(run["budget_seed_total"]),
        "warnings": [],
    }


def campaign_strategy() -> dict:
    """The optimized Campaign budget plan and the response evidence behind it.

    Read in its own shape in both modes. This artifact has no database
    representation: it is produced by `script/generate_campaign_strategy.py`
    rather than by the import pipeline.
    """
    fallback = pipeline_artifact_path(
        "strategy/campaign_strategy.json",
        STRATEGY_OUTPUT_DIR / "campaign_strategy.json",
    )
    return read_json(
        restored_artifact_path("optimization", "campaign_strategy.json", fallback)
    )


def strategy_request() -> dict:
    """The Campaign Group, its Campaigns, weights, and capacity rules.

    Capacity rules are pipeline configuration rather than observed data, so no
    table holds them; in database mode the key is present but empty and views
    must treat it as optional. The outcome weights are recoverable, because the
    budget run records the weights it was executed with.
    """
    if not use_database():
        return read_json(STRATEGY_INPUT_DIR / "strategy_request.json")

    groups = orm_rows(
        select(
            CampaignGroup.campaign_group_id,
            CampaignGroup.group_name,
            CampaignGroup.platform,
            CampaignGroup.currency,
            CampaignGroup.total_daily_budget,
            CampaignGroup.sample_version,
            CampaignGroup.candidate_pool_id,
            CampaignGroup.mta_batch_id,
            Advertiser.marketplace,
            Advertiser.advertiser_id,
        )
        .join(Advertiser, Advertiser.id == CampaignGroup.advertiser_pk)
        .limit(1)
    )
    if not groups:
        return {}
    group = groups[0]

    # See `budget_recommendation`: `id` is the artifact's insertion order, and
    # `campaign_id` is alphabetical and would disagree with file mode.
    campaigns = orm_rows(
        select(
            Campaign.campaign_id,
            Campaign.campaign_name,
            Campaign.ad_product,
            Campaign.status,
        ).order_by(Campaign.id)
    )
    runs = orm_rows(
        select(
            BudgetRecommendationRun.weight_converted_users,
            BudgetRecommendationRun.weight_purchase_count,
            BudgetRecommendationRun.weight_revenue,
            BudgetRecommendationRun.source_report_start_date,
            BudgetRecommendationRun.source_report_end_date,
            BudgetRecommendationRun.source_marketplace,
            BudgetRecommendationRun.source_advertiser_id,
            BudgetRecommendationRun.source_attribution_sha256,
            BudgetRecommendationRun.source_entity_sha256,
        )
        .order_by(BudgetRecommendationRun.id.desc())
        .limit(1)
    )

    weights: dict = {}
    source: dict = {}
    if runs:
        run = runs[0]
        weights = {
            "converted_users": _float(run["weight_converted_users"]),
            "purchase_count": _float(run["weight_purchase_count"]),
            "revenue": _float(run["weight_revenue"]),
        }
        source = {
            "report_start_date": format_date(run["source_report_start_date"]),
            "report_end_date": format_date(run["source_report_end_date"]),
            "marketplace": run["source_marketplace"],
            "advertiser_id": run["source_advertiser_id"],
            "attribution_sha256": run["source_attribution_sha256"],
            "entity_sha256": run["source_entity_sha256"],
        }

    return {
        "sample_version": group["sample_version"] or "",
        "candidate_pool_id": group["candidate_pool_id"] or "",
        "mta_batch_id": group["mta_batch_id"] or "",
        "mta_source": source,
        "campaign_group": {
            "campaign_group_id": group["campaign_group_id"],
            "group_name": group["group_name"],
            "platform": group["platform"],
            "marketplace": group["marketplace"],
            "advertiser_id": group["advertiser_id"],
            "currency": group["currency"],
            "total_daily_budget": _float(group["total_daily_budget"]),
        },
        "campaigns": campaigns,
        "outcome_weights": weights,
        "capacity_rules": {},
    }


def candidate_pool() -> dict:
    """Eligible keyword, SKU, target, and audience counts per Campaign."""
    if not use_database():
        return read_json(STRATEGY_INPUT_DIR / "candidate_pool.json")

    rows = orm_rows(
        select(
            Campaign.campaign_id,
            TargetingCandidate.candidate_kind,
            TargetingCandidate.eligible_count,
            TargetingCandidate.candidate_pool_id,
            TargetingCandidate.candidate_usage_policy,
            TargetingCandidate.sample_version,
        )
        .join(Campaign, Campaign.id == TargetingCandidate.campaign_pk)
        .order_by(Campaign.id, TargetingCandidate.id)
    )

    counts: dict[str, dict] = {}
    pool_id = ""
    policy = ""
    version = ""
    for row in rows:
        pool_id = pool_id or (row["candidate_pool_id"] or "")
        policy = policy or (row["candidate_usage_policy"] or "")
        version = version or (row["sample_version"] or "")
        record = counts.setdefault(
            row["campaign_id"], {"campaign_id": row["campaign_id"]}
        )
        record[row["candidate_kind"]] = int(_float(row["eligible_count"]))

    group = orm_rows(select(CampaignGroup.campaign_group_id).limit(1))
    return {
        "sample_version": version,
        "candidate_pool_id": pool_id,
        "campaign_group_id": group[0]["campaign_group_id"] if group else "",
        "candidate_usage_policy": policy,
        "campaign_candidate_counts": list(counts.values()),
    }
