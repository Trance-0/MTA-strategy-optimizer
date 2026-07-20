from __future__ import annotations

import csv
import math
import os
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from touchpoint_key import (
    canonicalize_amc_touchpoint_key,
    touchpoint_key_from_ads_row,
)


START = "Start"
CONVERSION = "Conversion"
NULL = "Null"

PATH_FIELD_DESCRIPTIONS = {
    "report_start_date": "报告开始日期",
    "report_end_date": "报告结束日期",
    "marketplace": "广告市场",
    "advertiser_id": "AMC 广告主 ID",
    "path": "匿名聚合五段触点路径",
    "users": "路径用户数",
    "converted_users": "转化用户数",
    "purchase_count": "购买次数",
    "revenue": "销售额",
}

ADS_FIELD_DESCRIPTIONS = {
    "reportDate": "报告日期",
    "marketplace": "广告市场",
    "accountId": "广告账户 ID 对应 AMC advertiser id",
    "adProduct": "广告产品",
    "adType": "Sponsored Ads 广告形式",
    "creativeType": "创意类型",
    "inventoryType": "DSP 库存类型",
    "placement": "广告位置",
    "interaction_type": "互动类型（IMPRESSION 或 CLICK）",
    "cost_type": "计费类型（CPC 或 CPM）",
    "normalizedTouchpoint": "标准化五段触点键",
    "currencyCode": "币种",
    "impressions": "曝光量",
    "clicks": "点击量",
    "cost": "广告花费",
    "purchases": "平台报告购买量",
    "sales": "平台报告销售额",
}

KNOWN_FIELD_DESCRIPTION_ROWS = (
    PATH_FIELD_DESCRIPTIONS,
    ADS_FIELD_DESCRIPTIONS,
)


@dataclass(frozen=True)
class AttributionResult:
    touchpoint: str
    converted_user_share: float
    purchase_count_share: float
    revenue_share: float
    attributed_converted_users: float
    attributed_purchase_count: float
    attributed_revenue: float


@dataclass(frozen=True)
class TouchpointSpend:
    touchpoint: str
    impressions: int
    clicks: int
    cost: float
    reported_purchases: int
    reported_sales: float


def _is_field_description_row(row: Mapping[object, object]) -> bool:
    """Match only a complete, known human-readable field guide row."""
    return any(dict(row) == description for description in KNOWN_FIELD_DESCRIPTION_ROWS)


def read_csv(path: str | Path) -> List[dict]:
    with Path(path).open(newline="") as f:
        rows = [
            {
                (key.strip() if key is not None else key): (
                    value.strip() if isinstance(value, str) else value
                )
                for key, value in row.items()
            }
            for row in csv.DictReader(f)
        ]
    return [row for row in rows if not _is_field_description_row(row)]


def write_csv(path: str | Path, rows: Sequence[Mapping], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_csv_atomic(
    path: str | Path, rows: Sequence[Mapping], fieldnames: Sequence[str]
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        write_csv(temporary_path, rows, fieldnames)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_csv_set_atomic(
    artifacts: Sequence[tuple[str | Path, Sequence[Mapping], Sequence[str]]]
) -> List[Path]:
    """Stage and publish a CSV set, restoring the complete prior set on failure."""
    if not artifacts:
        return []
    destinations = [Path(path) for path, _, _ in artifacts]
    resolved = [path.resolve() for path in destinations]
    if len(resolved) != len(set(resolved)):
        raise ValueError("CSV artifact set contains duplicate destinations")
    parents = {path.parent.resolve() for path in destinations}
    if len(parents) != 1:
        raise ValueError("CSV artifact set must use one output directory")
    output_dir = destinations[0].parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".csv_set_", dir=output_dir) as tmp:
        temporary_root = Path(tmp)
        staged: list[Path] = []
        for index, (destination, rows, fieldnames) in enumerate(artifacts):
            stage = temporary_root / f"stage_{index:02d}_{Path(destination).name}"
            write_csv(stage, rows, fieldnames)
            staged.append(stage)

        backups: dict[Path, Path | None] = {}
        for index, destination in enumerate(destinations):
            if destination.exists():
                backup = temporary_root / f"backup_{index:02d}_{destination.name}"
                shutil.copy2(destination, backup)
                backups[destination] = backup
            else:
                backups[destination] = None

        published: list[Path] = []
        try:
            for stage, destination in zip(staged, destinations):
                os.replace(stage, destination)
                published.append(destination)
        except Exception:
            rollback_errors = []
            for destination in reversed(published):
                backup = backups[destination]
                try:
                    if backup is None:
                        destination.unlink(missing_ok=True)
                    else:
                        os.replace(backup, destination)
                except Exception as rollback_error:  # pragma: no cover
                    rollback_errors.append(f"{destination}: {rollback_error}")
            if rollback_errors:
                raise RuntimeError(
                    "CSV publication and rollback both failed: "
                    + "; ".join(rollback_errors)
                )
            raise
    return destinations


def parse_path(path: str) -> List[str]:
    return [part.strip() for part in path.split(">") if part.strip()]


def parse_channels(channels: str) -> Tuple[str, ...]:
    return tuple(channel.strip() for channel in channels.split(",") if channel.strip())


def unique_touchpoints(path: Sequence[str]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(state for state in path if state not in {START, CONVERSION, NULL}))


def safe_float(value: object) -> float:
    if value in ("", None):
        return 0.0
    return float(value)


def safe_int(value: object) -> int:
    if value in ("", None):
        return 0
    return int(float(value))


def _strict_number(value: object, field: str, *, integer: bool = False) -> float | int:
    if value in (None, "") or not str(value).strip():
        raise ValueError(f"{field} is required")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number: {value!r}")
    if integer and not number.is_integer():
        raise ValueError(f"{field} must be an integer: {value!r}")
    return int(number) if integer else number


def _optional_non_negative_number(
    value: object, field: str, *, integer: bool = False
) -> float | int:
    if value in (None, "") or not str(value).strip():
        return 0 if integer else 0.0
    return _strict_number(value, field, integer=integer)


def validate_amc_aggregated_row(
    row: Mapping[str, object], row_number: int
) -> List[str]:
    missing = [
        field
        for field in (
            "path",
            "users",
            "converted_users",
            "purchase_count",
            "revenue",
        )
        if row.get(field) in (None, "") or not str(row.get(field, "")).strip()
    ]
    if missing:
        raise ValueError(
            f"AMC row {row_number}: required field(s) missing: {', '.join(missing)}"
        )

    raw_path = str(row["path"]).strip()
    raw_parts = raw_path.split(">")
    if any(not part.strip() for part in raw_parts):
        raise ValueError(f"AMC row {row_number}: path contains an empty touchpoint")
    raw_touchpoints = [part.strip() for part in raw_parts]
    if START in raw_touchpoints or CONVERSION in raw_touchpoints:
        raise ValueError(f"AMC row {row_number}: path cannot contain reserved terminal states")
    if NULL in raw_touchpoints[:-1] or (raw_touchpoints == [NULL]):
        raise ValueError(f"AMC row {row_number}: Null is allowed only after a touchpoint")
    explicit_null = raw_touchpoints[-1] == NULL
    key_parts = raw_touchpoints[:-1] if explicit_null else raw_touchpoints
    try:
        parts = [canonicalize_amc_touchpoint_key(part) for part in key_parts]
    except ValueError as exc:
        raise ValueError(f"AMC row {row_number}: {exc}") from exc
    if explicit_null:
        parts.append(NULL)

    users = int(_strict_number(row.get("users"), "users", integer=True))
    converted_users = int(
        _strict_number(row.get("converted_users"), "converted_users", integer=True)
    )
    purchase_count = int(
        _strict_number(row.get("purchase_count"), "purchase_count", integer=True)
    )
    revenue = float(_strict_number(row.get("revenue"), "revenue"))
    if converted_users > users:
        raise ValueError(f"AMC row {row_number}: converted_users must be <= users")
    if purchase_count < converted_users:
        raise ValueError(
            f"AMC row {row_number}: purchase_count must be >= converted_users"
        )
    if converted_users == 0 and (purchase_count > 0 or revenue > 0):
        raise ValueError(
            f"AMC row {row_number}: positive outcomes require converted_users > 0"
        )
    if parts[-1] == NULL and (
        converted_users > 0 or purchase_count > 0 or revenue > 0
    ):
        raise ValueError(
            f"AMC row {row_number}: a path ending in Null cannot contain outcomes"
        )
    return parts


def safe_divide(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def amc_path_to_markov_path(path: str, converted_users: object) -> str:
    raw_parts = str(path).split(">")
    if any(not part.strip() for part in raw_parts):
        raise ValueError("path contains an empty touchpoint")
    raw_touchpoints = [part.strip() for part in raw_parts]
    if START in raw_touchpoints or CONVERSION in raw_touchpoints:
        raise ValueError("path cannot contain reserved terminal states")
    if NULL in raw_touchpoints[:-1] or raw_touchpoints == [NULL]:
        raise ValueError("Null is allowed only after a touchpoint")
    explicit_null = raw_touchpoints[-1] == NULL
    key_parts = raw_touchpoints[:-1] if explicit_null else raw_touchpoints
    touchpoints = [canonicalize_amc_touchpoint_key(part) for part in key_parts]
    if explicit_null:
        touchpoints.append(NULL)
    if touchpoints and touchpoints[-1] == NULL:
        states = [START, *touchpoints]
    elif safe_float(converted_users) > 0:
        states = [START, *touchpoints, CONVERSION]
    else:
        states = [START, *touchpoints, NULL]
    return " > ".join(states)


def amc_rows_to_markov_rows(amc_rows: Sequence[Mapping[str, object]]) -> List[dict]:
    rows = []
    for idx, row in enumerate(amc_rows, start=1):
        touchpoints = validate_amc_aggregated_row(row, idx)
        users = safe_float(row.get("users"))
        converted_users = safe_int(row.get("converted_users"))
        purchase_count = safe_int(row.get("purchase_count"))
        revenue = safe_float(row.get("revenue"))
        if users < 0 or converted_users < 0 or converted_users > users:
            raise ValueError("Markov rows require 0 <= converted_users <= users")

        explicit_null = bool(touchpoints and touchpoints[-1] == NULL)
        if explicit_null:
            touchpoints = touchpoints[:-1]
            if converted_users or purchase_count or revenue:
                raise ValueError("A path ending in Null cannot contain outcomes")

        base_path = [START, *touchpoints]
        if converted_users > 0:
            rows.append(
                {
                    "path_id": f"amc_path_{idx:05d}_conversion",
                    "path": " > ".join([*base_path, CONVERSION]),
                    "converted_users": converted_users,
                    "purchase_count": purchase_count,
                    "revenue": revenue,
                    "users": users,
                    "weight": float(converted_users),
                }
            )
        null_weight = users - converted_users
        if null_weight > 0:
            rows.append(
                {
                    "path_id": f"amc_path_{idx:05d}_null",
                    "path": " > ".join([*base_path, NULL]),
                    "converted_users": 0,
                    "purchase_count": 0,
                    "revenue": 0.0,
                    "users": users,
                    "weight": null_weight,
                }
            )
    return rows


def amc_rows_to_outcome_markov_rows(
    amc_rows: Sequence[Mapping[str, object]], outcome_field: str
) -> List[dict]:
    if outcome_field not in {"purchase_count", "revenue"}:
        raise ValueError(f"unsupported Markov outcome: {outcome_field}")
    rows = []
    for idx, row in enumerate(amc_rows, start=1):
        touchpoints = validate_amc_aggregated_row(row, idx)
        if touchpoints[-1] == NULL:
            continue
        outcome = safe_float(row.get(outcome_field))
        if outcome <= 0:
            continue
        rows.append(
            {
                "path_id": f"amc_path_{idx:05d}_{outcome_field}",
                "path": " > ".join([START, *touchpoints, CONVERSION]),
                "weight": outcome,
            }
        )
    return rows


def amc_rows_to_shapley_rows(amc_rows: Sequence[Mapping[str, object]]) -> List[dict]:
    rows = []
    for idx, row in enumerate(amc_rows, start=1):
        touchpoints = unique_touchpoints(validate_amc_aggregated_row(row, idx))
        rows.append(
            {
                "path_id": f"amc_path_{idx:05d}",
                "channels": ",".join(touchpoints),
                "converted_users": safe_int(row.get("converted_users")),
                "purchase_count": safe_int(row.get("purchase_count")),
                "revenue": safe_float(row.get("revenue")),
                "users": safe_float(row.get("users")),
            }
        )
    return rows


class WeightedMarkovAttribution:
    """First-order Markov attribution for aggregated AMC path rows."""

    def __init__(self, path_rows: Sequence[Mapping[str, object]]):
        self.path_rows = list(path_rows)
        self.paths = [parse_path(str(row["path"])) for row in self.path_rows]
        self.touchpoints = sorted(
            {
                state
                for path in self.paths
                for state in path
                if state not in {START, CONVERSION, NULL}
            }
        )

    def transition_matrix(self, removed_touchpoint: str | None = None) -> Dict[str, Dict[str, float]]:
        counts: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for row, path in zip(self.path_rows, self.paths):
            if len(path) < 2:
                continue
            weight = safe_float(row.get("weight", row.get("users")))
            if weight <= 0:
                continue
            for current, nxt in zip(path, path[1:]):
                if current == removed_touchpoint:
                    break
                if nxt == removed_touchpoint:
                    counts[current][NULL] += weight
                    break
                counts[current][nxt] += weight

        matrix: Dict[str, Dict[str, float]] = {}
        for current, next_counts in counts.items():
            total = sum(next_counts.values())
            matrix[current] = {nxt: count / total for nxt, count in next_counts.items()}
        return matrix

    def conversion_probability(self, removed_touchpoint: str | None = None) -> float:
        matrix = self.transition_matrix(removed_touchpoint)
        states = set(matrix.keys())
        for transitions in matrix.values():
            states.update(transitions.keys())

        values = {state: 0.0 for state in states}
        values[CONVERSION] = 1.0
        values[NULL] = 0.0

        converged = False
        for _ in range(1000):
            max_delta = 0.0
            next_values = dict(values)
            for state in states:
                if state in {CONVERSION, NULL}:
                    continue
                prob = sum(
                    transition_prob * values.get(nxt, 0.0)
                    for nxt, transition_prob in matrix.get(state, {}).items()
                )
                max_delta = max(max_delta, abs(prob - values.get(state, 0.0)))
                next_values[state] = prob
            values = next_values
            if max_delta < 1e-12:
                converged = True
                break

        if not converged and states - {CONVERSION, NULL}:
            raise RuntimeError("Markov conversion probability did not converge")

        return values.get(START, 0.0)

    def removal_effects(self) -> Dict[str, float]:
        base_prob = self.conversion_probability()
        effects = {}
        for touchpoint in self.touchpoints:
            removed_prob = self.conversion_probability(removed_touchpoint=touchpoint)
            effects[touchpoint] = max(base_prob - removed_prob, 0.0)
        return effects

    def contribution_shares(self, *, total_outcome: float) -> Dict[str, float]:
        if total_outcome <= 0:
            return {touchpoint: 0.0 for touchpoint in self.touchpoints}
        effects = self.removal_effects()
        total_effect = sum(effects.values())
        if total_effect <= 0:
            equal_share = 1 / len(self.touchpoints) if self.touchpoints else 0.0
            return {touchpoint: equal_share for touchpoint in self.touchpoints}
        return {
            touchpoint: effect / total_effect for touchpoint, effect in effects.items()
        }


class AggregatedShapleyAttribution:
    """Exact Shapley values for a sum of path-level unanimity games.

    A row's unique touchpoints form a coalition whose outcomes become
    available only when every coalition member is present. The exact Shapley value
    of that unanimity game divides the row outcome equally among its unique members.
    Summing row games preserves all outcome totals.
    """

    def __init__(self, channel_set_rows: Sequence[Mapping[str, object]]):
        self.rows = list(channel_set_rows)
        self.touchpoints = sorted(
            {
                channel
                for row in self.rows
                for channel in parse_channels(str(row["channels"]))
            }
        )
        self.total_converted_users = sum(
            safe_int(row.get("converted_users")) for row in self.rows
        )
        self.total_purchase_count = sum(
            safe_int(row.get("purchase_count")) for row in self.rows
        )
        self.total_revenue = sum(safe_float(row.get("revenue")) for row in self.rows)

    def coalition_value(self, coalition: Sequence[str], outcome_field: str) -> float:
        members = set(coalition)
        return sum(
            safe_float(row.get(outcome_field))
            for row in self.rows
            if set(parse_channels(str(row["channels"]))).issubset(members)
        )

    def _scores(self, outcome_field: str) -> Dict[str, float]:
        """Closed form of exact Shapley values for the coalition function above."""
        scores = {touchpoint: 0.0 for touchpoint in self.touchpoints}
        for row in self.rows:
            touchpoints = tuple(dict.fromkeys(parse_channels(str(row["channels"]))))
            if not touchpoints:
                continue
            outcome = safe_float(row.get(outcome_field))
            per_touchpoint_credit = outcome / len(touchpoints)
            for touchpoint in touchpoints:
                scores[touchpoint] += per_touchpoint_credit
        return scores

    def attribute(self) -> List[AttributionResult]:
        converted_user_scores = self._scores("converted_users")
        purchase_count_scores = self._scores("purchase_count")
        revenue_scores = self._scores("revenue")
        total_converted_user_score = sum(converted_user_scores.values())
        total_purchase_count_score = sum(purchase_count_scores.values())
        total_revenue_score = sum(revenue_scores.values())

        results = []
        for touchpoint in self.touchpoints:
            revenue_share = (
                revenue_scores[touchpoint] / total_revenue_score
                if total_revenue_score > 0
                else 0.0
            )
            converted_user_share = (
                converted_user_scores[touchpoint] / total_converted_user_score
                if total_converted_user_score > 0
                else 0.0
            )
            purchase_count_share = (
                purchase_count_scores[touchpoint] / total_purchase_count_score
                if total_purchase_count_score > 0
                else 0.0
            )
            results.append(
                AttributionResult(
                    touchpoint=touchpoint,
                    converted_user_share=converted_user_share,
                    purchase_count_share=purchase_count_share,
                    revenue_share=revenue_share,
                    attributed_converted_users=converted_user_scores[touchpoint],
                    attributed_purchase_count=purchase_count_scores[touchpoint],
                    attributed_revenue=revenue_scores[touchpoint],
                )
            )
        return results


def run_markov_attribution(
    amc_rows: Sequence[Mapping[str, object]],
) -> List[AttributionResult]:
    validated_rows = [dict(row) for row in amc_rows]
    conversion_model = WeightedMarkovAttribution(
        amc_rows_to_markov_rows(validated_rows)
    )
    purchase_count_model = WeightedMarkovAttribution(
        amc_rows_to_outcome_markov_rows(validated_rows, "purchase_count")
    )
    revenue_model = WeightedMarkovAttribution(
        amc_rows_to_outcome_markov_rows(validated_rows, "revenue")
    )

    touchpoints = sorted(
        set(conversion_model.touchpoints)
        | set(purchase_count_model.touchpoints)
        | set(revenue_model.touchpoints)
    )
    total_converted_users = sum(
        safe_int(row.get("converted_users")) for row in validated_rows
    )
    total_purchase_count = sum(
        safe_int(row.get("purchase_count")) for row in validated_rows
    )
    total_revenue = sum(safe_float(row.get("revenue")) for row in validated_rows)

    converted_user_shares = conversion_model.contribution_shares(
        total_outcome=total_converted_users
    )
    purchase_count_shares = purchase_count_model.contribution_shares(
        total_outcome=total_purchase_count
    )
    revenue_shares = revenue_model.contribution_shares(total_outcome=total_revenue)

    return [
        AttributionResult(
            touchpoint=touchpoint,
            converted_user_share=converted_user_shares.get(touchpoint, 0.0),
            purchase_count_share=purchase_count_shares.get(touchpoint, 0.0),
            revenue_share=revenue_shares.get(touchpoint, 0.0),
            attributed_converted_users=(
                converted_user_shares.get(touchpoint, 0.0) * total_converted_users
            ),
            attributed_purchase_count=(
                purchase_count_shares.get(touchpoint, 0.0) * total_purchase_count
            ),
            attributed_revenue=revenue_shares.get(touchpoint, 0.0) * total_revenue,
        )
        for touchpoint in touchpoints
    ]


def run_shapley_attribution(
    amc_rows: Sequence[Mapping[str, object]],
) -> List[AttributionResult]:
    model = AggregatedShapleyAttribution(amc_rows_to_shapley_rows(amc_rows))
    return model.attribute()


def aggregate_spend_by_touchpoint(
    amazon_ads_rows: Sequence[Mapping[str, object]],
) -> Dict[str, TouchpointSpend]:
    grouped: Dict[str, dict] = defaultdict(
        lambda: {
            "impressions": 0,
            "clicks": 0,
            "cost": 0.0,
            "reported_purchases": 0,
            "reported_sales": 0.0,
        }
    )
    for row_number, row in enumerate(amazon_ads_rows, start=2):
        touchpoint = touchpoint_key_from_ads_row(row, row_number=row_number)
        interaction_type = touchpoint.rsplit(":", 1)[1]
        cost_type = str(row.get("cost_type", "")).strip().upper()
        if cost_type not in {"CPC", "CPM"}:
            raise ValueError(
                f"Amazon Ads row {row_number}: cost_type must be CPC or CPM"
            )
        metrics = grouped[touchpoint]
        try:
            cost = float(_optional_non_negative_number(row.get("cost"), "cost"))
            if (
                (cost_type == "CPC" and interaction_type != "CLICK")
                or (cost_type == "CPM" and interaction_type != "IMPRESSION")
            ):
                raise ValueError(
                    f"cost_type={cost_type} conflicts with interaction_type={interaction_type}"
                )
            purchases = int(_optional_non_negative_number(
                row.get("purchases"), "purchases", integer=True
            ))
            sales = float(_optional_non_negative_number(row.get("sales"), "sales"))
            if interaction_type != "CLICK" and (purchases or sales):
                raise ValueError(
                    "platform purchases and sales are allowed only for CLICK"
                )
            impressions = int(_optional_non_negative_number(
                row.get("impressions"), "impressions", integer=True
            ))
            clicks = int(_optional_non_negative_number(
                row.get("clicks"), "clicks", integer=True
            ))
            if interaction_type == "CLICK" and impressions:
                raise ValueError("impressions are allowed only for IMPRESSION")
            if interaction_type == "IMPRESSION" and clicks:
                raise ValueError("clicks are allowed only for CLICK")
            metrics["impressions"] += impressions
            metrics["clicks"] += clicks
            metrics["cost"] += cost
            metrics["reported_purchases"] += purchases
            metrics["reported_sales"] += sales
        except ValueError as exc:
            raise ValueError(f"Amazon Ads row {row_number}: {exc}") from exc

    return {
        touchpoint: TouchpointSpend(touchpoint=touchpoint, **metrics)
        for touchpoint, metrics in grouped.items()
    }


def _rounded_with_residual(
    results: Sequence[AttributionResult], field: str, digits: int
) -> List[float]:
    raw_values = [float(getattr(result, field)) for result in results]
    if not raw_values:
        return []
    if any(value < 0 or not math.isfinite(value) for value in raw_values):
        raise ValueError(f"{field} values must be finite and non-negative")

    # Allocate integer units using the largest-remainder method. This preserves
    # the rounded total without ever making a small non-negative value negative.
    scale = 10**digits
    scaled_values = [value * scale for value in raw_values]
    units = [math.floor(value) for value in scaled_values]
    target_units = int(round(round(sum(raw_values), digits) * scale))
    remaining = target_units - sum(units)
    order = sorted(
        range(len(raw_values)),
        key=lambda index: (
            scaled_values[index] - math.floor(scaled_values[index]),
            raw_values[index],
            -index,
        ),
        reverse=True,
    )
    if remaining < 0 or remaining > len(order):
        raise ValueError(f"{field} cannot be rounded without losing conservation")
    for offset in range(remaining):
        units[order[offset % len(order)]] += 1
    return [unit / scale for unit in units]


def result_rows(
    model_name: str,
    attribution_results: Sequence[AttributionResult],
    spend_by_touchpoint: Mapping[str, TouchpointSpend],
) -> List[dict]:
    results = list(attribution_results)
    for result in results:
        try:
            canonical = canonicalize_amc_touchpoint_key(result.touchpoint)
        except ValueError as exc:
            raise ValueError(
                "result rows require canonical five-part touchpoints"
            ) from exc
        if canonical != result.touchpoint:
            raise ValueError(
                "result rows require canonical five-part touchpoints"
            )
    rounded_fields = {
        "converted_user_share": _rounded_with_residual(
            results, "converted_user_share", 6
        ),
        "purchase_count_share": _rounded_with_residual(
            results, "purchase_count_share", 6
        ),
        "revenue_share": _rounded_with_residual(results, "revenue_share", 6),
        "attributed_converted_users": _rounded_with_residual(
            results, "attributed_converted_users", 4
        ),
        "attributed_purchase_count": _rounded_with_residual(
            results, "attributed_purchase_count", 4
        ),
        "attributed_revenue": _rounded_with_residual(
            results, "attributed_revenue", 2
        ),
    }

    rows = []
    for index, result in enumerate(results):
        if result.touchpoint not in spend_by_touchpoint:
            raise ValueError(
                f"missing Amazon Ads spend for touchpoint: {result.touchpoint}"
            )
        spend = spend_by_touchpoint[result.touchpoint]
        attributed_converted_users = rounded_fields["attributed_converted_users"][index]
        attributed_purchase_count = rounded_fields["attributed_purchase_count"][index]
        attributed_revenue = rounded_fields["attributed_revenue"][index]
        roas = safe_divide(attributed_revenue, spend.cost)
        roi = safe_divide(attributed_revenue - spend.cost, spend.cost)
        cpa = (
            None
            if spend.cost == 0
            else safe_divide(spend.cost, attributed_purchase_count)
        )
        cost_per_converted_user = (
            None
            if spend.cost == 0
            else safe_divide(spend.cost, attributed_converted_users)
        )
        rows.append(
            {
                "attribution_model": model_name,
                "touchpoint": result.touchpoint,
                "interaction_type": result.touchpoint.rsplit(":", 1)[1],
                "converted_user_share": rounded_fields["converted_user_share"][index],
                "purchase_count_share": rounded_fields["purchase_count_share"][index],
                "revenue_share": rounded_fields["revenue_share"][index],
                "attributed_converted_users": attributed_converted_users,
                "attributed_purchase_count": attributed_purchase_count,
                "attributed_revenue": attributed_revenue,
                "impressions": spend.impressions,
                "clicks": spend.clicks,
                "cost": round(spend.cost, 2),
                "reported_purchases": spend.reported_purchases,
                "reported_sales": round(spend.reported_sales, 2),
                "roas": "" if roas is None else round(roas, 6),
                "roi": "" if roi is None else round(roi, 6),
                "cpa": "" if cpa is None else round(cpa, 6),
                "cost_per_converted_user": (
                    ""
                    if cost_per_converted_user is None
                    else round(cost_per_converted_user, 6)
                ),
            }
        )
    return rows
