from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


EXPECTED_CAMPAIGN_COUNT = 4
ALLOWED_PAIR_TYPES = {"EXISTING", "VALIDATED", "EXPLORATION", "BLOCKED"}
ASSIGNABLE_PAIR_TYPES = ALLOWED_PAIR_TYPES - {"BLOCKED"}
REQUIRED_FILES = {
    "campaign_group": "campaign_group.json",
    "campaigns": "campaigns.csv",
    "campaign_group_relationships": "campaign_group_relationships.csv",
    "keywords": "candidate_keywords.csv",
    "skus": "candidate_skus.csv",
    "pairs": "eligible_keyword_sku_pairs.csv",
    "recommendation": "initial_recommendation.json",
}


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise HierarchyValidationError(f"{path}: CSV header is missing")
            return [
                {key: (value or "").strip() for key, value in row.items()}
                for row in reader
            ]
    except OSError as exc:
        raise HierarchyValidationError(f"cannot read {path}: {exc}") from exc


def _required_text(value: object, context: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise HierarchyValidationError(f"{context} is required")
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


def _unique_index(rows: list[dict[str, str]], key: str, context: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        value = _required_text(row.get(key), f"{context} row {row_number} {key}")
        if value in result:
            raise HierarchyValidationError(f"{context}: duplicate {key} {value}")
        result[value] = row
    return result


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-8)


def validate_simulated_hierarchy(data_dir: str | Path) -> dict[str, Any]:
    root = Path(data_dir)
    missing = [name for name in REQUIRED_FILES.values() if not (root / name).is_file()]
    if missing:
        raise HierarchyValidationError(f"missing required sample file(s): {', '.join(missing)}")

    envelope = _read_json(root / REQUIRED_FILES["campaign_group"])
    group = envelope.get("campaign_group")
    if not isinstance(group, dict):
        raise HierarchyValidationError("campaign_group.json: campaign_group must be an object")
    group_id = _required_text(group.get("campaign_group_id"), "campaign_group_id")
    for field in ("platform", "marketplace", "advertiser_id", "currency"):
        _required_text(group.get(field), f"campaign_group.{field}")
    pool_id = _required_text(envelope.get("candidate_pool_id"), "candidate_pool_id")
    mta_batch_id = _required_text(envelope.get("mta_batch_id"), "mta_batch_id")

    campaigns = _read_csv(root / REQUIRED_FILES["campaigns"])
    campaign_index = _unique_index(campaigns, "campaign_id", "campaigns")
    relationship_rows = _read_csv(root / REQUIRED_FILES["campaign_group_relationships"])
    related_campaign_ids: list[str] = []
    seen_relationships: set[tuple[str, str]] = set()
    for row_number, row in enumerate(relationship_rows, start=2):
        relationship_group_id = _required_text(
            row.get("campaign_group_id"), f"campaign_group_relationships row {row_number} campaign_group_id"
        )
        relationship_campaign_id = _required_text(
            row.get("campaign_id"), f"campaign_group_relationships row {row_number} campaign_id"
        )
        relationship_key = (relationship_group_id, relationship_campaign_id)
        if relationship_key in seen_relationships:
            raise HierarchyValidationError(
                f"duplicate Campaign Group/Campaign relationship {relationship_group_id}/{relationship_campaign_id}"
            )
        seen_relationships.add(relationship_key)
        if relationship_campaign_id not in campaign_index:
            raise HierarchyValidationError(
                f"Campaign Group relationship references unknown campaign {relationship_campaign_id}"
            )
        if relationship_group_id == group_id:
            related_campaign_ids.append(relationship_campaign_id)
    if len(related_campaign_ids) != EXPECTED_CAMPAIGN_COUNT or len(set(related_campaign_ids)) != EXPECTED_CAMPAIGN_COUNT:
        raise HierarchyValidationError(
            f"campaign_group {group_id} must contain exactly {EXPECTED_CAMPAIGN_COUNT} campaigns; "
            f"found {len(set(related_campaign_ids))}"
        )
    if set(related_campaign_ids) != set(campaign_index):
        raise HierarchyValidationError("sample campaigns must all be related to the current Campaign Group")
    for campaign_id, row in campaign_index.items():
        ad_product = _required_text(row.get("ad_product"), f"campaign {campaign_id} ad_product")
        if any(separator in ad_product for separator in ("|", ",", ";")):
            raise HierarchyValidationError(f"campaign {campaign_id} ad_product must be one scalar value")
        if row.get("status", "").lower() != "enabled":
            raise HierarchyValidationError(f"campaign {campaign_id} must be enabled")

    keyword_rows = _read_csv(root / REQUIRED_FILES["keywords"])
    sku_rows = _read_csv(root / REQUIRED_FILES["skus"])
    keyword_index = _unique_index(keyword_rows, "keyword_id", "candidate_keywords")
    sku_index = _unique_index(sku_rows, "sku_id", "candidate_skus")
    for kind, indexed in (("keyword", keyword_index), ("sku", sku_index)):
        for item_id, row in indexed.items():
            if row.get("campaign_group_id") != group_id:
                raise HierarchyValidationError(f"{kind} {item_id} belongs to a different campaign_group_id")
            if row.get("candidate_pool_id") != pool_id:
                raise HierarchyValidationError(f"{kind} {item_id} belongs to a different candidate_pool_id")
            _bool(row.get("eligible"), f"{kind} {item_id} eligible")
            if kind == "sku":
                for field in ("inventory_available", "paid_search_enabled", "scope_for_search_optimization"):
                    if not _bool(row.get(field), f"sku {item_id} {field}"):
                        raise HierarchyValidationError(f"sku {item_id} is not executable: {field} is false")

    pair_rows = _read_csv(root / REQUIRED_FILES["pairs"])
    pair_index: dict[tuple[str, str], dict[str, str]] = {}
    for row_number, row in enumerate(pair_rows, start=2):
        keyword_id = _required_text(row.get("keyword_id"), f"pair row {row_number} keyword_id")
        sku_id = _required_text(row.get("sku_id"), f"pair row {row_number} sku_id")
        if row.get("campaign_group_id") != group_id:
            raise HierarchyValidationError(f"pair {keyword_id}/{sku_id} belongs to a different campaign_group_id")
        if row.get("candidate_pool_id") != pool_id:
            raise HierarchyValidationError(f"pair {keyword_id}/{sku_id} belongs to a different candidate_pool_id")
        if keyword_id not in keyword_index or sku_id not in sku_index:
            raise HierarchyValidationError(f"pair {keyword_id}/{sku_id} references an item outside the candidate pool")
        relationship = _required_text(row.get("relationship_type"), f"pair {keyword_id}/{sku_id} relationship_type")
        if relationship not in ALLOWED_PAIR_TYPES:
            raise HierarchyValidationError(f"pair {keyword_id}/{sku_id} has unsupported relationship_type {relationship}")
        key = (keyword_id, sku_id)
        if key in pair_index:
            raise HierarchyValidationError(f"duplicate keyword/SKU pair {keyword_id}/{sku_id}")
        pair_index[key] = row

    historical_path = root / "historical_budgets.csv"
    historical_rows = _read_csv(historical_path) if historical_path.is_file() else []
    budget_baseline_value = group.get("budget_baseline")
    has_budget_baseline = budget_baseline_value not in (None, "")
    budget_baseline = _number(budget_baseline_value, "campaign_group.budget_baseline") if has_budget_baseline else None
    if historical_rows and not has_budget_baseline:
        raise HierarchyValidationError("historical_budgets.csv requires campaign_group.budget_baseline")
    if historical_rows:
        historical_index = _unique_index(historical_rows, "campaign_id", "historical_budgets")
        if set(historical_index) != set(campaign_index):
            raise HierarchyValidationError("historical_budgets must contain every campaign exactly once")
        if any(row.get("campaign_group_id") != group_id for row in historical_rows):
            raise HierarchyValidationError("historical_budgets contains a different campaign_group_id")
        historical_share = sum(_number(row.get("historical_budget_share"), "historical_budget_share") for row in historical_rows)
        historical_amount = sum(_number(row.get("current_daily_budget"), "current_daily_budget") for row in historical_rows)
        if not _close(historical_share, 1.0) or not _close(historical_amount, budget_baseline or 0.0):
            raise HierarchyValidationError("historical campaign budgets must conserve Group share and amount")

    recommendation = _read_json(root / REQUIRED_FILES["recommendation"])
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

    recommendation_campaigns = recommendation.get("campaigns")
    if not isinstance(recommendation_campaigns, list):
        raise HierarchyValidationError("recommendation.campaigns must be a list")
    recommended_ids = [_required_text(item.get("campaign_id") if isinstance(item, dict) else None, "recommendation campaign_id") for item in recommendation_campaigns]
    if len(recommended_ids) != len(set(recommended_ids)) or set(recommended_ids) != set(campaign_index):
        raise HierarchyValidationError("recommendation must contain every input campaign exactly once")

    seen_ad_groups: set[str] = set()
    keyword_match_by_campaign: set[tuple[str, str, str]] = set()
    total_share = 0.0
    total_amount = 0.0
    ad_group_count = 0
    for campaign_output in recommendation_campaigns:
        campaign_id = campaign_output["campaign_id"]
        if "ad_product" in campaign_output:
            raise HierarchyValidationError(f"recommendation campaign {campaign_id} must inherit ad_product from campaigns.csv")
        campaign_share = _number(campaign_output.get("budget_seed_share"), f"campaign {campaign_id} budget_seed_share")
        groups = campaign_output.get("recommended_ad_groups")
        if not isinstance(groups, list) or not groups:
            raise HierarchyValidationError(f"campaign {campaign_id} must contain recommended_ad_groups")
        group_share = 0.0
        group_amount = 0.0
        for ad_group in groups:
            if not isinstance(ad_group, dict):
                raise HierarchyValidationError(f"campaign {campaign_id} has a non-object Ad Group")
            ad_group_id = _required_text(ad_group.get("ad_group_id"), f"campaign {campaign_id} ad_group_id")
            if ad_group_id in seen_ad_groups:
                raise HierarchyValidationError(f"duplicate ad_group_id {ad_group_id}")
            seen_ad_groups.add(ad_group_id)
            if "ad_product" in ad_group:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must inherit ad_product from its Campaign")
            if ad_group.get("source_candidate_pool_id") != pool_id:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} candidate pool lineage does not match")
            reason_codes = ad_group.get("reason_codes")
            if not isinstance(reason_codes, list) or not reason_codes:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must contain reason_codes")
            for reason_code in reason_codes:
                _required_text(reason_code, f"Ad Group {ad_group_id} reason_code")
            confidence = _number(ad_group.get("confidence"), f"Ad Group {ad_group_id} confidence")
            if confidence > 1:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} confidence must be between 0 and 1")
            evidence = ad_group.get("mta_evidence")
            if not isinstance(evidence, list) or not evidence:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must contain MTA evidence")
            expected_ad_product = campaign_index[campaign_id]["ad_product"]
            for item in evidence:
                if not isinstance(item, dict):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} has invalid MTA evidence")
                touchpoint = _required_text(item.get("touchpoint"), f"Ad Group {ad_group_id} evidence touchpoint")
                if len(touchpoint.split(":")) != 5 or touchpoint.split(":", 1)[0] != expected_ad_product:
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} MTA touchpoint is not a compatible five-part key"
                    )
                outcomes = item.get("outcomes")
                if not isinstance(outcomes, list) or not outcomes:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} evidence must name outcomes")
                for outcome in outcomes:
                    if outcome not in {"converted_users", "purchase_count", "revenue"}:
                        raise HierarchyValidationError(f"Ad Group {ad_group_id} has unsupported MTA outcome {outcome}")
            ad_group_count += 1
            share = _number(ad_group.get("budget_seed_share"), f"Ad Group {ad_group_id} budget_seed_share")
            group_share += share

            keywords = ad_group.get("keywords")
            skus = ad_group.get("skus")
            pairings = ad_group.get("pairings")
            if not isinstance(keywords, list) or not keywords or not isinstance(skus, list) or not skus:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must contain parallel Keyword and SKU lists")
            if not isinstance(pairings, list) or not pairings:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must contain explicit pairings")
            assigned_keywords: set[str] = set()
            assigned_skus: set[str] = set()
            for keyword in keywords:
                if not isinstance(keyword, dict):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} has an invalid Keyword assignment")
                keyword_id = _required_text(keyword.get("keyword_id"), f"Ad Group {ad_group_id} keyword_id")
                match_type = _required_text(keyword.get("match_type"), f"Ad Group {ad_group_id} match_type")
                if keyword_id not in keyword_index or not _bool(keyword_index[keyword_id].get("eligible"), f"keyword {keyword_id} eligible"):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} references Keyword outside the eligible pool: {keyword_id}")
                allowed = set(filter(None, keyword_index[keyword_id].get("allowed_match_types", "").split("|")))
                if match_type not in allowed:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} uses unsupported match type {match_type} for {keyword_id}")
                duplicate_key = (campaign_id, keyword_id, match_type)
                if duplicate_key in keyword_match_by_campaign:
                    raise HierarchyValidationError(f"campaign {campaign_id} repeats Keyword/match type {keyword_id}/{match_type}")
                keyword_match_by_campaign.add(duplicate_key)
                assigned_keywords.add(keyword_id)
            for sku in skus:
                if not isinstance(sku, dict):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} has an invalid SKU assignment")
                sku_id = _required_text(sku.get("sku_id"), f"Ad Group {ad_group_id} sku_id")
                if sku_id in assigned_skus:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} repeats SKU {sku_id}")
                if sku_id not in sku_index or not _bool(sku_index[sku_id].get("eligible"), f"sku {sku_id} eligible"):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} references SKU outside the eligible pool: {sku_id}")
                assigned_skus.add(sku_id)
            paired_keywords: set[str] = set()
            paired_skus: set[str] = set()
            seen_pairings: set[tuple[str, str, str]] = set()
            for pairing in pairings:
                if not isinstance(pairing, dict):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} has an invalid pairing")
                pair = (_required_text(pairing.get("keyword_id"), "pairing keyword_id"), _required_text(pairing.get("sku_id"), "pairing sku_id"))
                pairing_match_type = _required_text(pairing.get("match_type"), "pairing match_type")
                pairing_key = (pair[0], pair[1], pairing_match_type)
                if pairing_key in seen_pairings:
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} repeats pairing {pair[0]}/{pair[1]}/{pairing_match_type}"
                    )
                seen_pairings.add(pairing_key)
                if pair[0] not in assigned_keywords or pair[1] not in assigned_skus:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} pairing references an unassigned Keyword or SKU")
                if not any(
                    keyword.get("keyword_id") == pair[0] and keyword.get("match_type") == pairing_match_type
                    for keyword in keywords
                ):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} pairing references an unassigned match type")
                source_pair = pair_index.get(pair)
                if source_pair is None or source_pair["relationship_type"] not in ASSIGNABLE_PAIR_TYPES:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} uses a missing or BLOCKED pair {pair[0]}/{pair[1]}")
                paired_keywords.add(pair[0])
                paired_skus.add(pair[1])
            if paired_keywords != assigned_keywords or paired_skus != assigned_skus:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} has unpaired Keyword or SKU assignments")

            if has_budget_baseline:
                amount = _number(ad_group.get("initial_daily_budget"), f"Ad Group {ad_group_id} initial_daily_budget")
                if not _close(amount, share * (budget_baseline or 0.0)):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} amount does not match its Group share")
                group_amount += amount
            elif "initial_daily_budget" in ad_group:
                raise HierarchyValidationError("no budget baseline: absolute Ad Group budget must be omitted")

        if not _close(group_share, campaign_share):
            raise HierarchyValidationError(f"campaign {campaign_id} Ad Group shares do not sum to campaign share")
        if has_budget_baseline:
            campaign_amount = _number(campaign_output.get("campaign_budget_seed"), f"campaign {campaign_id} campaign_budget_seed")
            if not _close(campaign_amount, group_amount) or not _close(campaign_amount, campaign_share * (budget_baseline or 0.0)):
                raise HierarchyValidationError(f"campaign {campaign_id} budget is not conserved")
            total_amount += campaign_amount
        elif "campaign_budget_seed" in campaign_output:
            raise HierarchyValidationError("no budget baseline: absolute Campaign budget must be omitted")
        total_share += campaign_share

    if not _close(total_share, 1.0):
        raise HierarchyValidationError("Campaign budget shares must sum to 1")
    warnings: list[str] = []
    if has_budget_baseline:
        total = _number(recommendation.get("budget_seed_total"), "recommendation.budget_seed_total")
        if not _close(total, budget_baseline or 0.0) or not _close(total_amount, total):
            raise HierarchyValidationError("Ad Group, Campaign and Campaign Group budgets must be conserved")
    else:
        if "budget_seed_total" in recommendation:
            raise HierarchyValidationError("no budget baseline: absolute Group budget must be omitted")
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
