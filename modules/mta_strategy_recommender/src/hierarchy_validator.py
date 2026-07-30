from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from budget_recommender import (
    BudgetRecommendationError,
    NORMALIZATION_UNIVERSE,
    SUPPORTED_SAMPLE_VERSION,
    generate_budget_recommendation,
)


REQUIRED_INPUT_FILES = ("strategy_request.json", "candidate_pool.json")
EXPECTED_INPUT_ENTRIES = {*REQUIRED_INPUT_FILES, "README.md"}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_OUTPUT_FIELDS = {
    "keyword_id",
    "keyword_ids",
    "sku_id",
    "sku_ids",
    "target_id",
    "target_ids",
    "audience_id",
    "audience_ids",
    "targeting_assignment",
    "recommended_actions",
    "strategy_name",
    "strategy_role",
    "entity_evidence",
    "source_ad_group_id",
    "historical_ad_group_id",
    "pairings",
}


class HierarchyValidationError(ValueError):
    """Raised when the budget-only strategy sample violates its contract."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            result = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise HierarchyValidationError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise HierarchyValidationError(f"{path}: top-level value must be an object")
    return result


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


def _integer(value: object, context: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise HierarchyValidationError(f"{context} must be an integer >= {minimum}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HierarchyValidationError(f"{context} must be an integer >= {minimum}") from exc
    if not number.is_integer() or number < minimum:
        raise HierarchyValidationError(f"{context} must be an integer >= {minimum}")
    return int(number)


def _resolve_evidence_path(explicit: str | Path | None, declared: str, context: str) -> Path:
    path = Path(explicit) if explicit is not None else PROJECT_ROOT / declared
    if not path.is_file():
        raise HierarchyValidationError(f"missing {context}: {path}")
    return path


def _forbidden_paths(value: object, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_OUTPUT_FIELDS:
                matches.append(child_path)
            matches.extend(_forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for position, child in enumerate(value):
            matches.extend(_forbidden_paths(child, f"{path}[{position}]"))
    return matches


def _first_difference(expected: object, actual: object, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        return f"{path} type"
    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)  # type: ignore[arg-type]
        if expected_keys != actual_keys:
            missing = sorted(expected_keys - actual_keys)
            extra = sorted(actual_keys - expected_keys)
            return f"{path} fields (missing={missing}, extra={extra})"
        for key in expected:
            difference = _first_difference(expected[key], actual[key], f"{path}.{key}")  # type: ignore[index]
            if difference:
                return difference
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):  # type: ignore[arg-type]
            return f"{path} length"
        for position, child in enumerate(expected):
            difference = _first_difference(child, actual[position], f"{path}[{position}]")  # type: ignore[index]
            if difference:
                return difference
        return None
    return None if expected == actual else path


def _validate_budget_invariants(recommendation: dict[str, Any]) -> None:
    campaigns = recommendation.get("campaigns")
    if not isinstance(campaigns, list) or not campaigns:
        raise HierarchyValidationError("recommendation campaigns must be a non-empty list")
    campaign_shares: list[float] = []
    campaign_amounts: list[float] = []
    has_budget = "budget_seed_total" in recommendation
    for position, campaign in enumerate(campaigns, start=1):
        if not isinstance(campaign, dict):
            raise HierarchyValidationError(f"campaign output {position} must be an object")
        groups = campaign.get("recommended_ad_groups")
        if not isinstance(groups, list) or len(groups) != campaign.get(
            "recommended_ad_group_count"
        ):
            raise HierarchyValidationError(
                f"campaign output {position} count does not match Ad Group slots"
            )
        campaign_share = float(campaign.get("budget_seed_share", -1))
        group_shares = [float(group.get("budget_seed_share", -1)) for group in groups]
        if not math.isclose(math.fsum(group_shares), campaign_share, abs_tol=1e-12):
            raise HierarchyValidationError(
                f"campaign output {position} Ad Group shares do not conserve Campaign share"
            )
        campaign_shares.append(campaign_share)
        if has_budget:
            campaign_amount = float(campaign.get("campaign_budget_seed", -1))
            group_amounts = [float(group.get("initial_daily_budget", -1)) for group in groups]
            if not math.isclose(math.fsum(group_amounts), campaign_amount, abs_tol=1e-9):
                raise HierarchyValidationError(
                    f"campaign output {position} Ad Group budgets do not conserve Campaign budget"
                )
            campaign_amounts.append(campaign_amount)
    if not math.isclose(math.fsum(campaign_shares), 1.0, abs_tol=1e-12):
        raise HierarchyValidationError("Campaign shares do not sum to 1")
    if has_budget and not math.isclose(
        math.fsum(campaign_amounts), float(recommendation["budget_seed_total"]), abs_tol=1e-9
    ):
        raise HierarchyValidationError("Campaign budgets do not conserve Group budget")


def load_aligned_strategy_inputs(
    data_dir: str | Path,
    attribution_path: str | Path | None = None,
    entity_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    """Load v4 inputs and verify that the referenced AMC evidence is unchanged and in scope."""

    root = Path(data_dir)
    missing = [name for name in REQUIRED_INPUT_FILES if not (root / name).is_file()]
    if missing:
        raise HierarchyValidationError(f"missing required sample file(s): {', '.join(missing)}")
    unexpected = sorted(path.name for path in root.iterdir() if path.name not in EXPECTED_INPUT_ENTRIES)
    if unexpected:
        raise HierarchyValidationError(
            "unrelated content must not be stored in the input directory: " + ", ".join(unexpected)
        )

    request = _read_json(root / "strategy_request.json")
    pool = _read_json(root / "candidate_pool.json")
    source = request.get("mta_source")
    if not isinstance(source, dict):
        raise HierarchyValidationError("strategy_request.mta_source must be an object")
    attribution = _resolve_evidence_path(
        attribution_path,
        _required_text(source.get("attribution_file"), "mta_source.attribution_file"),
        "AMC attribution file",
    )
    entity = _resolve_evidence_path(
        entity_path,
        _required_text(source.get("entity_file"), "mta_source.entity_file"),
        "AMC entity file",
    )
    if _sha256(attribution) != _required_text(
        source.get("attribution_sha256"), "mta_source.attribution_sha256"
    ):
        raise HierarchyValidationError("AMC attribution SHA-256 does not match strategy_request")
    if _sha256(entity) != _required_text(
        source.get("entity_sha256"), "mta_source.entity_sha256"
    ):
        raise HierarchyValidationError("AMC entity SHA-256 does not match strategy_request")

    attribution_rows = _read_csv(attribution)
    entity_rows = _read_csv(entity)
    touchpoint_count = len({row.get("touchpoint", "") for row in attribution_rows})
    if touchpoint_count != _integer(
        source.get("available_touchpoint_count"),
        "mta_source.available_touchpoint_count",
        minimum=1,
    ):
        raise HierarchyValidationError("AMC attribution touchpoint count does not match strategy_request")
    if len(entity_rows) != _integer(
        source.get("entity_row_count"), "mta_source.entity_row_count", minimum=1
    ):
        raise HierarchyValidationError("AMC entity row count does not match strategy_request")

    group = request.get("campaign_group")
    if not isinstance(group, dict):
        raise HierarchyValidationError("campaign_group must be an object")
    scope = {
        "report_start_date": source.get("report_start_date"),
        "report_end_date": source.get("report_end_date"),
        "marketplace": group.get("marketplace"),
        "advertiser_id": group.get("advertiser_id"),
        "campaign_group_id": group.get("campaign_group_id"),
    }
    if source.get("marketplace") != group.get("marketplace") or source.get(
        "advertiser_id"
    ) != group.get("advertiser_id"):
        raise HierarchyValidationError("mta_source scope does not match Campaign Group")
    campaigns = request.get("campaigns")
    if not isinstance(campaigns, list):
        raise HierarchyValidationError("campaigns must be a list")
    campaign_products = {
        row.get("campaign_id"): row.get("ad_product")
        for row in campaigns
        if isinstance(row, dict)
    }
    for row in entity_rows:
        if any(row.get(field) != expected for field, expected in scope.items()):
            raise HierarchyValidationError("AMC entity scope does not match strategy input")
        product = row.get("touchpoint", "").split(":", 1)[0]
        if campaign_products.get(row.get("campaign_id")) != product:
            raise HierarchyValidationError("AMC entity Campaign/ad_product does not match strategy input")

    if request.get("sample_version") != SUPPORTED_SAMPLE_VERSION or pool.get(
        "sample_version"
    ) != SUPPORTED_SAMPLE_VERSION:
        raise HierarchyValidationError(f"sample_version must be {SUPPORTED_SAMPLE_VERSION}")
    return request, pool, attribution_rows, entity_rows


def validate_simulated_hierarchy(
    data_dir: str | Path,
    recommendation_path: str | Path,
    attribution_path: str | Path | None = None,
    entity_path: str | Path | None = None,
) -> dict[str, Any]:
    request, pool, attribution_rows, entity_rows = load_aligned_strategy_inputs(
        data_dir, attribution_path, entity_path
    )
    recommendation_file = Path(recommendation_path)
    if not recommendation_file.is_file():
        raise HierarchyValidationError(f"missing recommendation fixture: {recommendation_file}")
    recommendation = _read_json(recommendation_file)
    forbidden = _forbidden_paths(recommendation)
    if forbidden:
        raise HierarchyValidationError(
            "budget-only output contains forbidden strategy field(s): " + ", ".join(forbidden)
        )
    try:
        expected = generate_budget_recommendation(
            request, pool, attribution_rows, entity_rows
        )
    except BudgetRecommendationError as exc:
        raise HierarchyValidationError(str(exc)) from exc
    difference = _first_difference(expected, recommendation)
    if difference:
        raise HierarchyValidationError(
            f"recommendation does not match generated budget seed at {difference}"
        )
    _validate_budget_invariants(recommendation)

    campaigns = expected["campaigns"]
    return {
        "campaign_group_id": expected["campaign_group_id"],
        "campaign_count": len(campaigns),
        "recommended_ad_group_count": sum(
            campaign["recommended_ad_group_count"] for campaign in campaigns
        ),
        "recommended_ad_group_counts": {
            campaign["campaign_id"]: campaign["recommended_ad_group_count"]
            for campaign in campaigns
        },
        "attribution_touchpoint_count": expected["budget_derivation"][
            "attribution_touchpoint_count"
        ],
        "entity_row_count": expected["budget_derivation"]["entity_row_count"],
        "normalization_universe": NORMALIZATION_UNIVERSE,
        "has_budget_baseline": "budget_seed_total" in expected,
        "recommendation_type": expected["recommendation_type"],
        "warnings": expected["warnings"],
    }
