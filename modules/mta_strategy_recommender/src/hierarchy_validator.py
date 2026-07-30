from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


EXPECTED_CAMPAIGN_COUNT = 4
EXPECTED_AD_GROUP_COUNTS = {
    "SPONSORED_PRODUCTS": 2,
    "SPONSORED_BRANDS": 2,
    "SPONSORED_DISPLAY": 1,
    "AMAZON_DSP": 1,
}
SEARCH_AD_PRODUCTS = {"SPONSORED_PRODUCTS", "SPONSORED_BRANDS"}
DISPLAY_AD_PRODUCTS = {"SPONSORED_DISPLAY", "AMAZON_DSP"}
OUTCOMES = ("converted_users", "purchase_count", "revenue")
SUPPORTED_SAMPLE_VERSION = "3.0"
ALLOWED_MATCH_TYPES = {"EXACT", "PHRASE", "BROAD"}
ALLOWED_EVIDENCE_TYPES = {"HISTORICAL", "VALIDATED"}
ALLOWED_ALLOCATION_ROLES = {"CORE", "EXPLORATION", "SIGNAL_ONLY"}
ALLOWED_POLICY_STATUSES = {"ALLOWED", "BLOCKED"}
ALLOWED_SIGNAL_EVIDENCE_TYPES = {"HISTORICAL_CANDIDATE", "VALIDATED_CANDIDATE"}
NORMALIZATION_UNIVERSE = "SELECTED_RECOMMENDED_TOUCHPOINTS"
ENTITY_SELECTION_METHOD = (
    "ASSISTED_REVENUE_DESC_THEN_NO_DUPLICATE_KEYWORD_MATCH_WITHIN_CAMPAIGN"
)
REQUIRED_INPUT_FILES = ("strategy_request.json", "candidate_pool.json")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_PLATFORM = "AMAZON"
EXPECTED_ATTRIBUTION_TOUCHPOINT_COUNT = 17
EXPECTED_ENTITY_ROW_COUNT = 34


class HierarchyValidationError(ValueError):
    """Raised when the aligned strategy sample violates its evidence contract."""


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
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise HierarchyValidationError(f"cannot read AMC evidence from {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise HierarchyValidationError(f"cannot hash AMC evidence {path}: {exc}") from exc
    return digest.hexdigest()


def _required_text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise HierarchyValidationError(f"{context} must be a non-empty trimmed string")
    return value


def _bool(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise HierarchyValidationError(f"{context} must be boolean")
    return value


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


def _integer(value: object, context: str, *, minimum: int = 0) -> int:
    number = _number(value, context)
    if not number.is_integer() or number < minimum:
        raise HierarchyValidationError(f"{context} must be an integer >= {minimum}")
    return int(number)


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-8)


def _money_close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-6)


def _objects(value: object, context: str, *, nonempty: bool = True) -> list[dict[str, Any]]:
    if not isinstance(value, list) or (nonempty and not value):
        raise HierarchyValidationError(f"{context} must be {'a non-empty list' if nonempty else 'a list'}")
    if any(not isinstance(item, dict) for item in value):
        raise HierarchyValidationError(f"{context} must contain only objects")
    return value


def _texts(value: object, context: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise HierarchyValidationError(f"{context} must be {'a non-empty list' if nonempty else 'a list'}")
    result = [_required_text(item, context) for item in value]
    if len(result) != len(set(result)):
        raise HierarchyValidationError(f"{context} must not contain duplicates")
    return result


def _unique(rows: list[dict[str, Any]], key: str, context: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows, start=1):
        item_id = _required_text(row.get(key), f"{context}[{position}].{key}")
        if item_id in result:
            raise HierarchyValidationError(f"{context} repeats {key} {item_id}")
        result[item_id] = row
    return result


def _resolve_evidence_path(explicit: str | Path | None, declared: str, context: str) -> Path:
    path = Path(explicit) if explicit is not None else PROJECT_ROOT / declared
    if not path.is_file():
        raise HierarchyValidationError(f"missing {context}: {path}")
    return path


def _validate_source(
    request: dict[str, Any],
    attribution_path: str | Path | None,
    entity_path: str | Path | None,
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]], Path, Path]:
    source = request.get("mta_source")
    if not isinstance(source, dict):
        raise HierarchyValidationError("strategy_request.mta_source must be an object")
    attribution_file = _required_text(source.get("attribution_file"), "mta_source.attribution_file")
    entity_file = _required_text(source.get("entity_file"), "mta_source.entity_file")
    attribution = _resolve_evidence_path(attribution_path, attribution_file, "AMC attribution file")
    entity = _resolve_evidence_path(entity_path, entity_file, "AMC entity file")
    if _sha256(attribution) != _required_text(source.get("attribution_sha256"), "mta_source.attribution_sha256"):
        raise HierarchyValidationError("AMC attribution SHA-256 does not match strategy_request")
    if _sha256(entity) != _required_text(source.get("entity_sha256"), "mta_source.entity_sha256"):
        raise HierarchyValidationError("AMC entity SHA-256 does not match strategy_request")
    attribution_rows = _read_csv(attribution)
    entity_rows = _read_csv(entity)
    touchpoint_count = len({row.get("touchpoint", "") for row in attribution_rows})
    if touchpoint_count != EXPECTED_ATTRIBUTION_TOUCHPOINT_COUNT:
        raise HierarchyValidationError(
            f"sample v{SUPPORTED_SAMPLE_VERSION} requires exactly "
            f"{EXPECTED_ATTRIBUTION_TOUCHPOINT_COUNT} AMC attribution touchpoints"
        )
    if len(entity_rows) != EXPECTED_ENTITY_ROW_COUNT:
        raise HierarchyValidationError(
            f"sample v{SUPPORTED_SAMPLE_VERSION} requires exactly "
            f"{EXPECTED_ENTITY_ROW_COUNT} AMC entity rows"
        )
    if touchpoint_count != _integer(source.get("available_touchpoint_count"), "mta_source.available_touchpoint_count", minimum=1):
        raise HierarchyValidationError("AMC attribution touchpoint count does not match strategy_request")
    if len(entity_rows) != _integer(source.get("entity_row_count"), "mta_source.entity_row_count", minimum=1):
        raise HierarchyValidationError("AMC entity row count does not match strategy_request")
    return source, attribution_rows, entity_rows, attribution, entity


def validate_simulated_hierarchy(
    data_dir: str | Path,
    recommendation_path: str | Path,
    attribution_path: str | Path | None = None,
    entity_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir)
    missing = [name for name in REQUIRED_INPUT_FILES if not (root / name).is_file()]
    if missing:
        raise HierarchyValidationError(f"missing required sample file(s): {', '.join(missing)}")
    expected_entries = {*REQUIRED_INPUT_FILES, "README.md"}
    unexpected = sorted(path.name for path in root.iterdir() if path.name not in expected_entries)
    if unexpected:
        raise HierarchyValidationError("unrelated content must not be stored in the input directory: " + ", ".join(unexpected))
    recommendation_file = Path(recommendation_path)
    if not recommendation_file.is_file():
        raise HierarchyValidationError(f"missing recommendation fixture: {recommendation_file}")

    request = _read_json(root / "strategy_request.json")
    pool = _read_json(root / "candidate_pool.json")
    recommendation = _read_json(recommendation_file)
    if request.get("sample_version") != SUPPORTED_SAMPLE_VERSION or pool.get("sample_version") != SUPPORTED_SAMPLE_VERSION:
        raise HierarchyValidationError(f"sample_version must be {SUPPORTED_SAMPLE_VERSION}")

    source, attribution_rows, entity_rows, _, _ = _validate_source(
        request, attribution_path, entity_path
    )
    group = request.get("campaign_group")
    if not isinstance(group, dict):
        raise HierarchyValidationError("campaign_group must be an object")
    group_id = _required_text(group.get("campaign_group_id"), "campaign_group_id")
    marketplace = _required_text(group.get("marketplace"), "campaign_group.marketplace")
    advertiser_id = _required_text(group.get("advertiser_id"), "campaign_group.advertiser_id")
    for field in ("group_name", "platform", "currency"):
        _required_text(group.get(field), f"campaign_group.{field}")
    if group.get("platform") != EXPECTED_PLATFORM:
        raise HierarchyValidationError(
            f"campaign_group.platform must be {EXPECTED_PLATFORM} for Amazon AMC evidence"
        )
    if source.get("marketplace") != marketplace or source.get("advertiser_id") != advertiser_id:
        raise HierarchyValidationError("mta_source scope does not match Campaign Group")
    report_start = _required_text(source.get("report_start_date"), "mta_source.report_start_date")
    report_end = _required_text(source.get("report_end_date"), "mta_source.report_end_date")

    campaigns = _objects(request.get("campaigns"), "campaigns")
    campaign_index = _unique(campaigns, "campaign_id", "campaigns")
    if len(campaign_index) != EXPECTED_CAMPAIGN_COUNT:
        raise HierarchyValidationError("Campaign Group must contain exactly 4 campaigns")
    ad_products: set[str] = set()
    for campaign_id, campaign in campaign_index.items():
        _required_text(campaign.get("campaign_name"), f"campaign {campaign_id} campaign_name")
        ad_product = _required_text(campaign.get("ad_product"), f"campaign {campaign_id} ad_product")
        if ad_product not in EXPECTED_AD_GROUP_COUNTS or ad_product in ad_products:
            raise HierarchyValidationError("the four Campaigns must use the four supported ad products once each")
        ad_products.add(ad_product)
        if campaign.get("status") != "enabled":
            raise HierarchyValidationError(f"campaign {campaign_id} must be enabled")
        _required_text(campaign.get("targeting"), f"campaign {campaign_id} targeting")

    for row in entity_rows:
        if (
            row.get("report_start_date") != report_start
            or row.get("report_end_date") != report_end
            or row.get("marketplace") != marketplace
            or row.get("advertiser_id") != advertiser_id
            or row.get("campaign_group_id") != group_id
        ):
            raise HierarchyValidationError("AMC entity scope does not match mta_source and Campaign Group")
        campaign = campaign_index.get(row.get("campaign_id", ""))
        if campaign is None or row.get("touchpoint", "").split(":", 1)[0] != campaign.get("ad_product"):
            raise HierarchyValidationError("AMC entity Campaign/ad_product does not match strategy input")

    weights = request.get("outcome_weights")
    if not isinstance(weights, dict) or set(weights) != set(OUTCOMES):
        raise HierarchyValidationError("outcome_weights must contain the three supported outcomes")
    normalized_weights = {name: _number(weights[name], f"outcome_weights.{name}") for name in OUTCOMES}
    if not _close(sum(normalized_weights.values()), 1.0):
        raise HierarchyValidationError("outcome_weights must sum to 1")
    selection = request.get("touchpoint_selection")
    if not isinstance(selection, dict):
        raise HierarchyValidationError("touchpoint_selection must be an object")
    if selection.get("normalization_universe") != NORMALIZATION_UNIVERSE:
        raise HierarchyValidationError("unsupported budget normalization universe")
    if selection.get("entity_selection_method") != ENTITY_SELECTION_METHOD:
        raise HierarchyValidationError("unsupported entity selection method")
    available_count = len({row["touchpoint"] for row in attribution_rows})
    selected_count = _integer(selection.get("selected_touchpoint_count"), "selected_touchpoint_count", minimum=1)
    if (
        selection.get("available_touchpoint_count") != available_count
        or selection.get("excluded_touchpoint_count") != available_count - selected_count
    ):
        raise HierarchyValidationError("touchpoint selection must disclose the 17 to 6 scope")

    constraints = request.get("ad_group_constraints")
    if not isinstance(constraints, dict):
        raise HierarchyValidationError("ad_group_constraints must be an object")
    min_search_keywords = _integer(constraints.get("min_native_keywords_search_ads"), "min_native_keywords_search_ads", minimum=1)
    max_keywords = _integer(constraints.get("max_native_keywords_per_ad_group"), "max_native_keywords_per_ad_group", minimum=1)
    min_skus = _integer(constraints.get("min_native_skus"), "min_native_skus", minimum=1)
    max_skus = _integer(constraints.get("max_native_skus_per_ad_group"), "max_native_skus_per_ad_group", minimum=1)
    max_ad_groups = _integer(constraints.get("max_ad_groups_per_campaign"), "max_ad_groups_per_campaign", minimum=1)
    max_exploration = _integer(constraints.get("max_exploration_groups_per_campaign"), "max_exploration_groups_per_campaign")

    pool_id = _required_text(request.get("candidate_pool_id"), "strategy_request.candidate_pool_id")
    mta_batch_id = _required_text(request.get("mta_batch_id"), "strategy_request.mta_batch_id")
    if pool.get("candidate_pool_id") != pool_id or pool.get("campaign_group_id") != group_id:
        raise HierarchyValidationError("candidate pool lineage does not match strategy request")
    keyword_index = _unique(_objects(pool.get("keywords"), "candidate_pool.keywords"), "keyword_id", "keywords")
    sku_index = _unique(_objects(pool.get("skus"), "candidate_pool.skus"), "sku_id", "skus")
    entity_keyword_ids = {row["keyword_id"] for row in entity_rows if row.get("keyword_id")}
    entity_sku_ids = {row["sku_id"] for row in entity_rows if row.get("sku_id")}
    keyword_matches: dict[str, set[str]] = {}
    for keyword_id, keyword in keyword_index.items():
        _required_text(keyword.get("keyword_text"), f"keyword {keyword_id} keyword_text")
        evidence_type = _required_text(keyword.get("evidence_type"), f"keyword {keyword_id} evidence_type")
        role = _required_text(keyword.get("allocation_role"), f"keyword {keyword_id} allocation_role")
        if evidence_type not in ALLOWED_EVIDENCE_TYPES or role not in ALLOWED_ALLOCATION_ROLES:
            raise HierarchyValidationError(f"keyword {keyword_id} has unsupported evidence or allocation role")
        historical_rows = [row for row in entity_rows if row.get("keyword_id") == keyword_id]
        if evidence_type == "HISTORICAL" and keyword_id not in entity_keyword_ids:
            raise HierarchyValidationError(f"HISTORICAL keyword {keyword_id} is absent from AMC entities")
        if not _bool(keyword.get("eligible"), f"keyword {keyword_id} eligible"):
            raise HierarchyValidationError(f"keyword {keyword_id} is not executable")
        match_types = set(_texts(keyword.get("allowed_match_types"), f"keyword {keyword_id} allowed_match_types", nonempty=True))
        if not match_types <= ALLOWED_MATCH_TYPES:
            raise HierarchyValidationError(f"keyword {keyword_id} has unsupported match type")
        if evidence_type == "HISTORICAL":
            observed_texts = {row.get("keyword_text") for row in historical_rows}
            observed_matches = {row.get("match_type") for row in historical_rows}
            if observed_texts != {keyword.get("keyword_text")} or observed_matches != match_types:
                raise HierarchyValidationError(
                    f"HISTORICAL keyword {keyword_id} metadata does not match AMC entities"
                )
        keyword_matches[keyword_id] = match_types
    for sku_id, sku in sku_index.items():
        evidence_type = _required_text(sku.get("evidence_type"), f"sku {sku_id} evidence_type")
        role = _required_text(sku.get("allocation_role"), f"sku {sku_id} allocation_role")
        if evidence_type not in ALLOWED_EVIDENCE_TYPES or role not in ALLOWED_ALLOCATION_ROLES:
            raise HierarchyValidationError(f"sku {sku_id} has unsupported evidence or allocation role")
        if evidence_type == "HISTORICAL" and sku_id not in entity_sku_ids:
            raise HierarchyValidationError(f"HISTORICAL SKU {sku_id} is absent from AMC entities")
        for field in ("product_id", "brand", "category", "segment"):
            _required_text(sku.get(field), f"sku {sku_id} {field}")
        for field in ("eligible", "inventory_available", "paid_search_enabled", "scope_for_search_optimization"):
            if not _bool(sku.get(field), f"sku {sku_id} {field}"):
                raise HierarchyValidationError(f"sku {sku_id} is not executable")

    pair_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    historical_pair_count = 0
    for position, pair in enumerate(_objects(pool.get("pair_rules"), "candidate_pool.pair_rules"), start=1):
        keyword_id = _required_text(pair.get("keyword_id"), f"pair[{position}].keyword_id")
        sku_id = _required_text(pair.get("sku_id"), f"pair[{position}].sku_id")
        match_type = _required_text(pair.get("match_type"), f"pair[{position}].match_type")
        key = (keyword_id, sku_id, match_type)
        if key in pair_index or keyword_id not in keyword_index or sku_id not in sku_index:
            raise HierarchyValidationError(f"invalid or duplicate candidate pair {key}")
        if match_type not in keyword_matches[keyword_id]:
            raise HierarchyValidationError(f"pair {key} uses a disallowed match type")
        evidence_type = _required_text(pair.get("evidence_type"), f"pair {key} evidence_type")
        policy = _required_text(pair.get("policy_status"), f"pair {key} policy_status")
        role = _required_text(pair.get("allocation_role"), f"pair {key} allocation_role")
        products = _texts(pair.get("eligible_ad_products"), f"pair {key} eligible_ad_products", nonempty=True)
        historical_touchpoints = _texts(pair.get("historical_touchpoints"), f"pair {key} historical_touchpoints")
        if evidence_type not in ALLOWED_EVIDENCE_TYPES or policy not in ALLOWED_POLICY_STATUSES or role not in ALLOWED_ALLOCATION_ROLES:
            raise HierarchyValidationError(f"pair {key} has unsupported evidence, policy or role")
        if not set(products) <= set(EXPECTED_AD_GROUP_COUNTS):
            raise HierarchyValidationError(f"pair {key} has unsupported eligible_ad_products")
        if evidence_type == "HISTORICAL":
            historical_pair_count += 1
            if not historical_touchpoints:
                raise HierarchyValidationError(f"HISTORICAL pair {key} must name AMC touchpoints")
            for touchpoint in historical_touchpoints:
                if not any(
                    row.get("keyword_id") == keyword_id
                    and row.get("sku_id") == sku_id
                    and row.get("match_type") == match_type
                    and row.get("touchpoint") == touchpoint
                    and touchpoint.split(":", 1)[0] in products
                    for row in entity_rows
                ):
                    raise HierarchyValidationError(f"HISTORICAL pair {key} is not supported by AMC entity data")
        elif historical_touchpoints:
            raise HierarchyValidationError(f"VALIDATED pair {key} must not claim historical touchpoints")
        pair_index[key] = pair

    signal_rules: dict[tuple[str, str, str], dict[str, Any]] = {}
    for position, rule in enumerate(_objects(pool.get("signal_rules"), "candidate_pool.signal_rules"), start=1):
        keyword_id = _required_text(rule.get("keyword_id"), f"signal_rule[{position}].keyword_id")
        sku_id = _required_text(rule.get("sku_id"), f"signal_rule[{position}].sku_id")
        products = _texts(rule.get("eligible_ad_products"), f"signal_rule[{position}].eligible_ad_products", nonempty=True)
        evidence_type = _required_text(rule.get("evidence_type"), f"signal_rule[{position}].evidence_type")
        if keyword_id not in keyword_index or sku_id not in sku_index or _bool(rule.get("direct_mta_entity_evidence"), "signal direct evidence"):
            raise HierarchyValidationError("strategy signal rules must reference candidates and deny direct entity evidence")
        if evidence_type not in ALLOWED_SIGNAL_EVIDENCE_TYPES:
            raise HierarchyValidationError("strategy signal rule has unsupported evidence_type")
        if not set(products) <= DISPLAY_AD_PRODUCTS:
            raise HierarchyValidationError("strategy signal rules are only supported for SD/DSP")
        for product in products:
            key = (keyword_id, sku_id, product)
            if key in signal_rules:
                raise HierarchyValidationError(f"duplicate signal rule {key}")
            signal_rules[key] = {**rule, "evidence_type": evidence_type}

    attribution_index: dict[tuple[str, str], dict[str, str]] = {}
    for row in attribution_rows:
        key = (row.get("touchpoint", ""), row.get("outcome", ""))
        if not key[0] or key[1] not in OUTCOMES:
            raise HierarchyValidationError(f"invalid AMC attribution row {key}")
        if key in attribution_index:
            raise HierarchyValidationError(f"duplicate AMC attribution row {key}")
        attribution_index[key] = row
    for touchpoint in {row.get("touchpoint", "") for row in attribution_rows}:
        if {outcome for candidate_touchpoint, outcome in attribution_index if candidate_touchpoint == touchpoint} != set(OUTCOMES):
            raise HierarchyValidationError(
                f"AMC attribution touchpoint {touchpoint} must contain all three outcomes"
            )

    if recommendation.get("campaign_group_id") != group_id or recommendation.get("candidate_pool_id") != pool_id or recommendation.get("mta_batch_id") != mta_batch_id:
        raise HierarchyValidationError("recommendation lineage does not match inputs")
    if recommendation.get("recommendation_type") != "INITIAL_SEED" or recommendation.get("handoff_status") != "READY_FOR_OPTIMIZATION" or recommendation.get("is_optimized") is not False:
        raise HierarchyValidationError("recommendation must be a non-optimized INITIAL_SEED ready for handoff")
    snapshot = recommendation.get("mta_source_snapshot")
    if not isinstance(snapshot, dict):
        raise HierarchyValidationError("recommendation must contain mta_source_snapshot")
    for field in ("report_start_date", "report_end_date", "marketplace", "advertiser_id", "attribution_sha256", "entity_sha256"):
        if snapshot.get(field) != source.get(field):
            raise HierarchyValidationError(f"recommendation source snapshot mismatch: {field}")
    output_selection = recommendation.get("touchpoint_selection")
    if not isinstance(output_selection, dict):
        raise HierarchyValidationError("recommendation touchpoint_selection must be an object")
    for field in ("normalization_universe", "available_touchpoint_count", "selected_touchpoint_count", "excluded_touchpoint_count", "entity_selection_method"):
        if output_selection.get(field) != selection.get(field):
            raise HierarchyValidationError(f"recommendation touchpoint selection mismatch: {field}")
    selected_touchpoints = _texts(output_selection.get("selected_touchpoints"), "selected_touchpoints", nonempty=True)
    if len(selected_touchpoints) != selected_count:
        raise HierarchyValidationError("selected_touchpoints count does not match declared 17 to 6 scope")

    derivation = recommendation.get("budget_derivation")
    if not isinstance(derivation, dict) or derivation.get("formula_version") != "WEIGHTED_MTA_SHARE_V1" or derivation.get("normalization_universe") != NORMALIZATION_UNIVERSE:
        raise HierarchyValidationError("invalid budget derivation metadata")
    if derivation.get("outcome_weights") != weights:
        raise HierarchyValidationError("budget derivation weights do not match strategy request")

    outputs = _objects(recommendation.get("campaigns"), "recommendation.campaigns")
    output_ids = [_required_text(item.get("campaign_id"), "recommendation campaign_id") for item in outputs]
    if len(output_ids) != len(set(output_ids)) or set(output_ids) != set(campaign_index):
        raise HierarchyValidationError("recommendation must contain every Campaign exactly once")

    has_budget = group.get("total_daily_budget") not in (None, "")
    total_budget = _number(group.get("total_daily_budget"), "total_daily_budget") if has_budget else None
    used_touchpoints: set[str] = set()
    used_keyword_matches: dict[str, set[tuple[str, str]]] = {campaign_id: set() for campaign_id in campaign_index}
    group_records: list[tuple[str, float, float, dict[str, Any]]] = []
    total_amount = 0.0
    ad_group_count = 0
    seen_ad_group_ids: set[str] = set()
    for campaign_output in outputs:
        campaign_id = campaign_output["campaign_id"]
        if "ad_product" in campaign_output:
            raise HierarchyValidationError(
                f"recommendation campaign {campaign_id} must inherit ad_product from strategy input"
            )
        campaign = campaign_index[campaign_id]
        ad_product = campaign["ad_product"]
        groups = _objects(campaign_output.get("recommended_ad_groups"), f"campaign {campaign_id} ad groups")
        expected_count = EXPECTED_AD_GROUP_COUNTS[ad_product]
        if len(groups) != expected_count or len(groups) > max_ad_groups or campaign_output.get("recommended_ad_group_count") != expected_count:
            raise HierarchyValidationError(f"campaign {campaign_id} must recommend {expected_count} Ad Groups")
        rationale = campaign_output.get("count_rationale")
        if not isinstance(rationale, dict) or rationale.get("final_recommended_count") != expected_count:
            raise HierarchyValidationError(f"campaign {campaign_id} count rationale does not match output")
        exploration_count = 0
        campaign_share = _number(campaign_output.get("budget_seed_share"), f"campaign {campaign_id} share")
        campaign_group_share = 0.0
        campaign_amount = 0.0
        for ad_group in groups:
            ad_group_count += 1
            ad_group_id = _required_text(ad_group.get("ad_group_id"), f"campaign {campaign_id} ad_group_id")
            if ad_group_id in seen_ad_group_ids:
                raise HierarchyValidationError(f"duplicate recommendation ad_group_id {ad_group_id}")
            seen_ad_group_ids.add(ad_group_id)
            if "ad_product" in ad_group:
                raise HierarchyValidationError(
                    f"Ad Group {ad_group_id} must inherit ad_product from its Campaign"
                )
            if ad_group.get("source_candidate_pool_id") != pool_id:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} candidate pool lineage mismatch")
            _required_text(ad_group.get("strategy_name"), f"Ad Group {ad_group_id} strategy_name")
            role = _required_text(ad_group.get("strategy_role"), f"Ad Group {ad_group_id} strategy_role")
            exploration_count += role == "EXPLORATION"
            confidence = _number(ad_group.get("confidence"), f"Ad Group {ad_group_id} confidence")
            if confidence > 1:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} confidence must be <= 1")
            _texts(ad_group.get("reason_codes"), f"Ad Group {ad_group_id} reason_codes", nonempty=True)
            for action in _objects(ad_group.get("recommended_actions"), f"Ad Group {ad_group_id} actions"):
                if action.get("causal_claim") is not False:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} must not make a causal claim")
                for field in ("dimension", "action", "value", "control_level", "evidence_type"):
                    _required_text(action.get(field), f"Ad Group {ad_group_id} action {field}")

            evidence = _objects(ad_group.get("mta_evidence"), f"Ad Group {ad_group_id} mta_evidence")
            if len(evidence) != 1:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must use exactly one selected touchpoint")
            item = evidence[0]
            touchpoint = _required_text(item.get("touchpoint"), f"Ad Group {ad_group_id} touchpoint")
            if touchpoint in used_touchpoints or touchpoint not in selected_touchpoints or touchpoint.split(":", 1)[0] != ad_product:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} uses an invalid or duplicate selected touchpoint")
            used_touchpoints.add(touchpoint)
            outcome_values = item.get("outcomes")
            if not isinstance(outcome_values, dict) or set(outcome_values) != set(OUTCOMES):
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must contain all MTA outcome values")
            score = 0.0
            for outcome in OUTCOMES:
                values = outcome_values[outcome]
                if not isinstance(values, dict):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} outcome {outcome} must be an object")
                source_row = attribution_index.get((touchpoint, outcome))
                if source_row is None:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} touchpoint/outcome is absent from AMC")
                for field in ("official_share", "recommended_value", "benchmark_share"):
                    if not _close(_number(values.get(field), f"{ad_group_id} {outcome} {field}"), float(source_row[field])):
                        raise HierarchyValidationError(f"Ad Group {ad_group_id} MTA value drift: {outcome}.{field}")
                if values.get("reliability_status") != source_row.get("reliability_status"):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} MTA reliability drift")
                score += normalized_weights[outcome] * float(source_row["recommended_value"])
            if not _close(_number(item.get("composite_score"), f"Ad Group {ad_group_id} composite_score"), score):
                raise HierarchyValidationError(f"Ad Group {ad_group_id} composite score cannot be reproduced")

            assignment = ad_group.get("targeting_assignment")
            if not isinstance(assignment, dict):
                raise HierarchyValidationError(f"Ad Group {ad_group_id} targeting_assignment must be an object")
            native = assignment.get("native_targets")
            signals = assignment.get("strategy_signals")
            if not isinstance(native, dict) or not isinstance(signals, dict):
                raise HierarchyValidationError(f"Ad Group {ad_group_id} must separate native targets and strategy signals")
            keywords = _objects(native.get("keywords"), f"Ad Group {ad_group_id} native keywords", nonempty=False)
            skus = _objects(native.get("skus"), f"Ad Group {ad_group_id} native skus")
            target_ids = _texts(native.get("target_ids"), f"Ad Group {ad_group_id} target_ids")
            audience_ids = _texts(native.get("audience_ids"), f"Ad Group {ad_group_id} audience_ids")
            pairings = _objects(assignment.get("pairings"), f"Ad Group {ad_group_id} pairings", nonempty=False)
            keyword_signals = _objects(signals.get("keyword_ids"), f"Ad Group {ad_group_id} keyword signals", nonempty=False)
            sku_signals = _objects(signals.get("sku_ids"), f"Ad Group {ad_group_id} SKU signals", nonempty=False)
            if not min_skus <= len(skus) <= max_skus:
                raise HierarchyValidationError(f"Ad Group {ad_group_id} native SKU capacity violation")

            entity_candidates = [
                row for row in entity_rows
                if row.get("campaign_id") == campaign_id and row.get("touchpoint") == touchpoint
            ]
            entity_candidates.sort(key=lambda row: float(row["assisted_revenue"]), reverse=True)
            if ad_product in SEARCH_AD_PRODUCTS:
                if (
                    len(keywords) != 1
                    or len(skus) != 1
                    or len(pairings) != 1
                    or not min_search_keywords <= len(keywords) <= max_keywords
                ):
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} search sample must contain exactly one Keyword/SKU/pairing"
                    )
                if target_ids or audience_ids or keyword_signals or sku_signals:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} search ads contain unsupported target arrays or signals")
                keyword = keywords[0]
                sku = skus[0]
                pairing = pairings[0]
                keyword_id = _required_text(keyword.get("keyword_id"), f"Ad Group {ad_group_id} keyword_id")
                match_type = _required_text(keyword.get("match_type"), f"Ad Group {ad_group_id} match_type")
                sku_id = _required_text(sku.get("sku_id"), f"Ad Group {ad_group_id} sku_id")
                target_id = _required_text(keyword.get("target_id"), f"Ad Group {ad_group_id} keyword target_id")
                asin = _required_text(sku.get("advertised_asin"), f"Ad Group {ad_group_id} advertised_asin")
                if keyword_id not in keyword_index or sku_id not in sku_index or match_type not in keyword_matches[keyword_id]:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} references an ineligible native candidate")
                pair_key = (keyword_id, sku_id, match_type)
                pair_rule = pair_index.get(pair_key)
                if pair_rule is None or pair_rule.get("evidence_type") != "HISTORICAL" or pair_rule.get("policy_status") != "ALLOWED" or ad_product not in pair_rule.get("eligible_ad_products", []):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} native pair is not an allowed HISTORICAL pair")
                expected_exploration = pair_rule.get("allocation_role") == "EXPLORATION"
                if (role == "EXPLORATION") != expected_exploration:
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} strategy role does not match pair allocation role"
                    )
                if (pairing.get("keyword_id"), pairing.get("sku_id"), pairing.get("match_type")) != pair_key:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} pairing does not match native targets")
                selected_rows = [
                    row for row in entity_candidates
                    if row.get("keyword_id") == keyword_id
                    and row.get("match_type") == match_type
                    and row.get("sku_id") == sku_id
                    and row.get("target_id") == target_id
                    and row.get("advertised_asin") == asin
                ]
                eligible_rows: list[dict[str, str]] = []
                for row in entity_candidates:
                    candidate_pair = pair_index.get(
                        (row.get("keyword_id", ""), row.get("sku_id", ""), row.get("match_type", ""))
                    )
                    if (
                        row.get("keyword_id") in keyword_index
                        and row.get("sku_id") in sku_index
                        and row.get("match_type") in keyword_matches.get(row.get("keyword_id", ""), set())
                        and (row.get("keyword_id"), row.get("match_type")) not in used_keyword_matches[campaign_id]
                        and candidate_pair is not None
                        and candidate_pair.get("evidence_type") == "HISTORICAL"
                        and candidate_pair.get("policy_status") == "ALLOWED"
                        and ad_product in candidate_pair.get("eligible_ad_products", [])
                        and touchpoint in candidate_pair.get("historical_touchpoints", [])
                    ):
                        eligible_rows.append(row)
                if len(selected_rows) != 1 or not eligible_rows or selected_rows[0] is not eligible_rows[0]:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} does not follow deterministic AMC entity selection")
                used_keyword_matches[campaign_id].add((keyword_id, match_type))
            else:
                if (
                    keywords
                    or pairings
                    or len(skus) != 1
                    or len(target_ids) != 1
                    or len(audience_ids) != 1
                    or len(keyword_signals) != 1
                    or sku_signals
                ):
                    raise HierarchyValidationError(
                        f"Ad Group {ad_group_id} SD/DSP sample must use exactly one SKU/Target/Audience and one Keyword signal"
                    )
                sku = skus[0]
                sku_id = _required_text(sku.get("sku_id"), f"Ad Group {ad_group_id} sku_id")
                asin = _required_text(sku.get("advertised_asin"), f"Ad Group {ad_group_id} advertised_asin")
                if sku_index.get(sku_id, {}).get("evidence_type") != "HISTORICAL":
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} native SKU must be HISTORICAL")
                selected_rows = [
                    row for row in entity_candidates
                    if row.get("sku_id") == sku_id
                    and row.get("advertised_asin") == asin
                    and row.get("target_id") == target_ids[0]
                    and row.get("audience_id") == audience_ids[0]
                ]
                eligible_rows = [
                    row
                    for row in entity_candidates
                    if row.get("sku_id") in sku_index
                    and sku_index[row["sku_id"]].get("evidence_type") == "HISTORICAL"
                    and row.get("target_id")
                    and row.get("audience_id")
                ]
                if len(selected_rows) != 1 or not eligible_rows or selected_rows[0] is not eligible_rows[0]:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} does not follow deterministic AMC entity selection")
                if not keyword_signals:
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} must preserve the given Keyword as a non-native signal")
                for signal in keyword_signals:
                    signal_id = _required_text(signal.get("keyword_id"), f"Ad Group {ad_group_id} signal keyword_id")
                    evidence_type = _required_text(signal.get("evidence_type"), f"Ad Group {ad_group_id} signal evidence_type")
                    if signal_id not in keyword_index or not keyword_index[signal_id].get("eligible"):
                        raise HierarchyValidationError(
                            f"Ad Group {ad_group_id} signal Keyword is not executable"
                        )
                    if signal.get("direct_mta_entity_evidence") is not False:
                        raise HierarchyValidationError(f"Ad Group {ad_group_id} signal cannot claim direct MTA entity evidence")
                    rule = signal_rules.get((signal_id, sku_id, ad_product))
                    if rule is None or rule.get("evidence_type") != evidence_type:
                        raise HierarchyValidationError(f"Ad Group {ad_group_id} strategy signal is not allowed by the candidate pool")

            selected_row = selected_rows[0]
            entity_evidence = ad_group.get("entity_evidence")
            if not isinstance(entity_evidence, dict):
                raise HierarchyValidationError(f"Ad Group {ad_group_id} entity_evidence must be an object")
            expected_rank = entity_candidates.index(selected_row) + 1
            if (
                entity_evidence.get("source_ad_group_id") != selected_row.get("ad_group_id")
                or entity_evidence.get("selection_rank") != expected_rank
                or not _close(_number(entity_evidence.get("assisted_revenue"), f"Ad Group {ad_group_id} assisted_revenue"), float(selected_row["assisted_revenue"]))
            ):
                raise HierarchyValidationError(f"Ad Group {ad_group_id} entity evidence does not match AMC")

            share = _number(ad_group.get("budget_seed_share"), f"Ad Group {ad_group_id} budget_seed_share")
            group_records.append((ad_group_id, score, share, ad_group))
            campaign_group_share += share
            if has_budget:
                amount = _number(ad_group.get("initial_daily_budget"), f"Ad Group {ad_group_id} initial_daily_budget")
                if not _money_close(amount, share * (total_budget or 0.0)):
                    raise HierarchyValidationError(f"Ad Group {ad_group_id} absolute budget does not match Group share")
                campaign_amount += amount
            elif "initial_daily_budget" in ad_group:
                raise HierarchyValidationError("no total budget: absolute Ad Group budget must be omitted")
        if exploration_count > max_exploration:
            raise HierarchyValidationError(f"campaign {campaign_id} exceeds exploration group limit")
        if not _close(campaign_group_share, campaign_share):
            raise HierarchyValidationError(f"campaign {campaign_id} Ad Group shares do not sum to Campaign share")
        if has_budget:
            output_amount = _number(campaign_output.get("campaign_budget_seed"), f"campaign {campaign_id} budget")
            if not _money_close(output_amount, campaign_amount) or not _money_close(output_amount, campaign_share * (total_budget or 0.0)):
                raise HierarchyValidationError(f"campaign {campaign_id} budget is not conserved")
            total_amount += output_amount
        elif "campaign_budget_seed" in campaign_output:
            raise HierarchyValidationError("no total budget: absolute Campaign budget must be omitted")

    if used_touchpoints != set(selected_touchpoints):
        raise HierarchyValidationError("the six selected touchpoints must each support exactly one Ad Group")
    score_total = sum(record[1] for record in group_records)
    if score_total <= 0:
        raise HierarchyValidationError("selected composite score total must be positive")
    if not _close(_number(derivation.get("selected_composite_score_total"), "selected score total"), score_total):
        raise HierarchyValidationError("selected composite score total cannot be reproduced")
    for ad_group_id, score, share, _ in group_records:
        if not _close(share, score / score_total):
            raise HierarchyValidationError(f"Ad Group {ad_group_id} budget share is not normalized from MTA score")
    if not _close(sum(record[2] for record in group_records), 1.0):
        raise HierarchyValidationError("Ad Group Group-level shares must sum to 1")
    warnings: list[str] = []
    if has_budget:
        if not _money_close(_number(recommendation.get("budget_seed_total"), "budget_seed_total"), total_budget or 0.0) or not _money_close(total_amount, total_budget or 0.0):
            raise HierarchyValidationError("Campaign Group budget is not conserved")
    else:
        if "budget_seed_total" in recommendation:
            raise HierarchyValidationError("no total budget: budget_seed_total must be omitted")
        warnings.append("NO_BUDGET_BASELINE_RELATIVE_SHARES_ONLY")

    return {
        "campaign_group_id": group_id,
        "campaign_count": len(campaign_index),
        "recommended_ad_group_count": ad_group_count,
        "keyword_count": len(keyword_index),
        "sku_count": len(sku_index),
        "historical_pair_count": historical_pair_count,
        "attribution_touchpoint_count": available_count,
        "entity_row_count": len(entity_rows),
        "selected_touchpoint_count": len(selected_touchpoints),
        "normalization_universe": NORMALIZATION_UNIVERSE,
        "has_budget_baseline": has_budget,
        "recommendation_type": "INITIAL_SEED",
        "warnings": warnings,
    }
