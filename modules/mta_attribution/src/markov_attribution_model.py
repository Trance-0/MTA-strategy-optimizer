"""Markov removal-effect attribution model.

Scores a touchpoint by how much the modelled conversion probability falls when
that touchpoint is removed from the transition network.

Inputs: validated aggregated path rows from ``attribution_contract``.
Outputs: ``AttributionResult`` per five-segment touchpoint, consumed by
``attribution_contract.result_rows``.

The file holds three stages: adapters that expand one aggregated row into
weighted state paths, ``WeightedMarkovAttribution`` which estimates transitions
and solves absorption, and ``run_markov_attribution`` which runs one independent
model per outcome and rescales shares back onto observed totals.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Mapping, Sequence

from attribution_contract import (
    CONVERSION,
    NULL,
    START,
    AttributionResult,
    parse_channels,
    parse_path,
    safe_float,
    safe_int,
    unique_touchpoints,
    validate_amc_aggregated_row,
)
from touchpoint_key import canonicalize_amc_touchpoint_key


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
