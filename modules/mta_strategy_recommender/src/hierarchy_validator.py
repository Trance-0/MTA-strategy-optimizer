from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


EXPECTED_CAMPAIGN_COUNT = 4
SUPPORTED_SAMPLE_VERSION = "2.0"
ALLOWED_MATCH_TYPES = {"EXACT", "PHRASE", "BROAD"}
ALLOWED_CANDIDATE_SOURCES = {"EXISTING", "VALIDATED", "EXPLORATION"}
ALLOWED_PAIR_TYPES = {"EXISTING", "VALIDATED", "EXPLORATION", "BLOCKED"}
ASSIGNABLE_PAIR_TYPES = ALLOWED_PAIR_TYPES - {"BLOCKED"}
REQUIRED_INPUT_FILES = ("strategy_request.json", "candidate_pool.json")


class HierarchyValidationError(ValueError):
    """Raised when a hierarchy sample violates the initializer contract."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise HierarchyValidationError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HierarchyValidationError(f"{path}: top-level value must be an object")
    return value


def _required_text(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise HierarchyValidationError(f"{context} must be a non-empty string")
    text = value.strip()
    if not text:
        raise HierarchyValidationError(f"{context} is required")
    if text != value:
        raise HierarchyValidationError(f"{context} must not contain surrounding whitespace")
    return text


def _bool(value: object, context: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise HierarchyValidationError(f"{context} must be boolean")


def _number(value: object, context: str) -> float:
    if isinstance(value, bool):
        raise HierarchyValidationError(f"{context} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HierarchyValidationError(f"{context} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise HierarchyValidationError(f"{context} must be finite and non-negative")
    return number


def _integer(value: object, context: str, *, minimum: int) -> int:
    number = _number(value, context)
    if not number.is_integer() or number < minimum:
        raise HierarchyValidationError(
            f"{context} must be an integer greater than or equal to {minimum}"
        )
    return int(number)


def _object_list(value: object, context: str, *, nonempty: bool = True) -> list[dict[str, Any]]:
    if not isinstance(value, list) or (nonempty and not value):
        suffix = "a non-empty list" if nonempty else "a list"
        raise HierarchyValidationError(f"{context} must be {suffix}")
    if any(not isinstance(item, dict) for item in value):
        raise HierarchyValidationError(f"{context} must contain only objects")
    return value


def _unique_index(rows: list[dict[str, Any]], key: str, context: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows, start=1):
        value = _required_text(row.get(key), f"{context}[{position}].{key}")
        if value in result:
            raise HierarchyValidationError(f"{context}: duplicate {key} {value}")
        result[value] = row
    return result


def _allowed_match_types(value: object, keyword_id: str) -> set[str]:
    if not isinstance(value, list) or not value:
        raise HierarchyValidationError(f"keyword {keyword_id} allowed_match_types must be a non-empty list")
    allowed = {_required_text(item, f"keyword {keyword_id} allowed_match_types") for item in value}
    if len(allowed) != len(value):
        raise HierarchyValidationError(f"keyword {keyword_id} repeats an allowed match type")
    invalid = allowed - ALLOWED_MATCH_TYPES
    if invalid:
        raise HierarchyValidationError(
            f"keyword {keyword_id} has unsupported match type(s): {sorted(invalid)}"
        )
    return allowed


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-8)


def validate_simulated_hierarchy(
    data_dir: str | Path,
    recommendation_path: str | Path,
) -> dict[str, Any]:
    root = Path(data_dir)
    missing = [name for name in REQUIRED_INPUT_FILES if not (root / name).is_file()]
    if missing:
        raise HierarchyValidationError(f"missing required sample file(s): {', '.join(missing)}")
    expected_entries = {*REQUIRED_INPUT_FILES, "README.md"}
    unexpected_entries = sorted(
        str(path.relative_to(root))
        for path in root.iterdir()
        if path.name not in expected_entries
    )
    if unexpected_entries:
        raise HierarchyValidationError(
            "expected-output or unrelated content must not be stored in the input directory: "
            + ", ".join(unexpected_entries)
        )
    recommendation_file = Path(recommendation_path)
    if not recommendation_file.is_file():
        raise HierarchyValidationError(f"missing recommendation fixture: {recommendation_file}")

    request = _read_json(root / "strategy_request.json")
    pool = _read_json(root / "candidate_pool.json")
    recommendation = _read_json(recommendation_file)

    request_version = _required_text(request.get("sample_version"), "strategy_request.sample_version")
    pool_version = _required_text(pool.get("sample_version"), "candidate_pool.sample_version")
    if request_version != SUPPORTED_SAMPLE_VERSION or pool_version != request_version:
        raise HierarchyValidationError(
            f"sample_version must match supported version {SUPPORTED_SAMPLE_VERSION}"
        )

    group = request.get("campaign_group")
    if not isinstance(group, dict):
        raise HierarchyValidationError("strategy_request.json: campaign_group must be an object")
    group_id = _required_text(group.get("campaign_group_id"), "campaign_group_id")
    for field in ("platform", "marketplace", "advertiser_id", "currency"):
        _required_text(group.get(field), f"campaign_group.{field}")
    pool_id = _required_text(request.get("candidate_pool_id"), "strategy_request.candidate_pool_id")
    mta_batch_id = _required_text(request.get("mta_batch_id"), "strategy_request.mta_batch_id")

    campaigns = _object_list(request.get("campaigns"), "strategy_request.campaigns")
    campaign_index = _unique_index(campaigns, "campaign_id", "campaigns")
    if len(campaign_index) != EXPECTED_CAMPAIGN_COUNT:
        raise HierarchyValidationError(
            f"campaign_group {group_id} must contain exactly {EXPECTED_CAMPAIGN_COUNT} campaigns; "
            f"found {len(campaign_index)}"
        )
    for campaign_id, row in campaign_index.items():
        _required_text(row.get("campaign_name"), f"campaign {campaign_id} campaign_name")
        ad_product = _required_text(row.get("ad_product"), f"campaign {campaign_id} ad_product")
        if any(separator in ad_product for separator in ("|", ",", ";")):
            raise HierarchyValidationError(f"campaign {campaign_id} ad_product must be one scalar value")
        if str(row.get("status", "")).lower() != "enabled":
            raise HierarchyValidationError(f"campaign {campaign_id} must be enabled")
        _required_text(row.get("targeting"), f"campaign {campaign_id} targeting")

    weights = request.get("outcome_weights")
    if not isinstance(weights, dict) or set(weights) != {"converted_users", "purchase_count", "revenue"}:
        raise HierarchyValidationError("outcome_weights must contain converted_users, purchase_count and revenue")
    if not _close(sum(_number(value, f"outcome_weights.{name}") for name, value in weights.items()), 1.0):
        raise HierarchyValidationError("outcome_weights must sum to 1")

    constraints = request.get("ad_group_constraints")
    if not isinstance(constraints, dict):
        raise HierarchyValidationError("ad_group_constraints must be an object")
    min_keywords = _integer(constraints.get("min_keywords"), "ad_group_constraints.min_keywords", minimum=1)
    max_keywords = _integer(constraints.get("max_keywords"), "ad_group_constraints.max_keywords", minimum=1)
    min_skus = _integer(constraints.get("min_skus"), "ad_group_constraints.min_skus", minimum=1)
    max_skus = _integer(constraints.get("max_skus"), "ad_group_constraints.max_skus", minimum=1)
    max_ad_groups = _integer(
        constraints.get("max_ad_groups_per_campaign"),
        "ad_group_constraints.max_ad_groups_per_campaign",
        minimum=1,
    )
    max_exploration_groups = _integer(
        constraints.get("max_exploration_groups_per_campaign"),
        "ad_group_constraints.max_exploration_groups_per_campaign",
        minimum=0,
    )
    if min_keywords > max_keywords or min_skus > max_skus:
        raise HierarchyValidationError("ad_group_constraints minimum cannot exceed maximum")

    if pool.get("candidate_pool_id") != pool_id:
        raise HierarchyValidationError("candidate_pool.json candidate_pool_id does not match strategy request")
    if pool.get("campaign_group_id") != group_id:
        raise HierarchyValidationError("candidate_pool.json campaign_group_id does not match strategy request")
    keyword_rows = _object_list(pool.get("keywords"), "candidate_pool.keywords")
    sku_rows = _object_list(pool.get("skus"), "candidate_pool.skus")
    pair_rows = _object_list(pool.get("pair_rules"), "candidate_pool.pair_rules")
    keyword_index = _unique_index(keyword_rows, "keyword_id", "candidate_pool.keywords")
    sku_index = _unique_index(sku_rows, "sku_id", "candidate_pool.skus")
    keyword_match_types: dict[str, set[str]] = {}
    for keyword_id, row in keyword_index.items():
        _required_text(row.get("keyword_text"), f"keyword {keyword_id} keyword_text")
        _required_text(row.get("intent"), f"keyword {keyword_id} intent")
        source = _required_text(row.get("source"), f"keyword {keyword_id} source")
        if source not in ALLOWED_CANDIDATE_SOURCES:
            raise HierarchyValidationError(f"keyword {keyword_id} has unsupported source {source}")
        _bool(row.get("eligible"), f"keyword {keyword_id} eligible")
        keyword_match_types[keyword_id] = _allowed_match_types(row.get("allowed_match_types"), keyword_id)
    for sku_id, row in sku_index.items():
        for field in ("product_id", "brand", "category", "segment"):
            _required_text(row.get(field), f"sku {sku_id} {field}")
        source = _required_text(row.get("source"), f"sku {sku_id} source")
        if source not in ALLOWED_CANDIDATE_SOURCES:
            raise HierarchyValidationError(f"sku {sku_id} has unsupported source {source}")
        _bool(row.get("eligible"), f"sku {sku_id} eligible")
        for field in ("inventory_available", "paid_search_enabled", "scope_for_search_optimization"):
            if not _bool(row.get(field), f"sku {sku_id} {field}"):
                raise HierarchyValidationError(f"sku {sku_id} is not executable: {field} is false")

    pair_index: dict[tuple[str, str], dict[str, Any]] = {}
    for position, row in enumerate(pair_rows, start=1):
        keyword_id = _required_text(row.get("keyword_id"), f"pair_rules[{position}].keyword_id")
        sku_id = _required_text(row.get("sku_id"), f"pair_rules[{position}].sku_id")
        if keyword_id not in keyword_index or sku_id not in sku_index:
            raise HierarchyValidationError(f"pair {keyword_id}/{sku_id} references an item outside the candidate pool")
        relationship = _required_text(
            row.get("relationship_type"), f"pair {keyword_id}/{sku_id} relationship_type"
        )
        if relationship not in ALLOWED_PAIR_TYPES:
            raise HierarchyValidationError(f"pair {keyword_id}/{sku_id} has unsupported relationship_type {relationship}")
        key = (keyword_id, sku_id)
        if key in pair_index:
            raise HierarchyValidationError(f"duplicate keyword/SKU pair {keyword_id}/{sku_id}")
        pair_index[key] = row

    budget_value = group.get("total_daily_budget")
    has_budget_baseline = budget_value not in (None, "")
    total_daily_budget = _number(budget_value, "campaign_group.total_daily_budget") if has_budget_baseline else None

    if recommendation.get("campaign_group_id") != group_id:
        raise HierarchyValidationError("recommendation campaign_group_id does not match input")
    if recommendation.get("candidate_pool_id") != pool_id or recommendation.get("mta_batch_id") != mta_batch_id:
        raise HierarchyValidationError("recommendation lineage does not match candidate pool or MTA batch")
    if recommendation.get("recommendation_type") != "INITIAL_SEED":
        raise HierarchyValidationError("recommendation_type must be INITIAL_SEED")
    if recommendation.get("handoff_status") != "READY_FOR_OPTIMIZATION":
        raise HierarchyValidationError("handoff_status must be READY_FOR_OPTIMIZATION")
    if _bool(recommendation.get("is_optimized"), "recommendation.is_optimized"):
        raise HierarchyValidationError("initial strategy must not claim to be optimized")

    recommendation_campaigns = _object_list(recommendation.get("campaigns"), "recommendation.campaigns")
    recommended_ids = [
        _required_text(item.get("campaign_id"), "recommendation campaign_id")
        for item in recommendation_campaigns
    ]
    if len(recommended_ids) != len(set(recommended_ids)) or set(recommended_ids) != set(campaign_index):
        raise HierarchyValidationError("recommendation must contain every input campaign exactly once")

    seen_ad_groups: set[str] = set()
    keyword_match_by_campaign: set[tuple[str, str, str]] = set()
    total_share = 0.0
    total_amount = 0.0
    ad_group_count = 0
    for campaign_output in recommendation_campaigns:
        campaign_id = _required_text(
            campaign_output.get("campaign_id"), "recommendation campaign_id"
        )
        if "ad_product" in campaign_output:
            raise HierarchyValidationError(
                f"recommendation campaign {campaign_id} must inherit ad_product from strategy_request.json"
            )
        campaign_share = _number(
            campaign_output.get("budget_seed_share"), f"campaign {campaign_id} budget_seed_share"
        )
        groups = _object_list(
            campaign_output.get("recommended_ad_groups"), f"campaign {campaign_id} recommended_ad_groups"
        )
        if len(groups) > max_ad_groups:
            raise HierarchyValidationError(
                f"campaign {campaign_id} exceeds max_ad_groups_per_campaign"
            )
        exploration_group_count = 0
        group_share = 0.0
        group_amount = 0.0
        for ad_group in groups:
            ad_group_id = _required_text(ad_group.get("ad_group_id"), f"campaign {campaign_id} ad_group_id")
            if ad_group_id in seen_ad_groups:
                raise HierarchyValidationError(f"duplicate ad_group_id {ad_group_id}")
            seen_ad_groups.add(ad_group_id)
            if "ad_product" in ad_group:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must inherit ad_product from its Campaign")
            if ad_group.get("source_candidate_pool_id") != pool_id:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} candidate pool lineage does not match")
            _required_text(ad_group.get("strategy_name"), f"Ad Group {ad_group_id} strategy_name")
            strategy_role = _required_text(
                ad_group.get("strategy_role"), f"Ad Group {ad_group_id} strategy_role"
            )
            exploration_group_count += strategy_role == "EXPLORATION"
            reason_codes = ad_group.get("reason_codes")
            if not isinstance(reason_codes, list) or not reason_codes:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must contain reason_codes")
            normalized_reason_codes: set[str] = set()
            for reason_code in reason_codes:
                normalized_reason_codes.add(
                    _required_text(reason_code, f"Ad Group {ad_group_id} reason_code")
                )
            confidence = _number(ad_group.get("confidence"), f"Ad Group {ad_group_id} confidence")
            if confidence > 1:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} confidence must be between 0 and 1")
            evidence = _object_list(ad_group.get("mta_evidence"), f"Ad Group {ad_group_id} MTA evidence")
            expected_ad_product = _required_text(
                campaign_index[campaign_id].get("ad_product"), f"campaign {campaign_id} ad_product"
            )
            for item in evidence:
                touchpoint = _required_text(item.get("touchpoint"), f"Ad Group {ad_group_id} evidence touchpoint")
                touchpoint_parts = touchpoint.split(":")
                if (
                    len(touchpoint_parts) != 5
                    or any(not part.strip() or part != part.strip() for part in touchpoint_parts)
                    or touchpoint_parts[0] != expected_ad_product
                ):
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} MTA touchpoint is not a compatible five-part key"
                    )
                outcomes = item.get("outcomes")
                if not isinstance(outcomes, list) or not outcomes:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} evidence must name outcomes")
                for outcome in outcomes:
                    outcome = _required_text(
                        outcome, f"Ad Group {ad_group_id} evidence outcome"
                    )
                    if outcome not in {"converted_users", "purchase_count", "revenue"}:
                        raise HierarchyValidationError(f"Ad Group {ad_group_id} has unsupported MTA outcome {outcome}")
            ad_group_count += 1
            share = _number(ad_group.get("budget_seed_share"), f"Ad Group {ad_group_id} budget_seed_share")
            group_share += share

            keywords = _object_list(ad_group.get("keywords"), f"Ad Group {ad_group_id} keywords")
            skus = _object_list(ad_group.get("skus"), f"Ad Group {ad_group_id} skus")
            pairings = _object_list(ad_group.get("pairings"), f"Ad Group {ad_group_id} pairings")
            if not min_keywords <= len(keywords) <= max_keywords:
                raise HierarchyValidationError(
                    f"Ad Group {ad_group_id} keyword count violates capacity constraints"
                )
            if not min_skus <= len(skus) <= max_skus:
                raise HierarchyValidationError(
                    f"Ad Group {ad_group_id} SKU count violates capacity constraints"
                )
            assigned_keywords: set[str] = set()
            assigned_keyword_matches: set[tuple[str, str]] = set()
            assigned_skus: set[str] = set()
            for keyword in keywords:
                keyword_id = _required_text(keyword.get("keyword_id"), f"Ad Group {ad_group_id} keyword_id")
                match_type = _required_text(keyword.get("match_type"), f"Ad Group {ad_group_id} match_type")
                if keyword_id not in keyword_index or not _bool(
                    keyword_index[keyword_id].get("eligible"), f"keyword {keyword_id} eligible"
                ):
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} references Keyword outside the eligible pool: {keyword_id}"
                    )
                if match_type not in keyword_match_types[keyword_id]:
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} uses unsupported match type {match_type} for {keyword_id}"
                    )
                duplicate_key = (campaign_id, keyword_id, match_type)
                if duplicate_key in keyword_match_by_campaign:
                    raise HierarchyValidationError(
                        f"campaign {campaign_id} repeats Keyword/match type {keyword_id}/{match_type}"
                    )
                keyword_match_by_campaign.add(duplicate_key)
                assigned_keywords.add(keyword_id)
                assigned_keyword_matches.add((keyword_id, match_type))
            for sku in skus:
                sku_id = _required_text(sku.get("sku_id"), f"Ad Group {ad_group_id} sku_id")
                if sku_id in assigned_skus:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} repeats SKU {sku_id}")
                if sku_id not in sku_index or not _bool(sku_index[sku_id].get("eligible"), f"sku {sku_id} eligible"):
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} references SKU outside the eligible pool: {sku_id}"
                    )
                assigned_skus.add(sku_id)
            paired_keywords: set[str] = set()
            paired_keyword_matches: set[tuple[str, str]] = set()
            paired_skus: set[str] = set()
            seen_pairings: set[tuple[str, str, str]] = set()
            uses_exploration_pair = False
            for pairing in pairings:
                pair = (
                    _required_text(pairing.get("keyword_id"), "pairing keyword_id"),
                    _required_text(pairing.get("sku_id"), "pairing sku_id"),
                )
                pairing_match_type = _required_text(pairing.get("match_type"), "pairing match_type")
                pairing_key = (pair[0], pair[1], pairing_match_type)
                if pairing_key in seen_pairings:
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} repeats pairing {pair[0]}/{pair[1]}/{pairing_match_type}"
                    )
                seen_pairings.add(pairing_key)
                if pair[0] not in assigned_keywords or pair[1] not in assigned_skus:
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} pairing references an unassigned Keyword or SKU"
                    )
                if not any(
                    keyword.get("keyword_id") == pair[0] and keyword.get("match_type") == pairing_match_type
                    for keyword in keywords
                ):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} pairing references an unassigned match type")
                source_pair = pair_index.get(pair)
                if source_pair is None or source_pair["relationship_type"] not in ASSIGNABLE_PAIR_TYPES:
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} uses a missing or BLOCKED pair {pair[0]}/{pair[1]}"
                    )
                uses_exploration_pair = (
                    uses_exploration_pair
                    or source_pair["relationship_type"] == "EXPLORATION"
                )
                paired_keywords.add(pair[0])
                paired_keyword_matches.add((pair[0], pairing_match_type))
                paired_skus.add(pair[1])
            if (
                paired_keywords != assigned_keywords
                or paired_keyword_matches != assigned_keyword_matches
                or paired_skus != assigned_skus
            ):
                raise HierarchyValidationError(f"Ad Group {ad_group_id} has unpaired Keyword or SKU assignments")
            if uses_exploration_pair and (
                strategy_role != "EXPLORATION"
                or "CONTROLLED_EXPLORATION_PAIR" not in normalized_reason_codes
            ):
                raise HierarchyValidationError(
                    f"Ad Group {ad_group_id} must label exploration pairs as controlled EXPLORATION"
                )
            if strategy_role == "EXPLORATION" and not uses_exploration_pair:
                raise HierarchyValidationError(
                    f"Ad Group {ad_group_id} claims EXPLORATION without an exploration pair"
                )
            if "CONTROLLED_EXPLORATION_PAIR" in normalized_reason_codes and not uses_exploration_pair:
                raise HierarchyValidationError(
                    f"Ad Group {ad_group_id} claims controlled exploration without an exploration pair"
                )

            if has_budget_baseline:
                amount = _number(ad_group.get("initial_daily_budget"), f"Ad Group {ad_group_id} initial_daily_budget")
                if not _close(amount, share * (total_daily_budget or 0.0)):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} amount does not match its Group share")
                group_amount += amount
            elif "initial_daily_budget" in ad_group:
                raise HierarchyValidationError("no total daily budget: absolute Ad Group budget must be omitted")

        if exploration_group_count > max_exploration_groups:
            raise HierarchyValidationError(
                f"campaign {campaign_id} exceeds max_exploration_groups_per_campaign"
            )

        if not _close(group_share, campaign_share):
            raise HierarchyValidationError(f"campaign {campaign_id} Ad Group shares do not sum to campaign share")
        if has_budget_baseline:
            campaign_amount = _number(
                campaign_output.get("campaign_budget_seed"), f"campaign {campaign_id} campaign_budget_seed"
            )
            if not _close(campaign_amount, group_amount) or not _close(
                campaign_amount, campaign_share * (total_daily_budget or 0.0)
            ):
                raise HierarchyValidationError(f"campaign {campaign_id} budget is not conserved")
            total_amount += campaign_amount
        elif "campaign_budget_seed" in campaign_output:
            raise HierarchyValidationError("no total daily budget: absolute Campaign budget must be omitted")
        total_share += campaign_share

    if not _close(total_share, 1.0):
        raise HierarchyValidationError("Campaign budget shares must sum to 1")
    warnings: list[str] = []
    if has_budget_baseline:
        total = _number(recommendation.get("budget_seed_total"), "recommendation.budget_seed_total")
        if not _close(total, total_daily_budget or 0.0) or not _close(total_amount, total):
            raise HierarchyValidationError("Ad Group, Campaign and Campaign Group budgets must be conserved")
    else:
        if "budget_seed_total" in recommendation:
            raise HierarchyValidationError("no total daily budget: absolute Group budget must be omitted")
        warnings.append("NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY")

    return {
        "campaign_group_id": group_id,
        "campaign_count": len(campaign_index),
        "recommended_ad_group_count": ad_group_count,
        "keyword_count": len(keyword_index),
        "sku_count": len(sku_index),
        "pair_count": len(pair_index),
        "has_budget_baseline": has_budget_baseline,
        "recommendation_type": "INITIAL_SEED",
        "warnings": warnings,
    }
