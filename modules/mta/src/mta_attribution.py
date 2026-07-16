from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


START = "Start"
CONVERSION = "Conversion"
NULL = "Null"


@dataclass(frozen=True)
class AttributionResult:
    channel: str
    attributed_conversions: float
    attributed_revenue: float
    contribution_share: float
    spend: float = 0.0
    roas: float | None = None
    roi: float | None = None
    cpa: float | None = None


def read_csv(path: str | Path) -> List[dict]:
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: Sequence[Mapping], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_path(path: str) -> List[str]:
    return [part.strip() for part in path.split(">") if part.strip()]


def parse_channels(channels: str) -> Tuple[str, ...]:
    return tuple(channel.strip() for channel in channels.split(",") if channel.strip())


def _safe_float(value: object) -> float:
    if value in ("", None):
        return 0.0
    return float(value)


def _safe_int(value: object) -> int:
    if value in ("", None):
        return 0
    return int(float(value))


def load_spend_by_channel(spend_path: str | Path | None) -> Dict[str, float]:
    if spend_path is None:
        return {}
    spend_by_channel: Dict[str, float] = defaultdict(float)
    for row in read_csv(spend_path):
        spend_by_channel[row["channel"]] += _safe_float(row["spend"])
    return dict(spend_by_channel)


def add_roi_metrics(
    results: Sequence[AttributionResult],
    spend_by_channel: Mapping[str, float],
) -> List[AttributionResult]:
    enriched: List[AttributionResult] = []
    for result in results:
        spend = spend_by_channel.get(result.channel, 0.0)
        roas = result.attributed_revenue / spend if spend > 0 else None
        roi = (result.attributed_revenue - spend) / spend if spend > 0 else None
        cpa = spend / result.attributed_conversions if result.attributed_conversions > 0 else None
        enriched.append(
            AttributionResult(
                channel=result.channel,
                attributed_conversions=result.attributed_conversions,
                attributed_revenue=result.attributed_revenue,
                contribution_share=result.contribution_share,
                spend=spend,
                roas=roas,
                roi=roi,
                cpa=cpa,
            )
        )
    return enriched


def attribution_rows(results: Sequence[AttributionResult]) -> List[dict]:
    rows = []
    for result in results:
        rows.append(
            {
                "channel": result.channel,
                "contribution_share": round(result.contribution_share, 6),
                "attributed_conversions": round(result.attributed_conversions, 4),
                "attributed_revenue": round(result.attributed_revenue, 2),
                "spend": round(result.spend, 2),
                "roas": "" if result.roas is None else round(result.roas, 6),
                "roi": "" if result.roi is None else round(result.roi, 6),
                "cpa": "" if result.cpa is None else round(result.cpa, 6),
            }
        )
    return rows


class MarkovChainAttribution:
    """First-order Markov attribution using channel removal effect."""

    def __init__(self, path_rows: Sequence[Mapping[str, object]]):
        self.path_rows = list(path_rows)
        self.paths = [parse_path(str(row["path"])) for row in self.path_rows]
        self.total_conversions = sum(_safe_int(row.get("conversion")) for row in self.path_rows)
        self.total_revenue = sum(_safe_float(row.get("revenue")) for row in self.path_rows)
        self.channels = sorted(
            {
                state
                for path in self.paths
                for state in path
                if state not in {START, CONVERSION, NULL}
            }
        )

    def transition_matrix(self, removed_channel: str | None = None) -> Dict[str, Dict[str, float]]:
        counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for path in self.paths:
            if len(path) < 2:
                continue
            for current, nxt in zip(path, path[1:]):
                if current == removed_channel:
                    break
                if nxt == removed_channel:
                    counts[current][NULL] += 1
                    break
                counts[current][nxt] += 1

        matrix: Dict[str, Dict[str, float]] = {}
        for current, next_counts in counts.items():
            total = sum(next_counts.values())
            matrix[current] = {nxt: count / total for nxt, count in next_counts.items()}
        return matrix

    def conversion_probability(self, removed_channel: str | None = None) -> float:
        matrix = self.transition_matrix(removed_channel)
        states = set(matrix.keys())
        for transitions in matrix.values():
            states.update(transitions.keys())

        values = {state: 0.0 for state in states}
        values[CONVERSION] = 1.0
        values[NULL] = 0.0

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
                break

        return values.get(START, 0.0)

    def removal_effects(self) -> Dict[str, float]:
        base_prob = self.conversion_probability()
        effects = {}
        for channel in self.channels:
            removed_prob = self.conversion_probability(removed_channel=channel)
            effects[channel] = max(base_prob - removed_prob, 0.0)
        return effects

    def attribute(self) -> List[AttributionResult]:
        effects = self.removal_effects()
        total_effect = sum(effects.values())
        if total_effect <= 0:
            equal_share = 1 / len(self.channels) if self.channels else 0.0
            shares = {channel: equal_share for channel in self.channels}
        else:
            shares = {channel: effect / total_effect for channel, effect in effects.items()}

        return [
            AttributionResult(
                channel=channel,
                attributed_conversions=shares[channel] * self.total_conversions,
                attributed_revenue=shares[channel] * self.total_revenue,
                contribution_share=shares[channel],
            )
            for channel in self.channels
        ]


class ShapleyValueAttribution:
    """Path-level Shapley attribution over observed channel coalitions.

    For each user path, channels are treated symmetrically. The user's
    conversion/revenue is distributed across the unique channels in that path.
    This is the Shapley value for a path-level game where each observed channel
    is required equally for the observed outcome.
    """

    def __init__(self, channel_set_rows: Sequence[Mapping[str, object]]):
        self.rows = list(channel_set_rows)
        self.channels = sorted(
            {
                channel
                for row in self.rows
                for channel in parse_channels(str(row["channels"]))
            }
        )
        self.total_conversions = sum(_safe_int(row.get("conversion")) for row in self.rows)
        self.total_revenue = sum(_safe_float(row.get("revenue")) for row in self.rows)

    def _shapley_scores(self, outcome_field: str) -> Dict[str, float]:
        scores = {channel: 0.0 for channel in self.channels}
        for row in self.rows:
            channels = parse_channels(str(row["channels"]))
            if not channels:
                continue
            outcome = _safe_float(row.get(outcome_field))
            per_channel_credit = outcome / len(channels)
            for channel in channels:
                scores[channel] += per_channel_credit
        return scores

    def attribute(self) -> List[AttributionResult]:
        conversion_scores = self._shapley_scores("conversion")
        revenue_scores = self._shapley_scores("revenue")
        total_revenue_score = sum(revenue_scores.values())
        total_conversion_score = sum(conversion_scores.values())

        results = []
        for channel in self.channels:
            revenue_share = (
                revenue_scores[channel] / total_revenue_score
                if total_revenue_score > 0
                else 1 / len(self.channels)
            )
            conversion_share = (
                conversion_scores[channel] / total_conversion_score
                if total_conversion_score > 0
                else revenue_share
            )
            results.append(
                AttributionResult(
                    channel=channel,
                    attributed_conversions=conversion_share * self.total_conversions,
                    attributed_revenue=revenue_share * self.total_revenue,
                    contribution_share=revenue_share,
                )
            )
        return results


def run_markov(
    paths_path: str | Path,
    spend_path: str | Path | None = None,
) -> List[AttributionResult]:
    model = MarkovChainAttribution(read_csv(paths_path))
    return add_roi_metrics(model.attribute(), load_spend_by_channel(spend_path))


def run_shapley(
    channel_sets_path: str | Path,
    spend_path: str | Path | None = None,
) -> List[AttributionResult]:
    model = ShapleyValueAttribution(read_csv(channel_sets_path))
    return add_roi_metrics(model.attribute(), load_spend_by_channel(spend_path))
