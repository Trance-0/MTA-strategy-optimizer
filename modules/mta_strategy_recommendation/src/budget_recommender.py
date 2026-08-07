"""Deterministic Campaign Group budget initializer.

Converts attribution evidence into a new Ad Group count and an initial budget
split. It produces a starting point, never an optimized plan: the output is
labelled `INITIAL_SEED` and carries no claim of optimality.

Data flow:
    recommended attribution + entity bridge + strategy request + candidate pool
      -> touchpoint scores normalised across the whole MTA universe
      -> Campaign shares via the bridge
      -> capacity rules -> new Ad Group count per Campaign
      -> equal split inside each anonymous new group
      -> `initial_budget_recommendation.json`

New Ad Groups within one Campaign have no distinguishable candidate features
yet, which is why the split inside a group can only be equal.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping


SUPPORTED_SAMPLE_VERSION = "4.0"
SUPPORTED_AD_PRODUCTS = (
    "SPONSORED_PRODUCTS",
    "SPONSORED_BRANDS",
    "SPONSORED_DISPLAY",
    "AMAZON_DSP",
)
SEARCH_AD_PRODUCTS = {"SPONSORED_PRODUCTS", "SPONSORED_BRANDS"}
DISPLAY_AD_PRODUCTS = {"SPONSORED_DISPLAY", "AMAZON_DSP"}
OUTCOMES = ("converted_users", "purchase_count", "revenue")
ASSISTED_METRIC_BY_OUTCOME = {
    "converted_users": "assisted_converted_users",
    "purchase_count": "assisted_purchase_count",
    "revenue": "assisted_revenue",
}
BRIDGE_FALLBACK_METRICS = ("clicks", "impressions", "unique_users")
NORMALIZATION_UNIVERSE = "ALL_AVAILABLE_MTA_TOUCHPOINTS"
FORMULA_VERSION = "MTA_AMC_CAMPAIGN_BRIDGE_V1"
COUNT_FORMULA_VERSION = "CANDIDATE_CAPACITY_MAX_V1"
ALLOCATION_BASIS = "CAMPAIGN_MTA_EQUAL_SPLIT"
MTA_VALUE_POLICY = "RELIABLE_POINT_OR_UNRELIABLE_RANGE_MIDPOINT"


class BudgetRecommendationError(ValueError):
    """Raised when budget-only strategy inputs cannot produce a valid seed."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], context: str) -> None:
    actual = set(value)
    if actual != expected:
        raise BudgetRecommendationError(
            f"{context} fields must exactly match v4 schema "
            f"(missing={sorted(expected - actual)}, extra={sorted(actual - expected)})"
        )


def _required_text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise BudgetRecommendationError(f"{context} must be a non-empty trimmed string")
    return value


def _number(value: object, context: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool):
        raise BudgetRecommendationError(f"{context} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise BudgetRecommendationError(f"{context} must be numeric") from exc
    if not math.isfinite(result) or result < minimum:
        raise BudgetRecommendationError(f"{context} must be finite and >= {minimum}")
    return result


def _json_number(value: object, context: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BudgetRecommendationError(f"{context} must be a JSON number")
    return _number(value, context, minimum=minimum)


def _integer(value: object, context: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise BudgetRecommendationError(f"{context} must be an integer >= {minimum}")
    return value


def _objects(value: object, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value or any(not isinstance(row, dict) for row in value):
        raise BudgetRecommendationError(f"{context} must be a non-empty list of objects")
    return value


def _index_unique(
    rows: Iterable[dict[str, Any]], key: str, context: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows, start=1):
        item_id = _required_text(row.get(key), f"{context}[{position}].{key}")
        if item_id in result:
            raise BudgetRecommendationError(f"{context} repeats {key} {item_id}")
        result[item_id] = row
    return result


def _ceil_ratio(count: int, capacity: int) -> int:
    return 0 if count == 0 else (count + capacity - 1) // capacity


def _touchpoint_product(value: object, context: str) -> str:
    touchpoint = _required_text(value, context)
    segments = touchpoint.split(":")
    if len(segments) != 5 or any(not segment for segment in segments):
        raise BudgetRecommendationError(f"{context} must be a non-empty five-segment key")
    product = segments[0]
    if product not in SUPPORTED_AD_PRODUCTS:
        raise BudgetRecommendationError(f"{context} uses unsupported ad product {product}")
    return product


def _recommended_point(row: Mapping[str, Any], context: str) -> tuple[float, str]:
    status = _required_text(row.get("reliability_status"), f"{context} reliability_status")
    value = row.get("recommended_value")
    if status == "RELIABLE":
        point = _number(value, f"{context} recommended_value")
        if point > 1.0:
            raise BudgetRecommendationError(f"{context} recommended_value must be <= 1")
        return point, status
    if status != "UNRELIABLE":
        raise BudgetRecommendationError(f"{context} has unsupported reliability_status {status}")
    if not isinstance(value, str) or not value.startswith("[") or not value.endswith("]"):
        raise BudgetRecommendationError(
            f"{context} UNRELIABLE recommended_value must be [low,high]"
        )
    parts = value[1:-1].split(",")
    if len(parts) != 2:
        raise BudgetRecommendationError(
            f"{context} UNRELIABLE recommended_value must be [low,high]"
        )
    low = _number(parts[0], f"{context} recommended low")
    high = _number(parts[1], f"{context} recommended high")
    if low > high:
        raise BudgetRecommendationError(f"{context} recommended range must be ordered")
    if high > 1.0:
        raise BudgetRecommendationError(f"{context} recommended range endpoints must be <= 1")
    return (low + high) / 2.0, status


def _campaign_inputs(
    request: Mapping[str, Any], pool: Mapping[str, Any]
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, float],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    _exact_keys(
        request,
        {
            "sample_version",
            "candidate_pool_id",
            "mta_batch_id",
            "mta_source",
            "campaign_group",
            "campaigns",
            "outcome_weights",
            "capacity_rules",
        },
        "strategy_request",
    )
    _exact_keys(
        pool,
        {
            "sample_version",
            "candidate_pool_id",
            "campaign_group_id",
            "candidate_usage_policy",
            "campaign_candidate_counts",
        },
        "candidate_pool",
    )
    if request.get("sample_version") != SUPPORTED_SAMPLE_VERSION:
        raise BudgetRecommendationError(
            f"strategy_request.sample_version must be {SUPPORTED_SAMPLE_VERSION}"
        )
    if pool.get("sample_version") != SUPPORTED_SAMPLE_VERSION:
        raise BudgetRecommendationError(
            f"candidate_pool.sample_version must be {SUPPORTED_SAMPLE_VERSION}"
        )

    source = request.get("mta_source")
    if not isinstance(source, dict):
        raise BudgetRecommendationError("mta_source must be an object")
    _exact_keys(
        source,
        {
            "report_start_date",
            "report_end_date",
            "marketplace",
            "advertiser_id",
            "attribution_file",
            "attribution_sha256",
            "entity_file",
            "entity_sha256",
            "available_touchpoint_count",
            "entity_row_count",
        },
        "mta_source",
    )

    group = request.get("campaign_group")
    if not isinstance(group, dict):
        raise BudgetRecommendationError("campaign_group must be an object")
    group_fields = {
        "campaign_group_id",
        "group_name",
        "platform",
        "marketplace",
        "advertiser_id",
        "currency",
    }
    if "total_daily_budget" in group:
        group_fields.add("total_daily_budget")
    _exact_keys(group, group_fields, "campaign_group")
    group_id = _required_text(group.get("campaign_group_id"), "campaign_group_id")
    for field in ("group_name", "platform", "marketplace", "advertiser_id", "currency"):
        _required_text(group.get(field), f"campaign_group.{field}")
    if group.get("platform") != "AMAZON":
        raise BudgetRecommendationError("campaign_group.platform must be AMAZON")

    campaigns = _objects(request.get("campaigns"), "campaigns")
    campaign_index = _index_unique(campaigns, "campaign_id", "campaigns")
    if len(campaigns) != 4:
        raise BudgetRecommendationError("Campaign Group must contain exactly 4 Campaigns")
    product_campaigns: dict[str, str] = {}
    for campaign_id, campaign in campaign_index.items():
        _exact_keys(
            campaign,
            {"campaign_id", "campaign_name", "ad_product", "status"},
            f"campaign {campaign_id}",
        )
        _required_text(campaign.get("campaign_name"), f"campaign {campaign_id} campaign_name")
        product = _required_text(campaign.get("ad_product"), f"campaign {campaign_id} ad_product")
        if product not in SUPPORTED_AD_PRODUCTS or product in product_campaigns:
            raise BudgetRecommendationError(
                "the four Campaigns must use each supported ad product exactly once"
            )
        if campaign.get("status") != "enabled":
            raise BudgetRecommendationError(f"campaign {campaign_id} must be enabled")
        product_campaigns[product] = campaign_id

    weights = request.get("outcome_weights")
    if not isinstance(weights, dict) or set(weights) != set(OUTCOMES):
        raise BudgetRecommendationError(
            "outcome_weights must contain converted_users, purchase_count and revenue"
        )
    normalized_weights = {
        outcome: _json_number(weights[outcome], f"outcome_weights.{outcome}")
        for outcome in OUTCOMES
    }
    if not math.isclose(sum(normalized_weights.values()), 1.0, abs_tol=1e-9):
        raise BudgetRecommendationError("outcome_weights must sum to 1")

    pool_id = _required_text(request.get("candidate_pool_id"), "candidate_pool_id")
    if pool.get("candidate_pool_id") != pool_id or pool.get("campaign_group_id") != group_id:
        raise BudgetRecommendationError("candidate pool lineage does not match strategy request")
    if pool.get("candidate_usage_policy") != "USE_ALL_ELIGIBLE":
        raise BudgetRecommendationError("candidate_usage_policy must be USE_ALL_ELIGIBLE")
    candidate_counts = _index_unique(
        _objects(pool.get("campaign_candidate_counts"), "campaign_candidate_counts"),
        "campaign_id",
        "campaign_candidate_counts",
    )
    if set(candidate_counts) != set(campaign_index):
        raise BudgetRecommendationError(
            "campaign_candidate_counts must contain every Campaign exactly once"
        )

    capacity_rules = request.get("capacity_rules")
    if not isinstance(capacity_rules, dict) or set(capacity_rules) != set(SUPPORTED_AD_PRODUCTS):
        raise BudgetRecommendationError(
            "capacity_rules must contain each supported ad product exactly once"
        )
    if any(not isinstance(rule, dict) for rule in capacity_rules.values()):
        raise BudgetRecommendationError("each capacity rule must be an object")
    for product, rule in capacity_rules.items():
        shared_fields = {
            "max_skus_per_ad_group",
            "min_ad_groups",
            "max_ad_groups",
            "minimum_daily_budget_per_ad_group",
        }
        product_fields = (
            {"max_keyword_units_per_ad_group", "max_legal_pairs_per_ad_group"}
            if product in SEARCH_AD_PRODUCTS
            else {"max_targets_per_ad_group", "max_audiences_per_ad_group"}
        )
        _exact_keys(rule, shared_fields | product_fields, f"capacity_rules.{product}")

    return (
        group,
        campaigns,
        campaign_index,
        normalized_weights,
        candidate_counts,
        capacity_rules,
    )


def recommend_ad_group_count(
    campaign: Mapping[str, Any],
    candidate_counts: Mapping[str, Any],
    capacity_rule: Mapping[str, Any],
) -> tuple[int, dict[str, Any], float]:
    """Return the capacity-derived count, rationale, and minimum executable budget."""

    campaign_id = _required_text(campaign.get("campaign_id"), "campaign_id")
    product = _required_text(campaign.get("ad_product"), f"campaign {campaign_id} ad_product")
    expected_count_fields = {
        "campaign_id",
        "eligible_keyword_unit_count",
        "eligible_sku_count",
        "eligible_legal_pair_count",
        "eligible_target_count",
        "eligible_audience_count",
    }
    if set(candidate_counts) != expected_count_fields:
        raise BudgetRecommendationError(
            f"candidate counts for {campaign_id} must contain only the v4 count fields"
        )
    count_fields = (
        "eligible_keyword_unit_count",
        "eligible_sku_count",
        "eligible_legal_pair_count",
        "eligible_target_count",
        "eligible_audience_count",
    )
    counts = {
        field: _integer(candidate_counts[field], f"{campaign_id}.{field}")
        for field in count_fields
    }
    min_groups = _integer(capacity_rule.get("min_ad_groups"), f"{product}.min_ad_groups", minimum=1)
    max_groups = _integer(capacity_rule.get("max_ad_groups"), f"{product}.max_ad_groups", minimum=1)
    minimum_daily_budget = _json_number(
        capacity_rule.get("minimum_daily_budget_per_ad_group"),
        f"{product}.minimum_daily_budget_per_ad_group",
    )
    if minimum_daily_budget <= 0:
        raise BudgetRecommendationError(
            f"{product}.minimum_daily_budget_per_ad_group must be > 0"
        )
    if min_groups > max_groups:
        raise BudgetRecommendationError(f"{product} min_ad_groups exceeds max_ad_groups")

    rationale: dict[str, Any] = {
        "count_formula_version": COUNT_FORMULA_VERSION,
        **counts,
    }
    if product in SEARCH_AD_PRODUCTS:
        if counts["eligible_target_count"] or counts["eligible_audience_count"]:
            raise BudgetRecommendationError(
                f"{campaign_id} search count input must not include Target or Audience counts"
            )
        for field in (
            "eligible_keyword_unit_count",
            "eligible_sku_count",
            "eligible_legal_pair_count",
        ):
            if counts[field] == 0:
                raise BudgetRecommendationError(f"{campaign_id} requires a positive {field}")
        if counts["eligible_legal_pair_count"] > (
            counts["eligible_keyword_unit_count"] * counts["eligible_sku_count"]
        ):
            raise BudgetRecommendationError(
                f"{campaign_id} eligible_legal_pair_count exceeds Keyword × SKU upper bound"
            )
        keyword_capacity = _integer(
            capacity_rule.get("max_keyword_units_per_ad_group"),
            f"{product}.max_keyword_units_per_ad_group",
            minimum=1,
        )
        sku_capacity = _integer(
            capacity_rule.get("max_skus_per_ad_group"),
            f"{product}.max_skus_per_ad_group",
            minimum=1,
        )
        pair_capacity = _integer(
            capacity_rule.get("max_legal_pairs_per_ad_group"),
            f"{product}.max_legal_pairs_per_ad_group",
            minimum=1,
        )
        capacity_counts = {
            "keyword_capacity_count": _ceil_ratio(
                counts["eligible_keyword_unit_count"], keyword_capacity
            ),
            "sku_capacity_count": _ceil_ratio(counts["eligible_sku_count"], sku_capacity),
            "legal_pair_capacity_count": _ceil_ratio(
                counts["eligible_legal_pair_count"], pair_capacity
            ),
            "target_capacity_count": 0,
            "audience_capacity_count": 0,
        }
    elif product in DISPLAY_AD_PRODUCTS:
        if counts["eligible_keyword_unit_count"] or counts["eligible_legal_pair_count"]:
            raise BudgetRecommendationError(
                f"{campaign_id} display count input must not include Keyword or Pair counts"
            )
        for field in ("eligible_sku_count", "eligible_target_count", "eligible_audience_count"):
            if counts[field] == 0:
                raise BudgetRecommendationError(f"{campaign_id} requires a positive {field}")
        sku_capacity = _integer(
            capacity_rule.get("max_skus_per_ad_group"),
            f"{product}.max_skus_per_ad_group",
            minimum=1,
        )
        target_capacity = _integer(
            capacity_rule.get("max_targets_per_ad_group"),
            f"{product}.max_targets_per_ad_group",
            minimum=1,
        )
        audience_capacity = _integer(
            capacity_rule.get("max_audiences_per_ad_group"),
            f"{product}.max_audiences_per_ad_group",
            minimum=1,
        )
        capacity_counts = {
            "keyword_capacity_count": 0,
            "sku_capacity_count": _ceil_ratio(counts["eligible_sku_count"], sku_capacity),
            "legal_pair_capacity_count": 0,
            "target_capacity_count": _ceil_ratio(
                counts["eligible_target_count"], target_capacity
            ),
            "audience_capacity_count": _ceil_ratio(
                counts["eligible_audience_count"], audience_capacity
            ),
        }
    else:
        raise BudgetRecommendationError(f"unsupported ad product {product}")

    capacity_required = max(min_groups, *capacity_counts.values())
    if capacity_required > max_groups:
        raise BudgetRecommendationError(
            f"{campaign_id} requires {capacity_required} Ad Groups, exceeding max_ad_groups={max_groups}"
        )
    rationale.update(capacity_counts)
    rationale["capacity_required_count"] = capacity_required
    rationale["final_recommended_count"] = capacity_required
    minimum_required_budget = minimum_daily_budget * capacity_required
    if not math.isfinite(minimum_required_budget):
        raise BudgetRecommendationError(f"{campaign_id} minimum required budget overflow")
    return capacity_required, rationale, minimum_required_budget


def _entity_weight_method(
    rows: list[Mapping[str, Any]], outcome: str
) -> tuple[str, list[float]]:
    assisted_metric = ASSISTED_METRIC_BY_OUTCOME[outcome]
    for metric in (assisted_metric, *BRIDGE_FALLBACK_METRICS):
        values = [_number(row.get(metric), f"AMC entity {metric}") for row in rows]
        if sum(values) > 0:
            return metric.upper(), values
    return "EQUAL", [1.0] * len(rows)


def _bridge_campaign_scores(
    campaigns: list[dict[str, Any]],
    weights: Mapping[str, float],
    attribution_rows: list[Mapping[str, Any]],
    entity_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], int, Counter[str], dict[str, set[str]]]:
    product_to_campaign = {campaign["ad_product"]: campaign["campaign_id"] for campaign in campaigns}
    outcome_contributions: dict[str, dict[str, float]] = {
        campaign["campaign_id"]: {outcome: 0.0 for outcome in OUTCOMES}
        for campaign in campaigns
    }
    method_counts: dict[str, Counter[str]] = {
        campaign["campaign_id"]: Counter() for campaign in campaigns
    }
    touchpoints: dict[str, set[str]] = {
        campaign["campaign_id"]: set() for campaign in campaigns
    }
    historical_ad_groups: dict[str, set[str]] = {
        campaign["campaign_id"]: set() for campaign in campaigns
    }
    seen: set[tuple[str, str]] = set()
    outcomes_by_touchpoint: defaultdict[str, set[str]] = defaultdict(set)
    recommended_totals: Counter[str] = Counter()
    reliability_counts: Counter[str] = Counter()

    entity_signatures: set[tuple[tuple[str, str], ...]] = set()
    entity_touchpoints: set[str] = set()
    for position, entity in enumerate(entity_rows, start=1):
        if not isinstance(entity, Mapping):
            raise BudgetRecommendationError(f"AMC entity row {position} must be an object")
        touchpoint = _required_text(
            entity.get("touchpoint"), f"AMC entity row {position} touchpoint"
        )
        product = _touchpoint_product(touchpoint, f"AMC entity row {position} touchpoint")
        campaign_id = _required_text(
            entity.get("campaign_id"), f"AMC entity row {position} campaign_id"
        )
        if product_to_campaign.get(product) != campaign_id:
            raise BudgetRecommendationError(
                f"AMC entity row {position} Campaign/ad_product does not match strategy input"
            )
        signature = tuple(sorted((str(key), repr(value)) for key, value in entity.items()))
        if signature in entity_signatures:
            raise BudgetRecommendationError(f"duplicate AMC entity row at position {position}")
        entity_signatures.add(signature)
        entity_touchpoints.add(touchpoint)

    for position, row in enumerate(attribution_rows, start=1):
        touchpoint = _required_text(row.get("touchpoint"), f"attribution row {position} touchpoint")
        outcome = _required_text(row.get("outcome"), f"attribution row {position} outcome")
        if outcome not in OUTCOMES:
            raise BudgetRecommendationError(f"unsupported AMC outcome {outcome}")
        key = (touchpoint, outcome)
        if key in seen:
            raise BudgetRecommendationError(f"duplicate AMC attribution row {key}")
        seen.add(key)
        outcomes_by_touchpoint[touchpoint].add(outcome)
        product = _touchpoint_product(touchpoint, f"attribution row {position} touchpoint")
        campaign_id = product_to_campaign.get(product)
        if campaign_id is None:
            raise BudgetRecommendationError(f"AMC touchpoint uses unsupported ad product {product}")
        recommended_value, reliability_status = _recommended_point(
            row, f"attribution row {position}"
        )
        recommended_totals[outcome] += recommended_value
        reliability_counts[reliability_status] += 1
        matching_entities = [
            entity
            for entity in entity_rows
            if entity.get("touchpoint") == touchpoint
            and entity.get("campaign_id") == campaign_id
        ]
        if not matching_entities:
            raise BudgetRecommendationError(
                f"AMC touchpoint {touchpoint} has no entity bridge for Campaign {campaign_id}"
            )
        method, entity_weights = _entity_weight_method(matching_entities, outcome)
        denominator = sum(entity_weights)
        historical_allocations: defaultdict[str, float] = defaultdict(float)
        for entity_position, (entity, value) in enumerate(
            zip(matching_entities, entity_weights), start=1
        ):
            historical_ad_group_id = _required_text(
                entity.get("ad_group_id"),
                f"AMC entity bridge {touchpoint}[{entity_position}].ad_group_id",
            )
            historical_ad_groups[campaign_id].add(historical_ad_group_id)
            historical_allocations[historical_ad_group_id] += (
                recommended_value * value / denominator
            )
        allocated = sum(historical_allocations.values())
        if not math.isclose(allocated, recommended_value, abs_tol=1e-12):
            raise BudgetRecommendationError(f"AMC bridge failed to conserve {touchpoint}/{outcome}")
        outcome_contributions[campaign_id][outcome] += allocated
        method_counts[campaign_id][method] += 1
        touchpoints[campaign_id].add(touchpoint)

    if not seen:
        raise BudgetRecommendationError("AMC attribution input is empty")
    orphan_touchpoints = entity_touchpoints - set(outcomes_by_touchpoint)
    if orphan_touchpoints:
        raise BudgetRecommendationError(
            "AMC entity bridge contains touchpoints absent from attribution: "
            + ", ".join(sorted(orphan_touchpoints))
        )
    for touchpoint, observed in outcomes_by_touchpoint.items():
        if observed != set(OUTCOMES):
            raise BudgetRecommendationError(
                f"AMC touchpoint {touchpoint} must contain all three outcomes"
            )
    for outcome in OUTCOMES:
        if not math.isclose(recommended_totals[outcome], 1.0, abs_tol=1e-9):
            raise BudgetRecommendationError(
                f"AMC recommended_value for {outcome} must sum to 1"
            )

    result: dict[str, dict[str, Any]] = {}
    for campaign in campaigns:
        campaign_id = campaign["campaign_id"]
        if not touchpoints[campaign_id]:
            raise BudgetRecommendationError(
                f"Campaign {campaign_id} has no AMC attribution touchpoints"
            )
        contributions = outcome_contributions[campaign_id]
        score = sum(weights[outcome] * contributions[outcome] for outcome in OUTCOMES)
        result[campaign_id] = {
            "outcome_contributions": contributions,
            "campaign_mta_score": score,
            "bridge_summary": {
                "historical_ad_group_count": len(historical_ad_groups[campaign_id]),
                "touchpoint_count": len(touchpoints[campaign_id]),
                "touchpoint_outcome_count": sum(method_counts[campaign_id].values()),
                "method_counts": dict(sorted(method_counts[campaign_id].items())),
                "fallback_used": any(
                    method not in {name.upper() for name in ASSISTED_METRIC_BY_OUTCOME.values()}
                    for method in method_counts[campaign_id]
                ),
            },
        }
    return result, len(outcomes_by_touchpoint), reliability_counts, historical_ad_groups


def generate_budget_recommendation(
    request: Mapping[str, Any],
    pool: Mapping[str, Any],
    attribution_rows: list[Mapping[str, Any]],
    entity_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Generate a deterministic, non-optimized Ad Group count and budget seed."""

    (
        group,
        campaigns,
        _campaign_index,
        weights,
        candidate_counts,
        capacity_rules,
    ) = _campaign_inputs(request, pool)
    bridge, touchpoint_count, reliability_counts, historical_ad_groups = _bridge_campaign_scores(
        campaigns, weights, attribution_rows, entity_rows
    )
    score_total = sum(bridge[campaign["campaign_id"]]["campaign_mta_score"] for campaign in campaigns)
    if score_total <= 0:
        raise BudgetRecommendationError("Campaign MTA score total must be positive")

    has_budget = "total_daily_budget" in group and group["total_daily_budget"] is not None
    total_budget_value = group.get("total_daily_budget")
    total_budget = (
        _json_number(total_budget_value, "campaign_group.total_daily_budget")
        if has_budget
        else None
    )
    warnings: list[str] = []
    if not has_budget:
        warnings.append("NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY")
    if reliability_counts.get("UNRELIABLE", 0):
        warnings.append("UNRELIABLE_MTA_RANGE_MIDPOINT_USED")

    campaign_outputs: list[dict[str, Any]] = []
    for campaign in campaigns:
        campaign_id = campaign["campaign_id"]
        product = campaign["ad_product"]
        count, rationale, minimum_required_budget = recommend_ad_group_count(
            campaign, candidate_counts[campaign_id], capacity_rules[product]
        )
        campaign_score = bridge[campaign_id]["campaign_mta_score"]
        campaign_share = campaign_score / score_total
        output: dict[str, Any] = {
            "campaign_id": campaign_id,
            "recommended_ad_group_count": count,
            "count_rationale": rationale,
            "outcome_contributions": bridge[campaign_id]["outcome_contributions"],
            "campaign_mta_score": campaign_score,
            "bridge_summary": bridge[campaign_id]["bridge_summary"],
            "budget_seed_share": campaign_share,
        }
        if has_budget:
            output["minimum_required_daily_budget"] = minimum_required_budget
            campaign_budget = campaign_share * (total_budget or 0.0)
            output["campaign_budget_seed"] = campaign_budget
            if campaign_budget + 1e-9 < minimum_required_budget:
                output["execution_status"] = "INSUFFICIENT_BUDGET_FOR_MINIMUMS"
                warnings.append(f"INSUFFICIENT_BUDGET_FOR_MINIMUMS:{campaign_id}")
            else:
                output["execution_status"] = "EXECUTABLE"
        else:
            campaign_budget = None
            output["execution_status"] = "BUDGET_BASELINE_NOT_PROVIDED"

        group_share = campaign_share / count
        groups: list[dict[str, Any]] = []
        for position in range(1, count + 1):
            slot_id = f"{campaign_id}_NEW_AG_{position:02d}"
            if slot_id in historical_ad_groups[campaign_id]:
                raise BudgetRecommendationError(
                    f"new Ad Group slot ID collides with historical ad_group_id {slot_id}"
                )
            ad_group: dict[str, Any] = {
                "ad_group_slot_id": slot_id,
                "allocation_basis": ALLOCATION_BASIS,
                "budget_seed_share": group_share,
            }
            if has_budget:
                ad_group["initial_daily_budget"] = group_share * (total_budget or 0.0)
            groups.append(ad_group)
        output["recommended_ad_groups"] = groups
        campaign_outputs.append(output)

    source = request.get("mta_source")
    if not isinstance(source, dict):
        raise BudgetRecommendationError("mta_source must be an object")
    snapshot_fields = (
        "report_start_date",
        "report_end_date",
        "marketplace",
        "advertiser_id",
        "attribution_sha256",
        "entity_sha256",
    )
    snapshot = {
        field: _required_text(source.get(field), f"mta_source.{field}")
        for field in snapshot_fields
    }
    result: dict[str, Any] = {
        "schema_version": SUPPORTED_SAMPLE_VERSION,
        "campaign_group_id": group["campaign_group_id"],
        "candidate_pool_id": request["candidate_pool_id"],
        "mta_batch_id": _required_text(request.get("mta_batch_id"), "mta_batch_id"),
        "recommendation_type": "INITIAL_SEED",
        "handoff_status": "READY_FOR_OPTIMIZATION",
        "is_optimized": False,
        "mta_source_snapshot": snapshot,
        "budget_derivation": {
            "formula_version": FORMULA_VERSION,
            "normalization_universe": NORMALIZATION_UNIVERSE,
            "outcome_weights": dict(weights),
            "attribution_touchpoint_count": touchpoint_count,
            "entity_row_count": len(entity_rows),
            "bridge_fallback_order": [
                "ASSISTED_OUTCOME",
                "CLICKS",
                "IMPRESSIONS",
                "UNIQUE_USERS",
                "EQUAL",
            ],
            "mta_value_policy": MTA_VALUE_POLICY,
            "reliability_status_counts": dict(sorted(reliability_counts.items())),
            "campaign_score_total": score_total,
        },
        "warnings": warnings,
        "campaigns": campaign_outputs,
    }
    if has_budget:
        result["budget_seed_total"] = total_budget
    return result
