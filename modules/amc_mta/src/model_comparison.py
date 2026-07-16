from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from amc_mta_attribution import (
    NULL,
    PATH_FIELD_DESCRIPTIONS,
    safe_float,
    safe_int,
    validate_amc_aggregated_row,
)
from touchpoint_key import canonicalize_amc_touchpoint_key


OUTCOME_FIELDS = {
    "converted_users": ("converted_user_share", "attributed_converted_users"),
    "purchase_count": ("purchase_count_share", "attributed_purchase_count"),
    "revenue": ("revenue_share", "attributed_revenue"),
}

MODEL_OUTPUT_FIELDS = [
    "attribution_model",
    "touchpoint",
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
]

TOUCHPOINT_COMPARISON_FIELDS = [
    "touchpoint",
    "parent_touchpoint",
    "interaction_type",
    "outcome",
    "markov_share",
    "shapley_share",
    "markov_attributed_value",
    "shapley_attributed_value",
    "mean_share",
    "gap_pp",
    "signed_gap_pp",
    "relative_gap",
    "model_low",
    "model_high",
    "impressions",
    "clicks",
    "cost",
    "reported_purchases",
    "reported_sales",
    "markov_roas",
    "shapley_roas",
    "markov_roi",
    "shapley_roi",
    "markov_cpa",
    "shapley_cpa",
    "markov_cost_per_converted_user",
    "shapley_cost_per_converted_user",
    "raw_unique_paths",
    "raw_converted_users",
    "raw_purchase_count",
    "raw_revenue",
    "support_level",
    "parent_support_level",
    "markov_interval_low",
    "markov_interval_high",
    "shapley_interval_low",
    "shapley_interval_high",
    "gap_direction",
    "gap_direction_rate",
    "top5_entry_rate",
    "difference_level",
    "comparison_status",
    "critical_divergence",
    "parent_difference_level",
    "operational_status",
    "stability_level",
    "decision_status",
    "official_model",
    "official_share",
    "decision_value",
    "review_required",
    "automation_allowed",
    "reason_code",
]

SUMMARY_FIELDS = [
    "outcome",
    "grain",
    "report_start_date",
    "report_end_date",
    "max_touchpoint_gap_days",
    "reference_window_days",
    "touchpoint_count",
    "tvd",
    "spearman_rho",
    "top_k",
    "top_k_overlap",
    "top_k_overlap_rate",
    "critical_divergence_count",
    "distribution_gap",
    "rank_consistency",
    "support_status",
    "stability_status",
    "operational_status",
    "validation_error_count",
    "validation_reason_code",
    "comparison_status",
    "decision_status",
]

RECOMMENDED_FIELDS = [
    "touchpoint",
    "parent_touchpoint",
    "interaction_type",
    "outcome",
    "official_model",
    "official_share",
    "benchmark_model",
    "benchmark_share",
    "model_low",
    "model_high",
    "gap_pp",
    "difference_level",
    "support_level",
    "stability_level",
    "decision_status",
    "decision_value",
    "review_required",
    "automation_allowed",
    "reason_code",
]

_SHARED_PERFORMANCE_FIELDS = (
    "impressions",
    "clicks",
    "cost",
    "reported_purchases",
    "reported_sales",
)
_EFFICIENCY_FIELDS = ("roas", "roi", "cpa", "cost_per_converted_user")
_SHARE_TOLERANCE = 1e-6
_GAP_PP_TOLERANCE = 1e-6
_EFFICIENCY_TOLERANCE = 5e-7


@dataclass(frozen=True)
class ComparisonArtifacts:
    touchpoints: list[dict]
    summary: list[dict]
    recommended: list[dict]


def read_amc_csv_strict(path: str | Path) -> list[dict]:
    """Read the physical AMC path contract without silently normalizing it."""
    path = Path(path)
    expected_fields = list(PATH_FIELD_DESCRIPTIONS)
    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != expected_fields:
            raise ValueError(
                f"{path}: physical AMC header must exactly match {expected_fields}; "
                f"got={reader.fieldnames}"
            )
        rows: list[dict] = []
        description_count = 0
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"{path}: AMC row {row_number} contains extra column value(s)"
                )
            if set(row) != set(expected_fields):
                raise ValueError(f"{path}: AMC row {row_number} has missing columns")
            if any(value is None for value in row.values()):
                raise ValueError(f"{path}: AMC row {row_number} has missing columns")
            if row == PATH_FIELD_DESCRIPTIONS:
                description_count += 1
                if description_count > 1:
                    raise ValueError(f"{path}: AMC report contains multiple description rows")
                continue
            for field, value in row.items():
                if value != value.strip():
                    raise ValueError(
                        f"{path}: AMC row {row_number} field {field!r} contains surrounding whitespace"
                    )
            rows.append(row)
    return rows


def _finite_non_negative(
    value: object,
    context: str,
    *,
    blank_ok: bool = False,
    negative_ok: bool = False,
) -> float | str:
    if value in (None, ""):
        if blank_ok:
            return ""
        raise ValueError(f"{context} is required")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric") from exc
    if not math.isfinite(number) or (number < 0 and not negative_ok):
        qualifier = "finite" if negative_ok else "finite and non-negative"
        raise ValueError(f"{context} must be {qualifier}")
    return number


def _parent_touchpoint(touchpoint: str) -> str:
    return touchpoint.rsplit(":", 1)[0]


def _model_index(rows: Sequence[Mapping[str, object]], expected_model: str) -> dict[str, dict]:
    if not rows:
        raise ValueError(f"{expected_model} model output must contain at least one row")
    indexed: dict[str, dict] = {}
    for row_number, source in enumerate(rows, start=2):
        row = dict(source)
        model = str(row.get("attribution_model", ""))
        if model != expected_model:
            raise ValueError(
                f"{expected_model} row {row_number}: attribution_model must be {expected_model!r}"
            )
        raw_touchpoint = str(row.get("touchpoint", ""))
        try:
            touchpoint = canonicalize_amc_touchpoint_key(raw_touchpoint)
        except ValueError as exc:
            raise ValueError(f"{expected_model} row {row_number}: invalid touchpoint") from exc
        if touchpoint != raw_touchpoint:
            raise ValueError(
                f"{expected_model} row {row_number}: touchpoint must be canonical"
            )
        if touchpoint in indexed:
            raise ValueError(f"{expected_model}: duplicate touchpoint {touchpoint}")
        interaction_type = touchpoint.rsplit(":", 1)[1]
        if row.get("interaction_type") != interaction_type:
            raise ValueError(
                f"{expected_model} row {row_number}: interaction_type does not match touchpoint"
            )
        for share_field, attributed_field in OUTCOME_FIELDS.values():
            row[share_field] = _finite_non_negative(
                row.get(share_field), f"{expected_model} {touchpoint} {share_field}"
            )
            row[attributed_field] = _finite_non_negative(
                row.get(attributed_field), f"{expected_model} {touchpoint} {attributed_field}"
            )
        for field in _SHARED_PERFORMANCE_FIELDS:
            row[field] = _finite_non_negative(
                row.get(field), f"{expected_model} {touchpoint} {field}"
            )
            if field in {"impressions", "clicks", "reported_purchases"} and not float(
                row[field]
            ).is_integer():
                raise ValueError(
                    f"{expected_model} {touchpoint} {field} must be a non-negative integer"
                )
        for field in _EFFICIENCY_FIELDS:
            row[field] = _finite_non_negative(
                row.get(field),
                f"{expected_model} {touchpoint} {field}",
                blank_ok=True,
                negative_ok=field == "roi",
            )
        indexed[touchpoint] = row
    return indexed


def _validate_efficiency(model_name: str, touchpoint: str, row: Mapping[str, object]) -> None:
    cost = float(row["cost"])
    actual = {field: row[field] for field in _EFFICIENCY_FIELDS}
    if cost == 0:
        if any(value != "" for value in actual.values()):
            raise ValueError(
                f"{model_name} {touchpoint}: zero cost requires blank efficiency fields"
            )
        return

    revenue = float(row["attributed_revenue"])
    purchase_count = float(row["attributed_purchase_count"])
    converted_users = float(row["attributed_converted_users"])
    expected = {
        "roas": revenue / cost,
        "roi": (revenue - cost) / cost,
        "cpa": "" if purchase_count <= 0 else cost / purchase_count,
        "cost_per_converted_user": "" if converted_users <= 0 else cost / converted_users,
    }
    if actual["roi"] != "" and float(actual["roi"]) < -1 - _EFFICIENCY_TOLERANCE:
        raise ValueError(f"{model_name} {touchpoint}: ROI must be >= -1")
    for field, expected_value in expected.items():
        actual_value = actual[field]
        if expected_value == "":
            if actual_value != "":
                raise ValueError(
                    f"{model_name} {touchpoint}: {field} must be blank when its denominator is zero"
                )
        elif actual_value == "" or not math.isclose(
            float(actual_value),
            float(expected_value),
            rel_tol=0,
            abs_tol=_EFFICIENCY_TOLERANCE,
        ):
            raise ValueError(
                f"{model_name} {touchpoint}: {field} does not match attributed outcomes and cost"
            )


def _validate_models(
    markov_rows: Sequence[Mapping[str, object]],
    shapley_rows: Sequence[Mapping[str, object]],
    amc_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, dict], dict[str, dict], dict[str, float]]:
    markov = _model_index(markov_rows, "markov")
    shapley = _model_index(shapley_rows, "shapley")
    if set(markov) != set(shapley):
        missing = sorted(set(markov) - set(shapley))
        extra = sorted(set(shapley) - set(markov))
        raise ValueError(
            f"model touchpoint sets differ; missing in shapley={missing}, extra in shapley={extra}"
        )
    for touchpoint in markov:
        for field in _SHARED_PERFORMANCE_FIELDS:
            if not math.isclose(
                float(markov[touchpoint][field]),
                float(shapley[touchpoint][field]),
                rel_tol=0,
                abs_tol=_SHARE_TOLERANCE,
            ):
                raise ValueError(
                    f"model performance fields differ for {touchpoint}: {field}"
                )
        _validate_efficiency("markov", touchpoint, markov[touchpoint])
        _validate_efficiency("shapley", touchpoint, shapley[touchpoint])

    totals = {outcome: 0.0 for outcome in OUTCOME_FIELDS}
    if not amc_rows:
        raise ValueError("AMC report must contain at least one data row")
    amc_touchpoints: set[str] = set()
    scopes: set[tuple[str, str, str, str]] = set()
    for row_number, row in enumerate(amc_rows, start=2):
        parts = validate_amc_aggregated_row(row, row_number)
        amc_touchpoints.update(part for part in parts if part != NULL)
        scope_values = []
        for field in (
            "report_start_date",
            "report_end_date",
            "marketplace",
            "advertiser_id",
        ):
            value = str(row.get(field, "")).strip()
            if not value:
                raise ValueError(f"AMC row {row_number}: {field} is required")
            scope_values.append(value)
        scopes.add(tuple(scope_values))
        totals["converted_users"] += safe_int(row.get("converted_users"))
        totals["purchase_count"] += safe_int(row.get("purchase_count"))
        totals["revenue"] += safe_float(row.get("revenue"))
    if len(scopes) != 1:
        raise ValueError(
            "AMC report must contain one report window, marketplace, and advertiser_id"
        )
    if set(markov) != amc_touchpoints:
        missing = sorted(amc_touchpoints - set(markov))
        extra = sorted(set(markov) - amc_touchpoints)
        raise ValueError(
            f"model/AMC touchpoint sets differ; missing in models={missing}, extra in models={extra}"
        )

    for outcome, (share_field, attributed_field) in OUTCOME_FIELDS.items():
        model_totals = {}
        for model_name, indexed in (("markov", markov), ("shapley", shapley)):
            share_total = sum(float(row[share_field]) for row in indexed.values())
            attributed_total = sum(float(row[attributed_field]) for row in indexed.values())
            model_totals[model_name] = attributed_total
            if totals[outcome] == 0:
                if abs(share_total) > _SHARE_TOLERANCE or abs(attributed_total) > _SHARE_TOLERANCE:
                    raise ValueError(
                        f"{model_name} {outcome}: zero outcome requires zero shares and attribution"
                    )
            else:
                if not math.isclose(share_total, 1.0, rel_tol=0, abs_tol=_SHARE_TOLERANCE):
                    raise ValueError(
                        f"{model_name} {outcome}: shares do not sum to 1 (got {share_total})"
                    )
                rounding_unit = 0.01 if outcome == "revenue" else 0.0001
                tolerance = max(_SHARE_TOLERANCE, len(indexed) * rounding_unit)
                if not math.isclose(
                    attributed_total, totals[outcome], rel_tol=0, abs_tol=tolerance
                ):
                    raise ValueError(
                        f"{model_name} {outcome}: attributed total does not match AMC total"
                    )
        if (model_totals["markov"] == 0) != (model_totals["shapley"] == 0):
            raise ValueError(f"{outcome}: only one model has a zero outcome")

        attributed_rounding = 0.01 if outcome == "revenue" else 0.0001
        for model_name, indexed in (("markov", markov), ("shapley", shapley)):
            for touchpoint, row in indexed.items():
                expected_value = float(row[share_field]) * totals[outcome]
                # Both columns use independent largest-remainder allocation, so
                # either may move by one complete output unit at a row boundary.
                tolerance = totals[outcome] * 1e-6 + attributed_rounding
                if not math.isclose(
                    float(row[attributed_field]),
                    expected_value,
                    rel_tol=0,
                    abs_tol=tolerance,
                ):
                    raise ValueError(
                        f"{model_name} {touchpoint} {outcome}: attributed value does not match share × AMC total"
                    )
    return markov, shapley, totals


def _support_level(support: Mapping[str, float]) -> str:
    if (
        support["raw_purchase_count"] >= 100
        and support["raw_converted_users"] >= 50
        and support["raw_unique_paths"] >= 10
    ):
        return "FULL_SUPPORT"
    if (
        support["raw_purchase_count"] >= 30
        and support["raw_converted_users"] >= 20
        and support["raw_unique_paths"] >= 5
    ):
        return "LIMITED_SUPPORT"
    return "LOW_SUPPORT"


def calculate_raw_support(
    amc_rows: Sequence[Mapping[str, object]], *, grain: str = "FIVE_PART"
) -> dict[str, dict]:
    if grain not in {"FIVE_PART", "FOUR_PART"}:
        raise ValueError("grain must be FIVE_PART or FOUR_PART")
    grouped: dict[str, dict] = defaultdict(
        lambda: {
            "path_keys": set(),
            "raw_converted_users": 0,
            "raw_purchase_count": 0,
            "raw_revenue": 0.0,
        }
    )
    for row_number, row in enumerate(amc_rows, start=2):
        parts = validate_amc_aggregated_row(row, row_number)
        touchpoints = [part for part in parts if part != NULL]
        projected_path = [
            touchpoint if grain == "FIVE_PART" else _parent_touchpoint(touchpoint)
            for touchpoint in touchpoints
        ]
        normalized_path = " > ".join(projected_path)
        keys = set(projected_path)
        for key in keys:
            support = grouped[key]
            support["path_keys"].add(normalized_path)
            support["raw_converted_users"] += safe_int(row.get("converted_users"))
            support["raw_purchase_count"] += safe_int(row.get("purchase_count"))
            support["raw_revenue"] += safe_float(row.get("revenue"))

    results = {}
    for key, support in grouped.items():
        row = {
            "raw_unique_paths": len(support["path_keys"]),
            "raw_converted_users": support["raw_converted_users"],
            "raw_purchase_count": support["raw_purchase_count"],
            "raw_revenue": round(support["raw_revenue"], 6),
        }
        row["support_level"] = _support_level(row)
        results[key] = row
    return results


def classify_difference(markov_share: float, shapley_share: float) -> tuple[str, str, bool]:
    mean_share = (markov_share + shapley_share) / 2
    gap_pp = abs(markov_share - shapley_share) * 100
    relative_gap = 0.0 if mean_share == 0 else abs(markov_share - shapley_share) / mean_share
    critical = mean_share >= 0.10 - 1e-12 and gap_pp >= 5.0 - 1e-9
    if mean_share < 0.01 - 1e-12:
        reason = "LONG_TAIL_MODEL_SENSITIVE" if relative_gap >= 0.30 else "LONG_TAIL"
        return "LONG_TAIL", reason, critical
    if gap_pp <= 1.0 + 1e-9 and relative_gap <= 0.20 + 1e-12:
        return "SMALL", "ALIGNED", critical
    if gap_pp >= 3.0 - 1e-9:
        return "LARGE", "ABSOLUTE_GAP", critical
    if (
        mean_share >= 0.03 - 1e-12
        and gap_pp >= 1.5 - 1e-9
        and relative_gap >= 0.50 - 1e-12
    ):
        return "LARGE", "RELATIVE_AND_ABSOLUTE_GAP", critical
    return "MEDIUM", "MODEL_REVIEW", critical


def _comparison_status(difference_level: str) -> str:
    return {
        "SMALL": "ALIGNED",
        "MEDIUM": "REVIEW",
        "LARGE": "DIVERGENT",
        "LONG_TAIL": "LONG_TAIL",
    }[difference_level]


def _parent_reason(child_level: str, parent_level: str) -> str:
    if child_level == "LARGE":
        return (
            "INTERACTION_ALLOCATION_DIVERGENCE"
            if parent_level == "SMALL"
            else "TOUCHPOINT_DIVERGENCE"
        )
    if child_level == "MEDIUM":
        return (
            "INTERACTION_ALLOCATION_REVIEW"
            if parent_level == "SMALL"
            else "PARENT_TOUCHPOINT_REVIEW"
        )
    if child_level in {"SMALL", "LONG_TAIL"} and parent_level in {"MEDIUM", "LARGE"}:
        return "PARENT_AGGREGATE_DIVERGENCE"
    return ""


def _rank(values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(values, key=lambda key: (-values[key], key))
    ranks: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and math.isclose(
            values[ordered[end]], values[ordered[index]], rel_tol=0, abs_tol=1e-15
        ):
            end += 1
        average_rank = ((index + 1) + end) / 2
        for key in ordered[index:end]:
            ranks[key] = average_rank
        index = end
    return ranks


def spearman_rho(markov: Mapping[str, float], shapley: Mapping[str, float]) -> float | None:
    if len(markov) < 2 or set(markov) != set(shapley):
        return None
    if len(set(markov.values())) == 1 or len(set(shapley.values())) == 1:
        return None
    left = _rank(markov)
    right = _rank(shapley)
    left_mean = sum(left.values()) / len(left)
    right_mean = sum(right.values()) / len(right)
    covariance = sum((left[key] - left_mean) * (right[key] - right_mean) for key in left)
    left_ss = sum((value - left_mean) ** 2 for value in left.values())
    right_ss = sum((value - right_mean) ** 2 for value in right.values())
    denominator = math.sqrt(left_ss * right_ss)
    return None if denominator == 0 else covariance / denominator


def _aggregate_by_parent(indexed: Mapping[str, Mapping[str, object]], field: str) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for touchpoint, row in indexed.items():
        totals[_parent_touchpoint(touchpoint)] += float(row[field])
    return dict(totals)


def _overall_metrics(
    markov: Mapping[str, float], shapley: Mapping[str, float], critical_count: int
) -> dict:
    if not any(markov.values()) and not any(shapley.values()):
        return {
            "tvd": "",
            "spearman_rho": "",
            "top_k": min(5, len(markov)),
            "top_k_overlap": "",
            "top_k_overlap_rate": "",
            "distribution_gap": "NO_OUTCOME",
            "rank_consistency": "UNDEFINED",
            "comparison_status": "NO_OUTCOME",
        }
    tvd = 0.5 * sum(abs(markov[key] - shapley[key]) for key in markov)
    rho = spearman_rho(markov, shapley)
    k = min(5, len(markov))
    top_markov = set(sorted(markov, key=lambda key: (-markov[key], key))[:k])
    top_shapley = set(sorted(shapley, key=lambda key: (-shapley[key], key))[:k])
    overlap = len(top_markov & top_shapley)
    overlap_rate = 0.0 if k == 0 else overlap / k
    distribution_gap = "SMALL" if tvd <= 0.05 else "MEDIUM" if tvd <= 0.12 else "LARGE"
    rank_consistency = (
        "UNDEFINED"
        if rho is None
        else "HIGH"
        if rho >= 0.90
        else "MEDIUM"
        if rho >= 0.75
        else "LOW"
    )
    if rho is None:
        comparison_status = "MIXED_REVIEW"
    elif tvd <= 0.05 and rho >= 0.90 and overlap_rate >= 0.80 and critical_count == 0:
        comparison_status = "CONSISTENT"
    elif tvd > 0.12 or rho < 0.75 or overlap_rate < 0.60:
        comparison_status = "MODEL_DIVERGENT"
    else:
        comparison_status = "MIXED_REVIEW"
    return {
        "tvd": round(tvd, 9),
        "spearman_rho": "" if rho is None else round(rho, 9),
        "top_k": k,
        "top_k_overlap": overlap,
        "top_k_overlap_rate": round(overlap_rate, 9),
        "distribution_gap": distribution_gap,
        "rank_consistency": rank_consistency,
        "comparison_status": comparison_status,
    }


def _aggregate_support_status(support_rows: Iterable[Mapping[str, object]]) -> str:
    levels = {str(row["support_level"]) for row in support_rows}
    if "LOW_SUPPORT" in levels:
        return "LOW_SUPPORT"
    if "LIMITED_SUPPORT" in levels:
        return "LIMITED_SUPPORT"
    return "FULL_SUPPORT"


def compare_attribution_models(
    markov_rows: Sequence[Mapping[str, object]],
    shapley_rows: Sequence[Mapping[str, object]],
    amc_rows: Sequence[Mapping[str, object]],
    *,
    max_touchpoint_gap_days: int = 14,
    reference_window_days: int = 7,
) -> ComparisonArtifacts:
    for name, value in (
        ("max_touchpoint_gap_days", max_touchpoint_gap_days),
        ("reference_window_days", reference_window_days),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    markov, shapley, totals = _validate_models(markov_rows, shapley_rows, amc_rows)
    support_five = calculate_raw_support(amc_rows, grain="FIVE_PART")
    support_four = calculate_raw_support(amc_rows, grain="FOUR_PART")
    windows = {
        (str(row.get("report_start_date", "")), str(row.get("report_end_date", "")))
        for row in amc_rows
    }
    if len(windows) != 1:
        raise ValueError("AMC report must contain exactly one report window")
    report_start_date, report_end_date = next(iter(windows))

    touchpoint_rows: list[dict] = []
    summary_rows: list[dict] = []
    for outcome, (share_field, attributed_field) in OUTCOME_FIELDS.items():
        is_zero_outcome = totals[outcome] == 0
        parent_markov = _aggregate_by_parent(markov, share_field)
        parent_shapley = _aggregate_by_parent(shapley, share_field)
        parent_levels = {
            parent: (
                "NO_OUTCOME"
                if is_zero_outcome
                else classify_difference(parent_markov[parent], parent_shapley[parent])[0]
            )
            for parent in parent_markov
        }
        for touchpoint in sorted(markov):
            markov_row = markov[touchpoint]
            shapley_row = shapley[touchpoint]
            markov_share = float(markov_row[share_field])
            shapley_share = float(shapley_row[share_field])
            mean_share = (markov_share + shapley_share) / 2
            gap_pp = abs(markov_share - shapley_share) * 100
            signed_gap_pp = (markov_share - shapley_share) * 100
            relative_gap = 0.0 if mean_share == 0 else abs(markov_share - shapley_share) / mean_share
            if is_zero_outcome:
                difference_level, reason, critical = "NO_OUTCOME", "NO_OUTCOME", False
            else:
                difference_level, reason, critical = classify_difference(
                    markov_share, shapley_share
                )
            parent = _parent_touchpoint(touchpoint)
            parent_level = parent_levels[parent]
            parent_reason = (
                "" if is_zero_outcome else _parent_reason(difference_level, parent_level)
            )
            reason_code = "|".join(code for code in (reason, parent_reason) if code)
            support = support_five[touchpoint]
            parent_support = support_four[parent]
            touchpoint_rows.append(
                {
                    "touchpoint": touchpoint,
                    "parent_touchpoint": parent,
                    "interaction_type": touchpoint.rsplit(":", 1)[1],
                    "outcome": outcome,
                    "markov_share": round(markov_share, 9),
                    "shapley_share": round(shapley_share, 9),
                    "markov_attributed_value": markov_row[attributed_field],
                    "shapley_attributed_value": shapley_row[attributed_field],
                    "mean_share": round(mean_share, 9),
                    "gap_pp": round(gap_pp, 6),
                    "signed_gap_pp": round(signed_gap_pp, 6),
                    "relative_gap": round(relative_gap, 9),
                    "model_low": round(min(markov_share, shapley_share), 9),
                    "model_high": round(max(markov_share, shapley_share), 9),
                    **{field: markov_row[field] for field in _SHARED_PERFORMANCE_FIELDS},
                    **{f"markov_{field}": markov_row[field] for field in _EFFICIENCY_FIELDS},
                    **{f"shapley_{field}": shapley_row[field] for field in _EFFICIENCY_FIELDS},
                    "raw_unique_paths": support["raw_unique_paths"],
                    "raw_converted_users": support["raw_converted_users"],
                    "raw_purchase_count": support["raw_purchase_count"],
                    "raw_revenue": support["raw_revenue"],
                    "support_level": support["support_level"],
                    "parent_support_level": parent_support["support_level"],
                    "markov_interval_low": "",
                    "markov_interval_high": "",
                    "shapley_interval_low": "",
                    "shapley_interval_high": "",
                    "gap_direction": (
                        "TIE"
                        if abs(signed_gap_pp) <= _GAP_PP_TOLERANCE
                        else "MARKOV_HIGH"
                        if signed_gap_pp > 0
                        else "SHAPLEY_HIGH"
                    ),
                    "gap_direction_rate": "",
                    "top5_entry_rate": "",
                    "difference_level": difference_level,
                    "comparison_status": (
                        "NO_OUTCOME"
                        if is_zero_outcome
                        else _comparison_status(difference_level)
                    ),
                    "critical_divergence": str(critical).lower(),
                    "parent_difference_level": parent_level,
                    "operational_status": "VALID",
                    "stability_level": "UNVERIFIED",
                    "decision_status": (
                        "NO_OUTCOME" if is_zero_outcome else "EVIDENCE_UNVERIFIED"
                    ),
                    "official_model": "MARKOV",
                    "official_share": "" if is_zero_outcome else round(markov_share, 9),
                    "decision_value": "",
                    "review_required": "false" if is_zero_outcome else "true",
                    "automation_allowed": "false",
                    "reason_code": reason_code,
                }
            )

        for grain, grain_markov, grain_shapley, support_rows in (
            ("FIVE_PART", {key: float(row[share_field]) for key, row in markov.items()}, {key: float(row[share_field]) for key, row in shapley.items()}, support_five),
            ("FOUR_PART", parent_markov, parent_shapley, support_four),
        ):
            critical_count = sum(
                (
                    False
                    if is_zero_outcome
                    else classify_difference(grain_markov[key], grain_shapley[key])[2]
                )
                for key in grain_markov
            )
            metrics = _overall_metrics(grain_markov, grain_shapley, critical_count)
            summary_rows.append(
                {
                    "outcome": outcome,
                    "grain": grain,
                    "report_start_date": report_start_date,
                    "report_end_date": report_end_date,
                    "max_touchpoint_gap_days": max_touchpoint_gap_days,
                    "reference_window_days": reference_window_days,
                    "touchpoint_count": len(grain_markov),
                    **metrics,
                    "critical_divergence_count": critical_count,
                    "support_status": _aggregate_support_status(support_rows.values()),
                    "stability_status": "UNVERIFIED",
                    "operational_status": "VALID",
                    "validation_error_count": 0,
                    "validation_reason_code": "",
                    "decision_status": (
                        "NO_OUTCOME" if is_zero_outcome else "EVIDENCE_UNVERIFIED"
                    ),
                }
            )

    recommended_rows = [
        {
            "touchpoint": row["touchpoint"],
            "parent_touchpoint": row["parent_touchpoint"],
            "interaction_type": row["interaction_type"],
            "outcome": row["outcome"],
            "official_model": row["official_model"],
            "official_share": row["official_share"],
            "benchmark_model": "PATH_LEVEL_SHAPLEY",
            "benchmark_share": row["shapley_share"],
            "model_low": row["model_low"],
            "model_high": row["model_high"],
            "gap_pp": row["gap_pp"],
            "difference_level": row["difference_level"],
            "support_level": row["support_level"],
            "stability_level": row["stability_level"],
            "decision_status": row["decision_status"],
            "decision_value": "",
            "review_required": row["review_required"],
            "automation_allowed": row["automation_allowed"],
            "reason_code": row["reason_code"],
        }
        for row in touchpoint_rows
    ]
    return ComparisonArtifacts(touchpoint_rows, summary_rows, recommended_rows)
