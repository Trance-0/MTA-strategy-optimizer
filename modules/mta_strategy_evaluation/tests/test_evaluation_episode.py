"""Tests for the strategy evaluation episode and its three layers.

Covers the composition boundary that keeps ground truth out of model-facing
code, the constructor's cross-object checks, and each layer's behaviour when
what it needs is absent — which is the case the layers exist to report rather
than to fail on.
"""

from __future__ import annotations

import unittest

from modules.mta_common.src.budget import BudgetConstraints, BudgetObservation
from modules.mta_common.src.campaign import Campaign
from modules.mta_common.src.enums import (
    BudgetUsagePolicy,
    FieldAvailability,
    Provider,
)
from modules.mta_common.src.episode import CampaignEpisode
from modules.mta_common.src.evaluation_only import (
    EvaluationEpisode,
    EvaluationGroundTruth,
)
from modules.mta_common.src.outcome import OutcomeObservation
from modules.mta_common.src.reporting_scope import ReportingScope
from modules.mta_common.src.touchpoint import (
    Touchpoint,
    TouchpointFieldAvailability,
)
from modules.mta_strategy_evaluation.src.evaluation_episode import (
    GROUND_TRUTH_NOT_AVAILABLE,
    StrategyEvaluationEpisode,
    check_contract,
    compare_to_baselines,
    run_evaluation_layers,
    score_against_ground_truth,
)
from modules.mta_strategy_evaluation.src.strategy_output import (
    CampaignBudgetDecision,
    StrategyOutput,
)


def _scope(currency: str = "USD") -> ReportingScope:
    return ReportingScope(
        marketplace="TOY",
        advertiser_id="adv_demo_001",
        currency=currency,
        report_start_date="2026-01-01",
        report_end_date="2026-01-20",
    )


def _touchpoint() -> Touchpoint:
    return Touchpoint(
        provider=Provider.AMAZON_ADS,
        ad_product="SPONSORED_PRODUCTS",
        format="PRODUCT_AD",
        placement="TOP_OF_SEARCH",
        creative=None,
        interaction_type="CLICK",
        field_availability=TouchpointFieldAvailability(
            placement=FieldAvailability.AVAILABLE,
            creative=FieldAvailability.NOT_PROVIDED,
            interaction_type=FieldAvailability.AVAILABLE,
        ),
    )


def _episode(
    campaign_id: str = "C-1",
    configured_budget: float = 50.0,
    actual_spend: float = 40.0,
    revenue: float = 200.0,
    currency: str = "USD",
) -> CampaignEpisode:
    scope = _scope(currency)
    return CampaignEpisode(
        campaign=Campaign(
            campaign_id=campaign_id,
            campaign_name=f"Name {campaign_id}",
            provider=Provider.AMAZON_ADS,
            ad_product="SPONSORED_PRODUCTS",
            status="ACTIVE",
            reporting_scope=scope,
        ),
        budget_constraints=BudgetConstraints(
            campaign_id=campaign_id,
            budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
        ),
        budget_observation=BudgetObservation(
            campaign_id=campaign_id,
            reporting_scope=scope,
            configured_budget=configured_budget,
            actual_spend=actual_spend,
        ),
        outcome_observations=(
            OutcomeObservation(
                touchpoint=_touchpoint(),
                reporting_scope=scope,
                total_units=5,
                total_revenue=revenue,
            ),
        ),
    )


def _output(
    campaigns: tuple[CampaignBudgetDecision, ...] | None = None,
) -> StrategyOutput:
    return StrategyOutput(
        strategy_id="campaign_response_optimizer",
        strategy_version="1.0.0",
        allocation_type="OPTIMIZED",
        scope=_scope(),
        campaigns=campaigns
        or (
            CampaignBudgetDecision(campaign_id="C-1", budget_share=0.75, budget=75.0),
            CampaignBudgetDecision(campaign_id="C-2", budget_share=0.25, budget=25.0),
        ),
        total_budget=100.0,
    )


def _ground_truth() -> EvaluationGroundTruth:
    return EvaluationGroundTruth(
        true_incremental_units=3.0,
        true_incremental_revenue=120.0,
        true_causal_effect="SIMULATED_UPLIFT",
        simulator_ground_truth_id="GT-1",
    )


class CompositionTest(unittest.TestCase):
    """The episode holds observations rather than extending one."""

    def test_a_strategy_episode_is_not_a_campaign_episode(self) -> None:
        """Composition, not inheritance, is what keeps the two separable."""

        episode = StrategyEvaluationEpisode(
            strategy_output=_output(),
            episodes=(_episode("C-1"), _episode("C-2")),
        )

        self.assertNotIsInstance(episode, CampaignEpisode)

    def test_an_evaluation_episode_may_not_join_the_model_facing_episodes(
        self,
    ) -> None:
        """Ground truth reaches this type only through its own field."""

        with self.assertRaises(ValueError):
            StrategyEvaluationEpisode(
                strategy_output=_output(
                    campaigns=(
                        CampaignBudgetDecision(campaign_id="C-1", budget_share=1.0),
                    )
                ),
                episodes=(
                    EvaluationEpisode(
                        episode=_episode("C-1"), ground_truth=_ground_truth()
                    ),
                ),
            )

    def test_a_non_episode_is_rejected(self) -> None:
        """Only CampaignEpisode values are observations."""

        with self.assertRaises(ValueError):
            StrategyEvaluationEpisode(
                strategy_output=_output(
                    campaigns=(
                        CampaignBudgetDecision(campaign_id="C-1", budget_share=1.0),
                    )
                ),
                episodes=("C-1",),
            )


class ConstructionTest(unittest.TestCase):
    """Cross-object checks that make an evaluation meaningful."""

    def test_every_allocated_campaign_needs_an_observation(self) -> None:
        """A Campaign with no episode has nothing to be scored against."""

        with self.assertRaises(ValueError) as raised:
            StrategyEvaluationEpisode(
                strategy_output=_output(), episodes=(_episode("C-1"),)
            )

        self.assertIn("C-2", str(raised.exception))

    def test_currencies_must_agree(self) -> None:
        """A share of one currency cannot be scored against another."""

        with self.assertRaises(ValueError):
            StrategyEvaluationEpisode(
                strategy_output=_output(
                    campaigns=(
                        CampaignBudgetDecision(campaign_id="C-1", budget_share=1.0),
                    )
                ),
                episodes=(_episode("C-1", currency="EUR"),),
            )

    def test_an_unallocated_campaign_is_reported_rather_than_rejected(self) -> None:
        """Ignoring an observed Campaign is a decision, not an error."""

        episode = StrategyEvaluationEpisode(
            strategy_output=_output(
                campaigns=(
                    CampaignBudgetDecision(campaign_id="C-1", budget_share=1.0),
                )
            ),
            episodes=(_episode("C-1"), _episode("C-2")),
        )

        self.assertEqual(episode.unallocated_campaign_ids, ("C-2",))


class ContractLayerTest(unittest.TestCase):
    """Layer one needs no observation and no ground truth."""

    def test_a_conserving_strategy_passes(self) -> None:
        """The happy path reports no violation."""

        result = check_contract(_output())

        self.assertTrue(result.is_conserving)
        self.assertEqual(result.violations, ())

    def test_a_non_conserving_strategy_fails_with_its_violations(self) -> None:
        """The residual is reported rather than raised."""

        result = check_contract(
            StrategyOutput(
                strategy_id="s",
                strategy_version="1.0.0",
                allocation_type="OPTIMIZED",
                scope=_scope(),
                campaigns=(
                    CampaignBudgetDecision(campaign_id="C-1", budget_share=0.25),
                ),
            )
        )

        self.assertFalse(result.is_conserving)
        self.assertTrue(result.violations)


class BaselineLayerTest(unittest.TestCase):
    """Layer two measures rank agreement, not predicted revenue."""

    def _episode(self) -> StrategyEvaluationEpisode:
        # C-1 returns 200/40 = 5.0 per unit spent and gets the larger share;
        # C-2 returns 60/40 = 1.5 and gets the smaller. The ranking agrees.
        # Their configured budgets differ so the observed-budget baseline is a
        # ranking rather than a tie.
        return StrategyEvaluationEpisode(
            strategy_output=_output(),
            episodes=(
                _episode("C-1", configured_budget=60.0, revenue=200.0),
                _episode("C-2", configured_budget=40.0, revenue=60.0),
            ),
        )

    def test_agreeing_ranks_score_positively(self) -> None:
        """More budget to the more efficient Campaign is agreement."""

        result = compare_to_baselines(self._episode())

        self.assertEqual(result.rank_agreement, 1.0)

    def test_disagreeing_ranks_score_negatively(self) -> None:
        """The reversed allocation reverses the statistic."""

        result = compare_to_baselines(
            StrategyEvaluationEpisode(
                strategy_output=_output(
                    campaigns=(
                        CampaignBudgetDecision(
                            campaign_id="C-1", budget_share=0.25, budget=25.0
                        ),
                        CampaignBudgetDecision(
                            campaign_id="C-2", budget_share=0.75, budget=75.0
                        ),
                    )
                ),
                episodes=(
                    _episode("C-1", revenue=200.0),
                    _episode("C-2", revenue=60.0),
                ),
            )
        )

        self.assertEqual(result.rank_agreement, -1.0)

    def test_efficiency_is_none_rather_than_zero_when_nothing_was_spent(self) -> None:
        """An unspent Campaign is unmeasured, not the least efficient one."""

        result = compare_to_baselines(
            StrategyEvaluationEpisode(
                strategy_output=_output(),
                episodes=(
                    _episode("C-1", actual_spend=0.0),
                    _episode("C-2", revenue=60.0),
                ),
            )
        )
        unspent = next(row for row in result.campaigns if row.campaign_id == "C-1")

        self.assertIsNone(unspent.revenue_per_spend)

    def test_one_measurable_campaign_yields_no_agreement(self) -> None:
        """A ranking of one item has no direction, and the note says so."""

        result = compare_to_baselines(
            StrategyEvaluationEpisode(
                strategy_output=_output(),
                episodes=(
                    _episode("C-1", actual_spend=0.0),
                    _episode("C-2", actual_spend=0.0),
                ),
            )
        )

        self.assertIsNone(result.rank_agreement)
        self.assertTrue(any("direction" in note for note in result.notes))

    def test_the_equal_split_baseline_is_always_undefined(self) -> None:
        """An equal split expresses no preference, so it cannot agree."""

        result = compare_to_baselines(self._episode())

        self.assertIsNone(result.equal_split_agreement)
        self.assertTrue(any("equal split" in note for note in result.notes))

    def test_every_campaign_gets_its_equal_share(self) -> None:
        """The baseline share is reported per row even though it cannot rank."""

        result = compare_to_baselines(self._episode())

        self.assertEqual([row.equal_share for row in result.campaigns], [0.5, 0.5])

    def test_the_observed_budget_baseline_is_computed_when_present(self) -> None:
        """The observed configured budget is a ranking that can agree."""

        result = compare_to_baselines(self._episode())

        self.assertIsNotNone(result.observed_budget_agreement)

    def test_unallocated_campaigns_are_named_in_the_notes(self) -> None:
        """A comparison that omitted one would overstate its coverage."""

        result = compare_to_baselines(
            StrategyEvaluationEpisode(
                strategy_output=_output(
                    campaigns=(
                        CampaignBudgetDecision(campaign_id="C-1", budget_share=1.0),
                    )
                ),
                episodes=(_episode("C-1"), _episode("C-2")),
            )
        )

        self.assertEqual(result.unallocated_campaign_ids, ("C-2",))
        self.assertTrue(any("C-2" in note for note in result.notes))


class GroundTruthLayerTest(unittest.TestCase):
    """Layer three returns a not-run marker rather than a zero."""

    def test_absent_ground_truth_is_not_run_rather_than_scored_zero(self) -> None:
        """A zero would read as a strategy that scored nothing."""

        score = score_against_ground_truth(
            StrategyEvaluationEpisode(
                strategy_output=_output(),
                episodes=(_episode("C-1"), _episode("C-2")),
            )
        )

        self.assertFalse(score.was_run)
        self.assertEqual(score.reason, GROUND_TRUTH_NOT_AVAILABLE)
        self.assertIsNone(score.allocation_error)

    def test_present_ground_truth_still_carries_no_optimal_allocation(self) -> None:
        """An incremental effect is not an allocation to compare shares to."""

        score = score_against_ground_truth(
            StrategyEvaluationEpisode(
                strategy_output=_output(),
                episodes=(_episode("C-1"), _episode("C-2")),
                ground_truth=_ground_truth(),
            )
        )

        self.assertFalse(score.was_run)
        self.assertIn("incremental effect", score.reason)


class RunEvaluationLayersTest(unittest.TestCase):
    """All three layers run in order, and one failure does not hide another."""

    def test_a_conserving_strategy_is_scored_by_every_layer(self) -> None:
        """Layer two runs when layer one held."""

        result = run_evaluation_layers(
            StrategyEvaluationEpisode(
                strategy_output=_output(),
                episodes=(_episode("C-1"), _episode("C-2")),
            )
        )

        self.assertTrue(result.contract.is_conserving)
        self.assertIsNotNone(result.baseline_comparison)
        self.assertFalse(result.ground_truth.was_run)

    def test_a_non_conserving_strategy_is_not_compared(self) -> None:
        """Comparing a plan that lost or invented money is not meaningful."""

        result = run_evaluation_layers(
            StrategyEvaluationEpisode(
                strategy_output=StrategyOutput(
                    strategy_id="s",
                    strategy_version="1.0.0",
                    allocation_type="OPTIMIZED",
                    scope=_scope(),
                    campaigns=(
                        CampaignBudgetDecision(campaign_id="C-1", budget_share=0.25),
                    ),
                ),
                episodes=(_episode("C-1"),),
            )
        )

        self.assertFalse(result.contract.is_conserving)
        self.assertIsNone(result.baseline_comparison)

    def test_the_result_serializes_to_json_compatible_values(self) -> None:
        """Every layer's payload is plain values the artifact can carry."""

        payload = run_evaluation_layers(
            StrategyEvaluationEpisode(
                strategy_output=_output(),
                episodes=(_episode("C-1"), _episode("C-2")),
            )
        ).to_dict()

        self.assertEqual(payload["allocation_type"], "OPTIMIZED")
        self.assertTrue(payload["contract"]["is_conserving"])
        self.assertFalse(payload["ground_truth"]["was_run"])


if __name__ == "__main__":
    unittest.main()
