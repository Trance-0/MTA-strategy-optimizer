"""A strategy decision paired with what was then observed, and the layers over it.

A strategy evaluation needs one thing an attribution evaluation does not: the
decision. Attribution scores a model's explanation of what already happened,
so the model plus the dataset is enough. A strategy proposes budgets that were
never spent, so scoring it requires holding the proposal beside the
observations.

``StrategyEvaluationEpisode`` follows ``EvaluationEpisode``'s design exactly:
composition, not inheritance. It holds ``CampaignEpisode`` values in a field
rather than extending one, and it holds ``EvaluationGroundTruth`` in a
separate optional field. The consequence is that ``isinstance(episode,
CampaignEpisode)`` is ``False`` and ground truth reaches model-facing code only
if a caller deliberately writes the attribute path — a visible act in a diff
rather than an invisible one.

The three layers are three functions. Each returns a result rather than
raising, so one failing layer does not hide the others, and layer three
returns a not-run marker rather than a zero when no ground truth exists: a
zero would read as a strategy that scored nothing, while not-run reads as a
question that was not asked.

Data flow: ``strategy_projection`` -> here -> ``script/evaluate_strategies.py``
-> ``modules/mta_strategy_evaluation/outputs/strategy_evaluation.json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from modules.mta_common.src.episode import CampaignEpisode
from modules.mta_common.src.evaluation_only import (
    EvaluationEpisode,
    EvaluationGroundTruth,
)

from .strategy_output import ConservationReport, StrategyOutput

#: Layer three has nothing to score against in any configuration this
#: repository supports, and says so in these words rather than by returning a
#: zero. MTA-SIM publishes attribution ground truth, not strategy ground truth.
GROUND_TRUTH_NOT_AVAILABLE = (
    "No strategy ground truth is available: the simulator publishes attribution "
    "ground truth, not a true optimal allocation. This layer was not run."
)


@dataclass(frozen=True)
class StrategyEvaluationEpisode:
    """One strategy decision, the observations that followed, and optional truth.

    Attributes:
        strategy_output: The decision under evaluation.
        episodes: Model-facing observations for the same Campaigns and
            window. Ordinary ``CampaignEpisode`` values, so everything already
            true of them stays true.
        ground_truth: The simulator's true optimal allocation, when one
            exists. ``None`` for every evaluation this repository can
            currently run, and ``None`` rather than a fabricated value.
    """

    strategy_output: StrategyOutput
    episodes: tuple[CampaignEpisode, ...] = field(default_factory=tuple)
    ground_truth: EvaluationGroundTruth | None = None

    def __post_init__(self) -> None:
        for episode in self.episodes:
            if isinstance(episode, EvaluationEpisode):
                raise ValueError(
                    "EvaluationEpisode carries simulator ground truth and must "
                    "not be placed among the model-facing episodes; pass its "
                    ".episode and put the truth in ground_truth"
                )
            if not isinstance(episode, CampaignEpisode):
                raise ValueError(
                    f"expected CampaignEpisode, received {type(episode).__name__}"
                )

        observed = {episode.campaign.campaign_id for episode in self.episodes}
        allocated = {
            decision.campaign_id for decision in self.strategy_output.campaigns
        }
        missing = sorted(allocated - observed)
        if missing:
            raise ValueError(
                "every allocated Campaign needs at least one episode to be "
                f"evaluated against; {missing} have none"
            )

        currency = self.strategy_output.scope.currency
        mismatched = {
            episode.campaign.reporting_scope.currency for episode in self.episodes
        } - {currency}
        if mismatched:
            raise ValueError(
                "the strategy's currency and its episodes' must agree; the "
                f"strategy is in {currency!r} and episodes carry "
                f"{sorted(mismatched)}"
            )

    @property
    def unallocated_campaign_ids(self) -> tuple[str, ...]:
        """Observed Campaigns the strategy did not allocate to, in stable order.

        Reported rather than enforced. A strategy that ignores an observed
        Campaign is making a decision, not committing an error, but a
        comparison that silently omitted it would overstate its coverage.
        """

        allocated = {
            decision.campaign_id for decision in self.strategy_output.campaigns
        }
        seen: dict[str, None] = {}
        for episode in self.episodes:
            identifier = episode.campaign.campaign_id
            if identifier not in allocated:
                seen.setdefault(identifier, None)
        return tuple(seen)


@dataclass(frozen=True)
class ContractCheckResult:
    """Layer one: whether one strategy is internally correct and conserving.

    Attributes:
        strategy_id: The strategy this checked.
        conservation: The derived conservation report.
        violations: Each violation with its residual, in constraint order.
            ``is_conserving`` is a property over this, so the two cannot
            disagree.
    """

    strategy_id: str
    conservation: ConservationReport
    violations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_conserving(self) -> bool:
        """Return whether the checked allocation conserves."""

        return not self.violations

    def to_dict(self) -> dict:
        """Return this result as JSON-compatible values."""

        return {
            "strategy_id": self.strategy_id,
            "is_conserving": self.is_conserving,
            "violations": list(self.violations),
            "conservation": self.conservation.to_dict(),
        }


@dataclass(frozen=True)
class CampaignEfficiency:
    """One Campaign's observed return per unit of spend, and what it was given.

    Attributes:
        campaign_id: The Campaign.
        observed_spend: What it actually spent across the observed period.
        observed_revenue: What it earned across the same period.
        revenue_per_spend: ``observed_revenue / observed_spend``, or ``None``
            when nothing was spent — an efficiency is undefined without a
            denominator, and zero would rank an unspent Campaign as the worst
            rather than as unmeasured.
        strategy_share: The share the strategy gave it.
        equal_share: The share an equal split across the allocated Campaigns
            would have given it.
        observed_share: Its share of the observed configured budget, or
            ``None`` when no budget was configured anywhere.
    """

    campaign_id: str
    observed_spend: float
    observed_revenue: float
    revenue_per_spend: float | None
    strategy_share: float
    equal_share: float
    observed_share: float | None

    def to_dict(self) -> dict:
        """Return this row as JSON-compatible values."""

        return {
            "campaign_id": self.campaign_id,
            "observed_spend": self.observed_spend,
            "observed_revenue": self.observed_revenue,
            "revenue_per_spend": self.revenue_per_spend,
            "strategy_share": self.strategy_share,
            "equal_share": self.equal_share,
            "observed_share": self.observed_share,
        }


@dataclass(frozen=True)
class BaselineComparisonResult:
    """Layer two: whether the strategy moved budget toward observed efficiency.

    This reports a ranking agreement, not a revenue prediction. It answers
    "did the strategy concentrate budget in the Campaigns observed to return
    more per unit spent", which observed data can answer, rather than "how
    much revenue would this plan have produced", which it cannot.

    Attributes:
        campaigns: One row per allocated Campaign, in the strategy's order.
        rank_agreement: Kendall's tau-b between the strategy's shares and
            observed efficiency, in ``[-1, 1]``. ``None`` when fewer than two
            Campaigns carry a measurable efficiency, because a ranking of one
            item has no direction.
        equal_split_agreement: The same statistic for an equal split, which is
            always ``None`` — an equal split assigns every Campaign the same
            share, so it expresses no preference to agree or disagree. Present
            so a reader sees the baseline was considered rather than omitted.
        observed_budget_agreement: The same statistic for the observed
            configured budget, or ``None`` when no budget was configured.
        unallocated_campaign_ids: Observed Campaigns the strategy did not
            allocate to, named rather than silently excluded.
        notes: Why a statistic is absent, when one is.
    """

    campaigns: tuple[CampaignEfficiency, ...] = field(default_factory=tuple)
    rank_agreement: float | None = None
    equal_split_agreement: float | None = None
    observed_budget_agreement: float | None = None
    unallocated_campaign_ids: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        """Return this result as JSON-compatible values."""

        return {
            "campaigns": [row.to_dict() for row in self.campaigns],
            "rank_agreement": self.rank_agreement,
            "equal_split_agreement": self.equal_split_agreement,
            "observed_budget_agreement": self.observed_budget_agreement,
            "unallocated_campaign_ids": list(self.unallocated_campaign_ids),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class GroundTruthScore:
    """Layer three: how close the strategy came to a known optimal allocation.

    Attributes:
        was_run: Whether ground truth was available to score against.
        reason: Why it was not run, when it was not.
        allocation_error: Total absolute share difference from the optimum,
            populated only once a simulator publishes one.
    """

    was_run: bool = False
    reason: str = GROUND_TRUTH_NOT_AVAILABLE
    allocation_error: float | None = None

    def to_dict(self) -> dict:
        """Return this result as JSON-compatible values."""

        return {
            "was_run": self.was_run,
            "reason": self.reason,
            "allocation_error": self.allocation_error,
        }


@dataclass(frozen=True)
class StrategyEvaluationResult:
    """Every layer's result for one strategy.

    Attributes:
        strategy_id: The evaluated strategy.
        allocation_type: ``INITIAL_SEED`` or ``OPTIMIZED``, reported so the
            two are read separately rather than averaged.
        contract: Layer one.
        baseline_comparison: Layer two, or ``None`` when layer one failed and
            the strategy was not scored further.
        ground_truth: Layer three, always a not-run marker today.
    """

    strategy_id: str
    allocation_type: str
    contract: ContractCheckResult
    baseline_comparison: BaselineComparisonResult | None = None
    ground_truth: GroundTruthScore = field(default_factory=GroundTruthScore)

    def to_dict(self) -> dict:
        """Return every layer's result as JSON-compatible values."""

        return {
            "strategy_id": self.strategy_id,
            "allocation_type": self.allocation_type,
            "contract": self.contract.to_dict(),
            "baseline_comparison": (
                None
                if self.baseline_comparison is None
                else self.baseline_comparison.to_dict()
            ),
            "ground_truth": self.ground_truth.to_dict(),
        }


def check_contract(strategy_output: StrategyOutput) -> ContractCheckResult:
    """Layer one: is this strategy internally correct and conserving?

    Needs no observation and no ground truth. This is the only layer that can
    fail a strategy outright: a comparison against a plan that has lost or
    invented money is not meaningful, so a non-conserving plan is not scored
    further.

    Args:
        strategy_output: The decision to check.

    Returns:
        ContractCheckResult: The conservation report and every violation.
    """

    report = strategy_output.conservation()
    return ContractCheckResult(
        strategy_id=strategy_output.strategy_id,
        conservation=report,
        violations=report.violations,
    )


def compare_to_baselines(
    episode: StrategyEvaluationEpisode,
) -> BaselineComparisonResult:
    """Layer two: did the strategy move budget toward observed efficiency?

    Needs observations, no ground truth. The baselines are built from the same
    observations the comparison is made against, so this measures consistency
    with observed efficiency rather than out-of-sample performance. A strategy
    that concentrates budget in the historically best Campaign scores well by
    construction — a description of the metric, not evidence about the
    strategy.

    Args:
        episode: The decision and the observations that followed it.

    Returns:
        BaselineComparisonResult: One row per allocated Campaign and the rank
        agreement statistics, with a note wherever one is absent.
    """

    totals: dict[str, list[float]] = {}
    configured: dict[str, float] = {}
    for item in episode.episodes:
        identifier = item.campaign.campaign_id
        spend, revenue = totals.setdefault(identifier, [0.0, 0.0])
        observation = item.budget_observation
        if observation is not None:
            spend += observation.actual_spend or 0.0
            configured[identifier] = configured.get(identifier, 0.0) + (
                observation.configured_budget or 0.0
            )
        for outcome in item.outcome_observations:
            revenue += outcome.total_revenue or 0.0
        totals[identifier] = [spend, revenue]

    decisions = episode.strategy_output.campaigns
    equal_share = 1.0 / len(decisions) if decisions else 0.0
    configured_total = sum(
        configured.get(decision.campaign_id, 0.0) for decision in decisions
    )

    rows = tuple(
        CampaignEfficiency(
            campaign_id=decision.campaign_id,
            observed_spend=totals.get(decision.campaign_id, [0.0, 0.0])[0],
            observed_revenue=totals.get(decision.campaign_id, [0.0, 0.0])[1],
            revenue_per_spend=_ratio(
                totals.get(decision.campaign_id, [0.0, 0.0])[1],
                totals.get(decision.campaign_id, [0.0, 0.0])[0],
            ),
            strategy_share=decision.budget_share,
            equal_share=equal_share,
            observed_share=(
                configured.get(decision.campaign_id, 0.0) / configured_total
                if configured_total > 0
                else None
            ),
        )
        for decision in decisions
    )

    measurable = [row for row in rows if row.revenue_per_spend is not None]
    notes: list[str] = []
    if len(measurable) < 2:
        notes.append(
            "Fewer than two Campaigns recorded spend, so no ranking has a "
            "direction and no agreement statistic is reported."
        )

    efficiencies = [row.revenue_per_spend for row in measurable]
    rank_agreement = _kendall_tau(
        [row.strategy_share for row in measurable], efficiencies
    )
    observed_agreement = None
    if all(row.observed_share is not None for row in measurable):
        observed_agreement = _kendall_tau(
            [row.observed_share for row in measurable], efficiencies
        )
    else:
        notes.append(
            "No configured budget was observed, so the observed-budget baseline "
            "has no shares to rank."
        )

    notes.append(
        "An equal split assigns every Campaign the same share, so it expresses "
        "no preference and its agreement is undefined rather than zero."
    )
    if episode.unallocated_campaign_ids:
        notes.append(
            "These Campaigns were observed but not allocated to, so they are "
            f"outside this comparison: {list(episode.unallocated_campaign_ids)}."
        )

    return BaselineComparisonResult(
        campaigns=rows,
        rank_agreement=rank_agreement,
        equal_split_agreement=None,
        observed_budget_agreement=observed_agreement,
        unallocated_campaign_ids=episode.unallocated_campaign_ids,
        notes=tuple(notes),
    )


def score_against_ground_truth(
    episode: StrategyEvaluationEpisode,
) -> GroundTruthScore:
    """Layer three: does the strategy recover a known optimal allocation?

    Returns a not-run result when no ground truth is present, which is every
    run this repository can currently perform.

    Args:
        episode: The decision, the observations, and the optional truth.

    Returns:
        GroundTruthScore: A not-run marker whenever ``episode.ground_truth``
        is ``None``, never a zero score.
    """

    if episode.ground_truth is None:
        return GroundTruthScore()
    # A simulator that publishes a true optimal allocation would be scored
    # here. EvaluationGroundTruth carries a true incremental effect rather than
    # an allocation, so there is nothing to compare shares against, and this
    # layer says so rather than deriving an allocation from an effect.
    return GroundTruthScore(
        was_run=False,
        reason=(
            "Ground truth is present but carries a true incremental effect "
            "rather than a true optimal allocation, so there is no allocation "
            "to compare the strategy's shares against."
        ),
    )


def run_evaluation_layers(
    episode: StrategyEvaluationEpisode,
) -> StrategyEvaluationResult:
    """Run all three layers in order and return every result.

    Does not short-circuit on a failing contract in the sense of hiding it:
    the contract result is always returned, and only the baseline comparison
    is skipped when the plan does not conserve, because comparing a plan that
    lost or invented money is not meaningful.

    Args:
        episode: The decision and the observations that followed it.

    Returns:
        StrategyEvaluationResult: Layer one always, layer two when the
        contract held, and layer three's not-run marker.
    """

    contract = check_contract(episode.strategy_output)
    comparison = compare_to_baselines(episode) if contract.is_conserving else None
    return StrategyEvaluationResult(
        strategy_id=episode.strategy_output.strategy_id,
        allocation_type=episode.strategy_output.allocation_type,
        contract=contract,
        baseline_comparison=comparison,
        ground_truth=score_against_ground_truth(episode),
    )


def _ratio(numerator: float, denominator: float) -> float | None:
    """Return a ratio, or None when the denominator is zero.

    Zero would rank a Campaign that spent nothing as the least efficient one
    rather than as an unmeasured one, which is a different claim.
    """

    return numerator / denominator if denominator > 0 else None


def _kendall_tau(left: list[float], right: list[float]) -> float | None:
    """Kendall's tau-b between two rankings, or None when it has no direction.

    Tau-b rather than tau-a because ties are expected here: two Campaigns can
    easily receive the same share, and tau-a would treat a tie as neither
    agreement nor disagreement while still counting it in the denominator,
    understating agreement on small Campaign sets.
    """

    count = len(left)
    if count < 2 or len(right) != count:
        return None

    concordant = 0
    discordant = 0
    left_ties = 0
    right_ties = 0
    for i in range(count):
        for j in range(i + 1, count):
            a = left[i] - left[j]
            b = right[i] - right[j]
            if a == 0 and b == 0:
                left_ties += 1
                right_ties += 1
            elif a == 0:
                left_ties += 1
            elif b == 0:
                right_ties += 1
            elif (a > 0) == (b > 0):
                concordant += 1
            else:
                discordant += 1

    pairs = count * (count - 1) / 2
    denominator = ((pairs - left_ties) * (pairs - right_ties)) ** 0.5
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator
