"""Compare two attribution models and judge the result's reliability.

Consumes both models' published rows plus the path report, validates that they
describe the same report, then reports where they agree and whether the agreement
can be trusted.

Data flow: Markov rows + Shapley rows + path rows
  -> `_validate_models`   : identical touchpoint sets, conservation, efficiency
  -> per-touchpoint gaps  : gap in percentage points and relative gap
  -> `_overall_metrics`   : total variation distance, Spearman rho, top-k overlap
  -> three artifacts      : touchpoint comparison, summary, recommended value

Reliability is a fixed three-criterion contract: calculation validity, raw data
support, and cross-model consistency. All three must pass for a touchpoint to be
labelled `RELIABLE`, and the recommended value falls back to the interval between
the two models when it is not.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping, Sequence

from attribution_contract import (
    NULL,
    PATH_FIELD_DESCRIPTIONS,
    read_csv_normalized,
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
    "outcome",
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
]

SUMMARY_FIELDS = [
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
]

RECOMMENDED_FIELDS = [
    "touchpoint",
    "interaction_type",
    "outcome",
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
_EFFICIENCY_TOLERANCE = 5e-7
_MIN_SUPPORT_PURCHASE_COUNT = 30
_MIN_SUPPORT_CONVERTED_USERS = 20
_MIN_SUPPORT_UNIQUE_PATHS = 5
_MAX_CONSISTENT_GAP_PP = Decimal("1.0")
_MAX_CONSISTENT_RELATIVE_GAP = Decimal("0.20")
_DECIMAL_SHARE_KEYS = {
    share_field: f"__decimal_{share_field}"
    for share_field, _ in OUTCOME_FIELDS.values()
}


@dataclass(frozen=True)
class ComparisonArtifacts:
    touchpoints: list[dict]
    summary: list[dict]
    recommended: list[dict]


def read_amc_csv_strict(path: str | Path) -> list[dict]:
    """Read the AMC path contract after normalizing field and value edges."""
    path = Path(path)
    expected_fields = list(PATH_FIELD_DESCRIPTIONS)
    fieldnames, normalized_rows = read_csv_normalized(path)
    if fieldnames != expected_fields:
        raise ValueError(
            f"{path}: normalized AMC header must exactly match {expected_fields}; "
            f"got={fieldnames}"
        )

    rows: list[dict] = []
    description_count = 0
    for row in normalized_rows:
        if row == PATH_FIELD_DESCRIPTIONS:
            description_count += 1
            if description_count > 1:
                raise ValueError(f"{path}: AMC report contains multiple description rows")
            continue
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


def _preserve_share_decimal(value: object, normalized: float) -> Decimal:
    """Preserve text/Decimal share precision while retaining the legacy float path."""
    if isinstance(value, (str, Decimal)):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            pass
    return Decimal(str(normalized))


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
            raw_share = row.get(share_field)
            normalized_share = _finite_non_negative(
                raw_share, f"{expected_model} {touchpoint} {share_field}"
            )
            row[share_field] = normalized_share
            row[_DECIMAL_SHARE_KEYS[share_field]] = _preserve_share_decimal(
                raw_share, normalized_share
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
        try:
            report_start_date = date.fromisoformat(scope_values[0])
            report_end_date = date.fromisoformat(scope_values[1])
        except ValueError as exc:
            raise ValueError(
                f"AMC row {row_number}: report dates must be ISO dates"
            ) from exc
        if report_start_date > report_end_date:
            raise ValueError(f"AMC row {row_number}: report window is inverted")
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


def data_support_is_sufficient(support: Mapping[str, float]) -> bool:
    """Return whether all three minimum raw-support thresholds pass."""
    return (
        support["raw_purchase_count"] >= _MIN_SUPPORT_PURCHASE_COUNT
        and support["raw_converted_users"] >= _MIN_SUPPORT_CONVERTED_USERS
        and support["raw_unique_paths"] >= _MIN_SUPPORT_UNIQUE_PATHS
    )


def models_are_consistent(
    gap_pp: float | Decimal,
    relative_gap: float | Decimal,
    *,
    has_outcome: bool,
) -> bool:
    """Judge point-estimate consistency independently of difference labels."""
    if not has_outcome:
        return False
    try:
        gap = gap_pp if isinstance(gap_pp, Decimal) else Decimal(str(gap_pp))
        relative = (
            relative_gap
            if isinstance(relative_gap, Decimal)
            else Decimal(str(relative_gap))
        )
    except (InvalidOperation, TypeError, ValueError):
        return False
    if not gap.is_finite() or not relative.is_finite() or gap < 0 or relative < 0:
        return False
    return bool(
        gap <= _MAX_CONSISTENT_GAP_PP
        and relative <= _MAX_CONSISTENT_RELATIVE_GAP
    )


def _decimal_gap_metrics(
    markov_share: Decimal,
    shapley_share: Decimal,
) -> tuple[Decimal, Decimal]:
    """Calculate gap metrics from preserved, unrounded decimal shares."""
    mean_share = (markov_share + shapley_share) / Decimal("2")
    absolute_gap = abs(markov_share - shapley_share)
    relative_gap = Decimal("0") if mean_share == 0 else absolute_gap / mean_share
    return absolute_gap * Decimal("100"), relative_gap


def reliability_fields(
    calculation_valid: bool,
    data_support_sufficient: bool,
    models_consistent: bool,
) -> dict[str, str]:
    """Compose the fixed three-criterion reliability contract."""
    failures = []
    if not calculation_valid:
        failures.append("CALCULATION_INVALID")
    if not data_support_sufficient:
        failures.append("INSUFFICIENT_DATA_SUPPORT")
    if not models_consistent:
        failures.append("MODELS_INCONSISTENT")
    return {
        "calculation_valid": str(calculation_valid).lower(),
        "data_support_sufficient": str(data_support_sufficient).lower(),
        "models_consistent": str(models_consistent).lower(),
        "reliability_status": "UNRELIABLE" if failures else "RELIABLE",
        "reliability_reason": "|".join(failures) if failures else "ALL_CRITERIA_PASSED",
    }


def _recommended_value(row: Mapping[str, object], *, has_outcome: bool) -> float | str:
    """Select the official point value or the ordered model range."""
    if not has_outcome:
        return ""
    if row["reliability_status"] == "RELIABLE":
        return row["markov_share"]

    endpoints = []
    for value in (row["markov_share"], row["shapley_share"]):
        decimal_value = Decimal(str(value))
        display_value = "0.0" if decimal_value == 0 else str(value)
        endpoints.append((decimal_value, display_value))
    endpoints.sort(key=lambda endpoint: endpoint[0])
    return f"[{endpoints[0][1]},{endpoints[1][1]}]"


def calculate_raw_support(amc_rows: Sequence[Mapping[str, object]]) -> dict[str, dict]:
    """Calculate support for complete five-part touchpoints only."""
    grouped: dict[str, dict] = defaultdict(
        lambda: {
            "path_keys": set(),
            "raw_converted_users": 0,
            "raw_purchase_count": 0,
        }
    )
    for row_number, row in enumerate(amc_rows, start=2):
        parts = validate_amc_aggregated_row(row, row_number)
        touchpoints = [part for part in parts if part != NULL]
        normalized_path = " > ".join(touchpoints)
        keys = set(touchpoints)
        for key in keys:
            support = grouped[key]
            support["path_keys"].add(normalized_path)
            support["raw_converted_users"] += safe_int(row.get("converted_users"))
            support["raw_purchase_count"] += safe_int(row.get("purchase_count"))

    results = {}
    for key, support in grouped.items():
        row = {
            "raw_unique_paths": len(support["path_keys"]),
            "raw_converted_users": support["raw_converted_users"],
            "raw_purchase_count": support["raw_purchase_count"],
        }
        results[key] = row
    return results


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


def _overall_metrics(markov: Mapping[str, float], shapley: Mapping[str, float]) -> dict:
    if not any(markov.values()) and not any(shapley.values()):
        return {
            "tvd": "",
            "spearman_rho": "",
            "top_k_overlap_rate": "",
        }
    tvd = 0.5 * sum(abs(markov[key] - shapley[key]) for key in markov)
    rho = spearman_rho(markov, shapley)
    k = min(5, len(markov))
    top_markov = set(sorted(markov, key=lambda key: (-markov[key], key))[:k])
    top_shapley = set(sorted(shapley, key=lambda key: (-shapley[key], key))[:k])
    overlap = len(top_markov & top_shapley)
    overlap_rate = 0.0 if k == 0 else overlap / k
    return {
        "tvd": round(tvd, 9),
        "spearman_rho": "" if rho is None else round(rho, 9),
        "top_k_overlap_rate": round(overlap_rate, 9),
    }


def compare_attribution_models(
    markov_rows: Sequence[Mapping[str, object]],
    shapley_rows: Sequence[Mapping[str, object]],
    amc_rows: Sequence[Mapping[str, object]],
    *,
    max_touchpoint_gap_days: int = 14,
) -> ComparisonArtifacts:
    for name, value in (
        ("max_touchpoint_gap_days", max_touchpoint_gap_days),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    markov, shapley, totals = _validate_models(markov_rows, shapley_rows, amc_rows)
    support_five = calculate_raw_support(amc_rows)
    windows = {
        (str(row.get("report_start_date", "")), str(row.get("report_end_date", "")))
        for row in amc_rows
    }
    if len(windows) != 1:
        raise ValueError("AMC report must contain exactly one report window")
    report_start_date, report_end_date = next(iter(windows))

    zero_outcomes = {outcome for outcome, total in totals.items() if total == 0}
    touchpoint_rows: list[dict] = []
    summary_rows: list[dict] = []
    for outcome, (share_field, _) in OUTCOME_FIELDS.items():
        is_zero_outcome = totals[outcome] == 0
        outcome_reliability_rows: list[dict[str, str]] = []
        for touchpoint in sorted(markov):
            markov_row = markov[touchpoint]
            shapley_row = shapley[touchpoint]
            markov_share = float(markov_row[share_field])
            shapley_share = float(shapley_row[share_field])
            gap_pp_decimal, relative_gap_decimal = _decimal_gap_metrics(
                markov_row[_DECIMAL_SHARE_KEYS[share_field]],
                shapley_row[_DECIMAL_SHARE_KEYS[share_field]],
            )
            gap_pp = float(gap_pp_decimal)
            relative_gap = float(relative_gap_decimal)
            support = support_five[touchpoint]
            reliability = reliability_fields(
                calculation_valid=True,
                data_support_sufficient=(
                    not is_zero_outcome and data_support_is_sufficient(support)
                ),
                models_consistent=models_are_consistent(
                    gap_pp_decimal,
                    relative_gap_decimal,
                    has_outcome=not is_zero_outcome,
                ),
            )
            outcome_reliability_rows.append(reliability)
            touchpoint_rows.append(
                {
                    "touchpoint": touchpoint,
                    "outcome": outcome,
                    "markov_share": round(markov_share, 9),
                    "shapley_share": round(shapley_share, 9),
                    "gap_pp": round(gap_pp, 6),
                    "relative_gap": round(relative_gap, 9),
                    "raw_unique_paths": support["raw_unique_paths"],
                    "raw_converted_users": support["raw_converted_users"],
                    "raw_purchase_count": support["raw_purchase_count"],
                    **reliability,
                }
            )

        grain_markov = {key: float(row[share_field]) for key, row in markov.items()}
        grain_shapley = {key: float(row[share_field]) for key, row in shapley.items()}
        metrics = _overall_metrics(grain_markov, grain_shapley)
        summary_reliability = reliability_fields(
            calculation_valid=all(
                row["calculation_valid"] == "true"
                for row in outcome_reliability_rows
            ),
            data_support_sufficient=all(
                row["data_support_sufficient"] == "true"
                for row in outcome_reliability_rows
            ),
            models_consistent=all(
                row["models_consistent"] == "true"
                for row in outcome_reliability_rows
            ),
        )
        summary_rows.append(
            {
                "outcome": outcome,
                "report_start_date": report_start_date,
                "report_end_date": report_end_date,
                "max_touchpoint_gap_days": max_touchpoint_gap_days,
                "touchpoint_count": len(grain_markov),
                "tvd": metrics["tvd"],
                "spearman_rho": metrics["spearman_rho"],
                "top_k_overlap_rate": metrics["top_k_overlap_rate"],
                **summary_reliability,
            }
        )

    recommended_rows = []
    for row in touchpoint_rows:
        has_outcome = row["outcome"] not in zero_outcomes
        recommended_rows.append(
            {
                "touchpoint": row["touchpoint"],
                "interaction_type": row["touchpoint"].rsplit(":", 1)[1],
                "outcome": row["outcome"],
                "official_model": "MARKOV",
                "official_share": "" if not has_outcome else row["markov_share"],
                "recommended_value": _recommended_value(
                    row, has_outcome=has_outcome
                ),
                "benchmark_model": "PATH_LEVEL_SHAPLEY",
                "benchmark_share": row["shapley_share"],
                "gap_pp": row["gap_pp"],
                "relative_gap": row["relative_gap"],
                "calculation_valid": row["calculation_valid"],
                "data_support_sufficient": row["data_support_sufficient"],
                "models_consistent": row["models_consistent"],
                "reliability_status": row["reliability_status"],
                "reliability_reason": row["reliability_reason"],
            }
        )
    return ComparisonArtifacts(touchpoint_rows, summary_rows, recommended_rows)
