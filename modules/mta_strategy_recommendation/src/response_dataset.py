"""The one Campaign-period response dataset every response consumer reads.

Aggregates ``CampaignEpisode`` records into one row per Campaign, period, and
assigned budget intervention. The trainer, the optimizer, and the dashboard all
read this builder rather than each re-deriving Campaign totals from raw
observations, so a single definition of "what a Campaign spent and earned in a
period" exists.

What a row may carry is deliberately constrained:

- decision-time context (Provider, ad product, marketplace, currency, and the
  Campaign configuration known before the budget was committed);
- the assigned intervention (configured budget and its metadata);
- what was then observed (actual spend, impressions, clicks, total revenue).

What a row must never carry is simulator ground truth
(``EvaluationGroundTruth``, true incremental effect, oracle revenue) or
attribution output. Attribution answers how observed credit is divided among
touchpoints; this dataset answers how revenue responds when budget changes.
Those are different questions, so ``AttributionEvidence`` is not a feature
here and the builder rejects an ``EvaluationEpisode`` outright.

Data flow: MTA-SIM research snapshot -> ``mta_sim_research_adapter`` ->
``CampaignEpisode`` -> this builder -> ``response_model`` -> ``budget_optimizer``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from modules.mta_common.src.enums import AssignmentType, Provider
from modules.mta_common.src.episode import CampaignEpisode
from modules.mta_common.src.evaluation_only import EvaluationEpisode


# Field names that would constitute an attribution or ground-truth leak into
# the response model. Kept beside the builder that enforces them.
FORBIDDEN_RESPONSE_FEATURES = frozenset(
    {
        "attribution_evidence",
        "attributed_revenue",
        "credit_share",
        "markov_share",
        "shapley_share",
        "similarity_reference",
        "similarity_score",
        "true_incremental_units",
        "true_incremental_revenue",
        "true_causal_effect",
        "simulator_ground_truth_id",
        "incremental_units",
        "incremental_revenue",
        "expected_organic_units",
        "expected_organic_revenue",
    }
)


class ResponseDatasetError(ValueError):
    """Raised when episodes cannot form a valid response dataset."""


@dataclass(frozen=True)
class CampaignResponseObservation:
    """One Campaign, period, and intervention, as the response model sees it.

    Attributes:
        campaign_id: The observed Campaign.
        marketplace: Marketplace the period was observed in.
        report_start_date: Inclusive ISO start date of the period.
        report_end_date: Inclusive ISO end date of the period.
        currency: Currency every monetary field is denominated in.
        provider: Decision-time advertising platform.
        ad_product: Decision-time provider ad product.
        campaign_status: Decision-time Campaign status.
        configured_budget: The budget assigned before the period ran.
        actual_spend: What the period actually spent.
        impressions: Observed impressions summed across touchpoints.
        clicks: Observed clicks summed across touchpoints.
        total_revenue: Observed revenue summed across touchpoints and
            Products, which is the response model's target.
        intervention_id: Identifier of the assigned intervention, when one
            was recorded.
        baseline_budget: The untreated budget the intervention moved from.
        budget_delta: ``configured_budget - baseline_budget``.
        assignment_type: How the intervention was assigned.
        randomized: Whether assignment was randomized.
    """

    campaign_id: str
    marketplace: str
    report_start_date: str
    report_end_date: str
    currency: str
    provider: Provider
    ad_product: str
    campaign_status: str
    configured_budget: float
    actual_spend: float
    impressions: int
    clicks: int
    total_revenue: float
    intervention_id: str | None = None
    baseline_budget: float | None = None
    budget_delta: float | None = None
    assignment_type: AssignmentType | None = None
    randomized: bool | None = None

    def __post_init__(self) -> None:
        for name in ("configured_budget", "actual_spend", "total_revenue"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        for name in ("impressions", "clicks"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")

    @property
    def is_intervention(self) -> bool:
        """Return whether this period carries a recorded budget intervention."""

        return self.intervention_id is not None

    @property
    def period_key(self) -> tuple[str, str, str, str | None]:
        """Return the Campaign-period-intervention identity this row aggregates."""

        return (
            self.campaign_id,
            self.marketplace,
            self.report_start_date,
            self.intervention_id,
        )


@dataclass(frozen=True)
class CampaignResponseDataset:
    """Every Campaign-period response observation from one build.

    Attributes:
        observations: Rows ordered by Campaign, marketplace, and period.
    """

    observations: tuple[CampaignResponseObservation, ...] = field(default_factory=tuple)

    def __len__(self) -> int:
        return len(self.observations)

    def __iter__(self):
        return iter(self.observations)

    @property
    def campaign_ids(self) -> tuple[str, ...]:
        """Return every distinct Campaign present, in stable order."""

        seen: dict[str, None] = {}
        for item in self.observations:
            seen.setdefault(item.campaign_id, None)
        return tuple(seen)

    def for_campaign(self, campaign_id: str) -> tuple[CampaignResponseObservation, ...]:
        """Return one Campaign's observations in period order."""

        return tuple(
            item for item in self.observations if item.campaign_id == campaign_id
        )

    def by_campaign(self) -> Mapping[str, tuple[CampaignResponseObservation, ...]]:
        """Return every Campaign's observations keyed by Campaign identifier."""

        grouped: dict[str, list[CampaignResponseObservation]] = defaultdict(list)
        for item in self.observations:
            grouped[item.campaign_id].append(item)
        return {key: tuple(value) for key, value in grouped.items()}


def build_campaign_response_dataset(
    episodes: Iterable[CampaignEpisode],
) -> CampaignResponseDataset:
    """Aggregate Campaign episodes into Campaign-period response observations.

    Args:
        episodes: Model-facing ``CampaignEpisode`` records. Several episodes
            covering the same Campaign, marketplace, period, and assigned
            intervention are summed into one observation, which is how a
            Campaign advertising several Products yields one experimental-arm
            revenue figure.

    Returns:
        CampaignResponseDataset: One row per Campaign, marketplace, period,
            and intervention.

    Raises:
        ResponseDatasetError: If an ``EvaluationEpisode`` is supplied, if an
            episode has no budget observation, or if one Campaign-period
            carries conflicting currency or decision metadata.
    """

    grouped: dict[tuple[str, str, str, str], list[CampaignEpisode]] = defaultdict(list)
    for episode in episodes:
        if isinstance(episode, EvaluationEpisode):
            raise ResponseDatasetError(
                "EvaluationEpisode carries simulator ground truth and must not "
                "reach the response dataset; pass its .episode instead"
            )
        if not isinstance(episode, CampaignEpisode):
            raise ResponseDatasetError(
                f"expected CampaignEpisode, received {type(episode).__name__}"
            )
        observation = episode.budget_observation
        if observation is None:
            raise ResponseDatasetError(
                f"campaign {episode.campaign.campaign_id!r} has no "
                "budget_observation, so its budget response is unknown"
            )
        scope = observation.reporting_scope
        grouped[
            (
                episode.campaign.campaign_id,
                scope.marketplace,
                scope.report_start_date,
                observation.intervention_id or "",
            )
        ].append(episode)

    observations = [
        _aggregate_period(key, value) for key, value in sorted(grouped.items())
    ]
    return CampaignResponseDataset(observations=tuple(observations))


def _aggregate_period(
    key: tuple[str, str, str, str], episodes: Sequence[CampaignEpisode]
) -> CampaignResponseObservation:
    """Sum one Campaign-period-intervention into a response observation."""

    campaign_id, marketplace, report_start_date, _intervention_key = key
    first = episodes[0]
    budget = first.budget_observation
    scope = budget.reporting_scope

    currencies = {
        episode.budget_observation.reporting_scope.currency for episode in episodes
    }
    if len(currencies) != 1:
        raise ResponseDatasetError(
            f"campaign-period {key!r} mixes currencies {sorted(currencies)}"
        )
    # Budget and spend describe the Campaign-period itself, so they are taken
    # once rather than summed over episodes that repeat the same decision.
    configured_budget = _consistent_value(
        key,
        "configured_budget",
        (episode.budget_observation.configured_budget for episode in episodes),
    )
    actual_spend = _consistent_value(
        key,
        "actual_spend",
        (episode.budget_observation.actual_spend for episode in episodes),
    )
    for name in (
        "baseline_budget",
        "budget_delta",
        "assignment_type",
        "randomized",
    ):
        _consistent_value(
            key,
            name,
            (getattr(episode.budget_observation, name) for episode in episodes),
        )

    impressions = 0
    clicks = 0
    total_revenue = 0.0
    for episode in episodes:
        for delivery in episode.delivery_observations:
            impressions += delivery.impressions or 0
            clicks += delivery.clicks or 0
        for outcome in episode.outcome_observations:
            total_revenue += outcome.total_revenue or 0.0

    return CampaignResponseObservation(
        campaign_id=campaign_id,
        marketplace=marketplace,
        report_start_date=report_start_date,
        report_end_date=scope.report_end_date,
        currency=scope.currency,
        provider=first.campaign.provider,
        ad_product=first.campaign.ad_product,
        campaign_status=first.campaign.status,
        configured_budget=configured_budget,
        actual_spend=actual_spend,
        impressions=impressions,
        clicks=clicks,
        total_revenue=round(total_revenue, 6),
        intervention_id=budget.intervention_id,
        baseline_budget=budget.baseline_budget,
        budget_delta=budget.budget_delta,
        assignment_type=budget.assignment_type,
        randomized=budget.randomized,
    )


def _consistent_value(
    key: tuple[str, str, str, str], name: str, values: Iterable[object]
):
    """Return repeated decision metadata, refusing contradictory copies."""
    items = list(values)
    distinct = set(items)
    if len(distinct) != 1:
        raise ResponseDatasetError(
            f"campaign-period-intervention {key!r} carries conflicting {name}: "
            f"{sorted(str(item) for item in distinct)}"
        )
    value = items[0]
    if name in {"configured_budget", "actual_spend"}:
        return 0.0 if value is None else float(value)
    return value


def assert_no_forbidden_response_features(feature_names: Iterable[str]) -> None:
    """Reject attribution or ground-truth names used as response features.

    Args:
        feature_names: Candidate feature names a response model would read.

    Raises:
        ResponseDatasetError: If any name is an attribution result, a
            presentation-only similarity value, or simulator ground truth.
    """

    leaked = sorted(set(feature_names) & FORBIDDEN_RESPONSE_FEATURES)
    if leaked:
        raise ResponseDatasetError(
            "these are not legitimate response-model features: "
            f"{leaked}; attribution divides observed credit and cannot "
            "predict how revenue responds to a budget change"
        )
