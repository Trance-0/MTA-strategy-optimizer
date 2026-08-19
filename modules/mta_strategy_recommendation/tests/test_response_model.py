"""Tests for the two-stage Campaign response model.

Covers the mathematical properties the optimizer relies on (bounded, monotone
spend; monotone, concave revenue), the support states a Campaign can be in,
deterministic fitting, and artifact round-tripping.
"""

from __future__ import annotations

import math
import unittest

from modules.mta_common.src.enums import Provider
from modules.mta_strategy_recommendation.src.response_dataset import (
    CampaignResponseDataset,
    CampaignResponseObservation,
)
from modules.mta_strategy_recommendation.src.response_model import (
    MODEL_VERSION,
    CampaignResponseModel,
    ResponseModelError,
    ResponseSupport,
    RevenueResponse,
    SpendResponse,
    fit_campaign_response_models,
    response_models_from_dict,
    response_models_to_dict,
)


def _observation(
    campaign_id: str = "CAMPAIGN-1",
    day: int = 1,
    configured_budget: float = 100.0,
    actual_spend: float | None = None,
    revenue: float | None = None,
    ad_product: str = "SPONSORED_PRODUCTS",
) -> CampaignResponseObservation:
    """Build one observation on a known saturating response."""

    spend = (
        min(configured_budget, 200.0 * (1.0 - math.exp(-configured_budget / 150.0)))
        if actual_spend is None
        else actual_spend
    )
    earned = (
        50.0 + 900.0 * (1.0 - math.exp(-spend / 90.0))
        if revenue is None
        else revenue
    )
    return CampaignResponseObservation(
        campaign_id=campaign_id,
        marketplace="US",
        report_start_date=f"2026-01-{day:02d}",
        report_end_date=f"2026-01-{day:02d}",
        currency="USD",
        provider=Provider.AMAZON_ADS,
        ad_product=ad_product,
        campaign_status="ACTIVE",
        configured_budget=configured_budget,
        actual_spend=spend,
        impressions=int(spend * 20),
        clicks=int(spend),
        total_revenue=earned,
        intervention_id=f"{campaign_id}:US:2026-01-{day:02d}",
        baseline_budget=100.0,
        budget_delta=configured_budget - 100.0,
    )


def _dataset(
    campaign_id: str = "CAMPAIGN-1",
    budgets: tuple[float, ...] = (40.0, 70.0, 100.0, 130.0, 160.0, 200.0),
    ad_product: str = "SPONSORED_PRODUCTS",
) -> CampaignResponseDataset:
    return CampaignResponseDataset(
        observations=tuple(
            _observation(
                campaign_id=campaign_id,
                day=index + 1,
                configured_budget=budget,
                ad_product=ad_product,
            )
            for index, budget in enumerate(budgets)
        )
    )


class SpendResponseTest(unittest.TestCase):
    """The spend stage must stay bounded and monotone."""

    def test_expected_spend_is_never_negative(self) -> None:
        """Zero or negative budget yields no spend."""

        response = SpendResponse(capacity=200.0, scale=150.0)

        self.assertEqual(response.expected_spend(0.0), 0.0)
        self.assertGreaterEqual(response.expected_spend(50.0), 0.0)

    def test_expected_spend_never_exceeds_budget(self) -> None:
        """A Campaign cannot spend more than it was authorized."""

        response = SpendResponse(capacity=500.0, scale=10.0)

        for budget in (1.0, 5.0, 25.0, 100.0, 400.0):
            self.assertLessEqual(response.expected_spend(budget), budget + 1e-9)

    def test_expected_spend_is_monotone(self) -> None:
        """More budget never means less expected spend."""

        response = SpendResponse(capacity=200.0, scale=150.0)
        values = [response.expected_spend(budget) for budget in range(0, 400, 20)]

        for first, second in zip(values, values[1:]):
            self.assertGreaterEqual(second, first)

    def test_under_delivery_is_representable(self) -> None:
        """Spend can saturate below a large budget."""

        response = SpendResponse(capacity=100.0, scale=50.0)

        self.assertLess(response.expected_spend(1000.0), 1000.0)
        self.assertLessEqual(response.expected_spend(1000.0), 100.0)


class RevenueResponseTest(unittest.TestCase):
    """The revenue stage must be monotone with diminishing returns."""

    def test_revenue_is_monotone_in_spend(self) -> None:
        """More spend never means less expected revenue."""

        response = RevenueResponse(baseline=50.0, alpha=900.0, kappa=90.0)
        values = [response.expected_revenue(spend) for spend in range(0, 400, 20)]

        for first, second in zip(values, values[1:]):
            self.assertGreaterEqual(second, first)

    def test_marginal_revenue_diminishes(self) -> None:
        """Each additional unit of spend earns strictly less."""

        response = RevenueResponse(baseline=50.0, alpha=900.0, kappa=90.0)
        marginals = [response.marginal_revenue(spend) for spend in range(0, 400, 20)]

        for first, second in zip(marginals, marginals[1:]):
            self.assertLess(second, first)

    def test_baseline_is_returned_at_zero_spend(self) -> None:
        """Revenue at no spend is the fitted organic baseline."""

        response = RevenueResponse(baseline=50.0, alpha=900.0, kappa=90.0)

        self.assertEqual(response.expected_revenue(0.0), 50.0)

    def test_negative_parameters_are_rejected(self) -> None:
        """The concave, increasing shape is enforced at construction."""

        with self.assertRaises(ValueError):
            RevenueResponse(baseline=0.0, alpha=-1.0, kappa=90.0)
        with self.assertRaises(ValueError):
            RevenueResponse(baseline=0.0, alpha=1.0, kappa=0.0)


class FittingTest(unittest.TestCase):
    """Fitting must be deterministic and recover a known response."""

    def test_target_history_is_fitted_from_own_variation(self) -> None:
        """A Campaign with enough budget variation fits its own curve."""

        models = fit_campaign_response_models(_dataset())
        model = models["CAMPAIGN-1"]

        self.assertEqual(model.diagnostics.support, ResponseSupport.TARGET_HISTORY)
        self.assertTrue(model.is_usable)
        self.assertEqual(model.diagnostics.observation_count, 6)
        self.assertEqual(model.diagnostics.intervention_count, 6)

    def test_fit_is_deterministic(self) -> None:
        """The same dataset always produces identical parameters."""

        first = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]
        second = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]

        self.assertEqual(first.to_str(), second.to_str())

    def test_fitted_revenue_response_is_concave(self) -> None:
        """The recovered curve keeps diminishing marginal revenue."""

        model = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]
        marginals = [
            model.marginal_expected_revenue(budget)
            for budget in (20.0, 60.0, 100.0, 140.0, 180.0)
        ]

        for first, second in zip(marginals, marginals[1:]):
            self.assertLessEqual(second, first)

    def test_fitted_spend_response_respects_the_budget_cap(self) -> None:
        """The fitted spend stage never predicts overspending."""

        model = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]

        for budget in (10.0, 50.0, 120.0, 300.0):
            self.assertLessEqual(model.expected_spend(budget), budget + 1e-9)

    def test_expected_revenue_composes_both_stages(self) -> None:
        """Composed revenue equals revenue evaluated at expected spend."""

        model = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]

        self.assertAlmostEqual(
            model.expected_revenue(120.0),
            model.expected_revenue_from_spend(model.expected_spend(120.0)),
            places=9,
        )

    def test_fit_quality_is_reported(self) -> None:
        """Residual summaries accompany every fit."""

        diagnostics = fit_campaign_response_models(_dataset())[
            "CAMPAIGN-1"
        ].diagnostics

        self.assertIsNotNone(diagnostics.revenue_mean_absolute_error)
        self.assertIsNotNone(diagnostics.revenue_root_mean_square_error)
        self.assertIsNotNone(diagnostics.spend_mean_absolute_error)
        self.assertEqual(diagnostics.model_version, MODEL_VERSION)


class SupportStateTest(unittest.TestCase):
    """Each Campaign must report honestly what evidence stands behind it."""

    def test_insufficient_support_for_one_observation(self) -> None:
        """One data point cannot produce a falsely precise curve."""

        dataset = CampaignResponseDataset(observations=(_observation(),))
        model = fit_campaign_response_models(dataset)["CAMPAIGN-1"]

        self.assertEqual(
            model.diagnostics.support, ResponseSupport.INSUFFICIENT_SUPPORT
        )
        self.assertFalse(model.is_usable)

    def test_insufficient_support_without_budget_variation(self) -> None:
        """Repeating one budget says nothing about a budget change."""

        dataset = _dataset(budgets=(100.0, 100.0, 100.0, 100.0, 100.0))
        model = fit_campaign_response_models(dataset)["CAMPAIGN-1"]

        self.assertEqual(
            model.diagnostics.support, ResponseSupport.INSUFFICIENT_SUPPORT
        )

    def test_unusable_model_refuses_to_predict(self) -> None:
        """An unsupported Campaign raises rather than inventing a number."""

        dataset = CampaignResponseDataset(observations=(_observation(),))
        model = fit_campaign_response_models(dataset)["CAMPAIGN-1"]

        with self.assertRaises(ResponseModelError):
            model.expected_revenue(100.0)

    def test_pooled_transfer_supports_a_new_campaign(self) -> None:
        """A Campaign without history borrows comparable Campaigns' evidence."""

        rich = _dataset(campaign_id="CAMPAIGN-RICH").observations
        other = _dataset(campaign_id="CAMPAIGN-OTHER").observations
        newcomer = (_observation(campaign_id="CAMPAIGN-NEW", day=1),)
        models = fit_campaign_response_models(
            CampaignResponseDataset(observations=rich + other + newcomer)
        )
        model = models["CAMPAIGN-NEW"]

        self.assertEqual(model.diagnostics.support, ResponseSupport.POOLED_TRANSFER)
        self.assertTrue(model.is_usable)
        self.assertEqual(model.campaign_id, "CAMPAIGN-NEW")
        self.assertIn("CAMPAIGN-RICH", model.diagnostics.pooled_campaign_ids)

    def test_pooled_transfer_is_not_labelled_target_history(self) -> None:
        """A borrowed estimate never claims to be observed behavior."""

        rich = _dataset(campaign_id="CAMPAIGN-RICH").observations
        other = _dataset(campaign_id="CAMPAIGN-OTHER").observations
        newcomer = (_observation(campaign_id="CAMPAIGN-NEW", day=1),)
        models = fit_campaign_response_models(
            CampaignResponseDataset(observations=rich + other + newcomer)
        )

        self.assertNotEqual(
            models["CAMPAIGN-NEW"].diagnostics.support,
            ResponseSupport.TARGET_HISTORY,
        )

    def test_incomparable_campaign_gets_no_pooled_transfer(self) -> None:
        """Pooling requires comparable decision-time context."""

        rich = _dataset(campaign_id="CAMPAIGN-RICH").observations
        other = _dataset(campaign_id="CAMPAIGN-OTHER").observations
        newcomer = (
            _observation(
                campaign_id="CAMPAIGN-DSP", day=1, ad_product="AMAZON_DSP"
            ),
        )
        models = fit_campaign_response_models(
            CampaignResponseDataset(observations=rich + other + newcomer)
        )

        self.assertEqual(
            models["CAMPAIGN-DSP"].diagnostics.support,
            ResponseSupport.INSUFFICIENT_SUPPORT,
        )


class ExtrapolationTest(unittest.TestCase):
    """Predictions outside observed evidence must be flagged."""

    def test_budget_inside_observed_range_is_not_extrapolated(self) -> None:
        """A budget the Campaign has actually run is interpolation."""

        model = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]

        self.assertFalse(model.is_extrapolating(100.0))

    def test_budget_outside_observed_range_is_extrapolated(self) -> None:
        """A budget far above anything observed is flagged."""

        model = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]

        self.assertTrue(model.is_extrapolating(1000.0))
        self.assertTrue(model.is_extrapolating(1.0))

    def test_observed_ranges_are_reported(self) -> None:
        """Both observed budget and spend ranges accompany the model."""

        diagnostics = fit_campaign_response_models(_dataset())[
            "CAMPAIGN-1"
        ].diagnostics

        self.assertEqual(diagnostics.observed_budget_range, (40.0, 200.0))
        self.assertLess(
            diagnostics.observed_spend_range[0],
            diagnostics.observed_spend_range[1],
        )


class SerializationTest(unittest.TestCase):
    """Model artifacts must round-trip without loss."""

    def test_model_round_trips_through_dict(self) -> None:
        """A serialized model rebuilds to identical predictions."""

        model = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]
        rebuilt = CampaignResponseModel.from_dict(model.to_dict())

        self.assertEqual(rebuilt.to_dict(), model.to_dict())
        self.assertAlmostEqual(
            rebuilt.expected_revenue(120.0), model.expected_revenue(120.0)
        )

    def test_model_round_trips_through_text(self) -> None:
        """Text serialization is stable and reversible."""

        model = fit_campaign_response_models(_dataset())["CAMPAIGN-1"]

        self.assertEqual(
            CampaignResponseModel.from_str(model.to_str()).to_str(),
            model.to_str(),
        )

    def test_artifact_carries_required_identity(self) -> None:
        """The artifact records what it is and what evidence produced it."""

        payload = fit_campaign_response_models(_dataset())["CAMPAIGN-1"].to_dict()

        self.assertEqual(payload["model_version"], MODEL_VERSION)
        self.assertEqual(payload["campaign_id"], "CAMPAIGN-1")
        self.assertIn("model_id", payload)
        self.assertIn("diagnostics", payload)
        self.assertIn("observed_budget_range", payload["diagnostics"])

    def test_model_collection_round_trips(self) -> None:
        """Every fitted Campaign survives one serialization cycle."""

        models = fit_campaign_response_models(_dataset())
        rebuilt = response_models_from_dict(response_models_to_dict(models))

        self.assertEqual(set(rebuilt), set(models))
        self.assertEqual(
            rebuilt["CAMPAIGN-1"].to_dict(), models["CAMPAIGN-1"].to_dict()
        )

    def test_unsupported_model_round_trips(self) -> None:
        """An insufficient-support model serializes without inventing curves."""

        dataset = CampaignResponseDataset(observations=(_observation(),))
        model = fit_campaign_response_models(dataset)["CAMPAIGN-1"]
        rebuilt = CampaignResponseModel.from_dict(model.to_dict())

        self.assertFalse(rebuilt.is_usable)
        self.assertIsNone(rebuilt.spend_response)
        self.assertIsNone(rebuilt.revenue_response)


if __name__ == "__main__":
    unittest.main()
