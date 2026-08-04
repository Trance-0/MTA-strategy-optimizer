"""Path-level Shapley attribution model.

Treats each path's unique touchpoint set as a coalition in a unanimity game, so
a row's outcome becomes available only when every member is present. The exact
Shapley value of that game divides the row outcome equally among its members,
and summing row games preserves every outcome total exactly.

Inputs: validated aggregated path rows from ``attribution_contract``.
Outputs: ``AttributionResult`` per five-segment touchpoint, consumed by
``attribution_contract.result_rows``.

Because the closed form avoids enumerating coalitions, cost is linear in rows
rather than exponential in touchpoints.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

from attribution_contract import (
    AttributionResult,
    parse_channels,
    safe_float,
    safe_int,
    unique_touchpoints,
    validate_amc_aggregated_row,
)


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

def run_shapley_attribution(
    amc_rows: Sequence[Mapping[str, object]],
) -> List[AttributionResult]:
    model = AggregatedShapleyAttribution(amc_rows_to_shapley_rows(amc_rows))
    return model.attribute()
