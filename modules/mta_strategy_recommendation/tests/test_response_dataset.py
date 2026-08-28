"""Tests for the central Campaign-period response dataset builder.

Covers the model/attribution separation the dataset enforces, correct
Campaign-period aggregation across touchpoints and Products, and rejection of
evaluation-only episodes.
"""

from __future__ import annotations

import unittest

from modules.mta_common.src.budget import BudgetConstraints, BudgetObservation
from modules.mta_common.src.campaign import Campaign
from modules.mta_common.src.delivery import DeliveryObservation
from modules.mta_common.src.enums import (
    AssignmentType,
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
from modules.mta_strategy_recommendation.src.response_dataset import (
    ResponseDatasetError,
    assert_no_forbidden_response_features,
    build_campaign_response_dataset,
)


def _scope(date: str = "2026-01-01", currency: str = "USD") -> ReportingScope:
    return ReportingScope(
        marketplace="US",
        advertiser_id="ADV-1",
        currency=currency,
        report_start_date=date,
        report_end_date=date,
    )


def _touchpoint(interaction: str = "CLICK") -> Touchpoint:
    return Touchpoint(
        provider=Provider.AMAZON_ADS,
        ad_product="SPONSORED_PRODUCTS",
        format="PRODUCT_AD",
        placement="TOP_OF_SEARCH",
        creative=None,
        interaction_type=interaction,
        field_availability=TouchpointFieldAvailability(
            placement=FieldAvailability.AVAILABLE,
            creative=FieldAvailability.NOT_PROVIDED,
            interaction_type=FieldAvailability.AVAILABLE,
        ),
    )


def _episode(
    campaign_id: str = "CAMPAIGN-1",
    date: str = "2026-01-01",
    configured_budget: float = 100.0,
    actual_spend: float = 80.0,
    revenue: float = 400.0,
    impressions: int = 1000,
    clicks: int = 40,
    intervention_id: str | None = "CAMPAIGN-1:US:2026-01-01:1",
    currency: str = "USD",
) -> CampaignEpisode:
    scope = _scope(date, currency)
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
            intervention_id=intervention_id,
            baseline_budget=100.0,
            budget_delta=configured_budget - 100.0,
            assignment_type=AssignmentType.RULE_BASED,
            randomized=False,
        ),
        delivery_observations=(
            DeliveryObservation(
                touchpoint=_touchpoint("IMPRESSION"),
                reporting_scope=scope,
                cost=actual_spend,
                reported_purchases=0,
                reported_sales=0.0,
                impressions=impressions,
            ),
            DeliveryObservation(
                touchpoint=_touchpoint("CLICK"),
                reporting_scope=scope,
                cost=0.0,
                reported_purchases=5,
                reported_sales=revenue,
                clicks=clicks,
            ),
        ),
        outcome_observations=(
            OutcomeObservation(
                touchpoint=_touchpoint("CLICK"),
                reporting_scope=scope,
                total_units=10,
                total_revenue=revenue,
            ),
        ),
    )


class AggregationTest(unittest.TestCase):
    """Campaign-period totals must sum touchpoints and Products correctly."""

    def test_campaign_period_aggregates_delivery_and_revenue(self) -> None:
        """Impressions, clicks, and revenue sum across touchpoints."""

        dataset = build_campaign_response_dataset([_episode()])
        observation = dataset.observations[0]

        self.assertEqual(len(dataset), 1)
        self.assertEqual(observation.impressions, 1000)
        self.assertEqual(observation.clicks, 40)
        self.assertEqual(observation.total_revenue, 400.0)

    def test_budget_and_spend_are_preserved_distinctly(self) -> None:
        """Configured budget and actual spend stay separate fields."""

        dataset = build_campaign_response_dataset(
            [_episode(configured_budget=120.0, actual_spend=90.0)]
        )
        observation = dataset.observations[0]

        self.assertEqual(observation.configured_budget, 120.0)
        self.assertEqual(observation.actual_spend, 90.0)

    def test_multi_product_revenue_sums_within_one_campaign_period(self) -> None:
        """Several Product episodes become one Campaign-period revenue."""

        first = _episode(revenue=400.0)
        second = _episode(revenue=250.0)
        dataset = build_campaign_response_dataset([first, second])

        self.assertEqual(len(dataset), 1)
        self.assertEqual(dataset.observations[0].total_revenue, 650.0)

    def test_budget_is_not_double_counted_across_products(self) -> None:
        """One budget decision is not summed once per linked Product."""

        dataset = build_campaign_response_dataset(
            [_episode(configured_budget=100.0, actual_spend=80.0)] * 3
        )

        self.assertEqual(dataset.observations[0].configured_budget, 100.0)
        self.assertEqual(dataset.observations[0].actual_spend, 80.0)

    def test_intervention_metadata_is_retained(self) -> None:
        """Assignment metadata survives aggregation."""

        observation = build_campaign_response_dataset([_episode()]).observations[0]

        self.assertTrue(observation.is_intervention)
        self.assertEqual(observation.assignment_type, AssignmentType.RULE_BASED)
        self.assertEqual(observation.baseline_budget, 100.0)
        self.assertFalse(observation.randomized)

    def test_distinct_periods_stay_separate(self) -> None:
        """Each Campaign-period is its own response observation."""

        dataset = build_campaign_response_dataset(
            [
                _episode(date="2026-01-01", intervention_id="A"),
                _episode(date="2026-01-02", intervention_id="B"),
            ]
        )

        self.assertEqual(len(dataset), 2)
        self.assertEqual(len(dataset.for_campaign("CAMPAIGN-1")), 2)

    def test_experiment_arms_in_one_period_stay_separate(self) -> None:
        """Parallel budget levels are distinct response observations."""

        dataset = build_campaign_response_dataset(
            [
                _episode(intervention_id="A", configured_budget=75),
                _episode(intervention_id="B", configured_budget=125),
            ]
        )

        self.assertEqual(len(dataset), 2)
        self.assertEqual(
            {item.intervention_id for item in dataset},
            {"A", "B"},
        )

    def test_one_intervention_cannot_repeat_conflicting_budget_metadata(self) -> None:
        """Product episodes repeating one decision must agree on its budget."""

        with self.assertRaisesRegex(ResponseDatasetError, "configured_budget"):
            build_campaign_response_dataset(
                [
                    _episode(intervention_id="A", configured_budget=75),
                    _episode(intervention_id="A", configured_budget=125),
                ]
            )


class ModelSeparationTest(unittest.TestCase):
    """Attribution and simulator truth must not enter the response dataset."""

    def test_evaluation_episode_is_rejected(self) -> None:
        """The training path refuses simulator ground truth outright."""

        evaluation = EvaluationEpisode(
            episode=_episode(),
            ground_truth=EvaluationGroundTruth(
                true_incremental_units=5.0,
                true_incremental_revenue=100.0,
                true_causal_effect="known saturating response",
                simulator_ground_truth_id="GT-1",
            ),
        )

        with self.assertRaisesRegex(ResponseDatasetError, "EvaluationEpisode"):
            build_campaign_response_dataset([evaluation])

    def test_campaign_episode_is_accepted(self) -> None:
        """The model-facing episode type is what the builder consumes."""

        dataset = build_campaign_response_dataset([_episode()])

        self.assertEqual(len(dataset), 1)

    def test_attribution_is_not_required(self) -> None:
        """An episode with no attribution evidence still builds a row."""

        episode = _episode()

        self.assertEqual(episode.attribution_evidence, ())
        self.assertEqual(len(build_campaign_response_dataset([episode])), 1)

    def test_attribution_features_are_refused(self) -> None:
        """Attribution shares are not legitimate response features."""

        for name in ("shapley_share", "markov_share", "attributed_revenue"):
            with self.subTest(feature=name):
                with self.assertRaises(ResponseDatasetError):
                    assert_no_forbidden_response_features([name])

    def test_similarity_reference_is_refused(self) -> None:
        """Dashboard similarity is presentation-only, never a model feature."""

        with self.assertRaises(ResponseDatasetError):
            assert_no_forbidden_response_features(["similarity_reference"])

    def test_ground_truth_fields_are_refused(self) -> None:
        """Simulator truth is not a response feature."""

        with self.assertRaises(ResponseDatasetError):
            assert_no_forbidden_response_features(["true_incremental_revenue"])

    def test_ordinary_decision_time_features_are_allowed(self) -> None:
        """Legitimate context passes the same check."""

        assert_no_forbidden_response_features(
            ["provider", "ad_product", "marketplace", "configured_budget"]
        )

    def test_response_observation_carries_no_ground_truth_field(self) -> None:
        """The row type has no attribute path into evaluation-only truth."""

        observation = build_campaign_response_dataset([_episode()]).observations[0]

        for name in (
            "incremental_revenue",
            "true_incremental_revenue",
            "attribution_evidence",
        ):
            self.assertFalse(hasattr(observation, name))


class ValidationTest(unittest.TestCase):
    """The builder must refuse structurally unusable input."""

    def test_missing_budget_observation_is_rejected(self) -> None:
        """A period with no budget cannot describe a budget response."""

        scope = _scope()
        episode = CampaignEpisode(
            campaign=Campaign(
                campaign_id="CAMPAIGN-1",
                campaign_name="Name",
                provider=Provider.AMAZON_ADS,
                ad_product="SPONSORED_PRODUCTS",
                status="ACTIVE",
                reporting_scope=scope,
            ),
            budget_constraints=BudgetConstraints(
                campaign_id="CAMPAIGN-1",
                budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
            ),
        )

        with self.assertRaisesRegex(ResponseDatasetError, "budget_observation"):
            build_campaign_response_dataset([episode])

    def test_empty_input_produces_an_empty_dataset(self) -> None:
        """No episodes is a valid, empty result rather than an error."""

        dataset = build_campaign_response_dataset([])

        self.assertEqual(len(dataset), 0)
        self.assertEqual(dataset.campaign_ids, ())


if __name__ == "__main__":
    unittest.main()
