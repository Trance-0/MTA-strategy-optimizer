"""Tests for the Campaign-level constrained budget optimizer.

Covers both budget usage policies, every constraint the solver must respect,
the equal-marginal condition an interior concave solution satisfies, and the
structured refusals that must appear instead of a fabricated optimum.

These are tests of mathematical correctness and constraint handling. They do
not compare the optimizer's policy against the simulator's oracle, which is
out of scope for this stage.
"""

from __future__ import annotations

import unittest

from modules.mta_common.src.budget import BudgetConstraints
from modules.mta_common.src.enums import BudgetUsagePolicy, StrategyObjective
from modules.mta_strategy_recommendation.src.budget_optimizer import (
    AD_GROUP_OPTIMIZATION_CLAIM,
    AD_GROUP_PROJECTION_BASIS,
    CampaignBudgetRequest,
    optimize_campaign_budgets,
)
from modules.mta_strategy_recommendation.src.response_model import (
    CampaignResponseModel,
    ResponseDiagnostics,
    ResponseSupport,
    RevenueResponse,
    SpendResponse,
)


def _model(
    campaign_id: str,
    alpha: float = 900.0,
    kappa: float = 90.0,
    support: ResponseSupport = ResponseSupport.TARGET_HISTORY,
    observed_range: tuple[float, float] = (40.0, 200.0),
) -> CampaignResponseModel:
    """Build a usable response model with known concave parameters."""

    return CampaignResponseModel(
        campaign_id=campaign_id,
        currency="USD",
        spend_response=SpendResponse(capacity=1000.0, scale=1000.0),
        revenue_response=RevenueResponse(baseline=50.0, alpha=alpha, kappa=kappa),
        diagnostics=ResponseDiagnostics(
            support=support,
            observation_count=8,
            intervention_count=8,
            distinct_budget_count=5,
            observed_budget_range=observed_range,
            observed_spend_range=(30.0, 180.0),
        ),
    )


def _unusable(campaign_id: str) -> CampaignResponseModel:
    """Build a model that cannot justify an optimized budget."""

    return CampaignResponseModel(
        campaign_id=campaign_id,
        currency="USD",
        spend_response=None,
        revenue_response=None,
        diagnostics=ResponseDiagnostics(
            support=ResponseSupport.INSUFFICIENT_SUPPORT, observation_count=1
        ),
    )


def _request(
    campaign_id: str,
    initial_budget: float = 100.0,
    minimum: float | None = None,
    maximum: float | None = None,
    is_active: bool = True,
    policy: BudgetUsagePolicy = BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
    currency: str = "USD",
) -> CampaignBudgetRequest:
    return CampaignBudgetRequest(
        campaign_id=campaign_id,
        constraints=BudgetConstraints(
            campaign_id=campaign_id,
            budget_usage_policy=policy,
            minimum_daily_budget=minimum,
            maximum_daily_budget=maximum,
        ),
        initial_budget=initial_budget,
        currency=currency,
        is_active=is_active,
        current_budget=initial_budget,
    )


class BudgetUsagePolicyTest(unittest.TestCase):
    """Both usage policies must be honored exactly."""

    def test_spend_full_budget_allocates_the_whole_authorized_total(self) -> None:
        """An equality policy exhausts the authorized budget."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B")],
            response_models={"A": _model("A"), "B": _model("B", alpha=600.0)},
            total_budget=300.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
        )

        self.assertTrue(plan.is_optimized)
        self.assertAlmostEqual(plan.allocated_budget, 300.0, places=4)

    def test_spend_up_to_budget_never_exceeds_the_authorized_total(self) -> None:
        """An inequality policy may leave budget unallocated."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B")],
            response_models={"A": _model("A"), "B": _model("B")},
            total_budget=300.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
        )

        self.assertTrue(plan.is_optimized)
        self.assertLessEqual(plan.allocated_budget, 300.0 + 1e-4)

    def test_up_to_budget_leaves_remainder_when_returns_are_exhausted(self) -> None:
        """Budget beyond useful spend is not forced out the door."""

        plan = optimize_campaign_budgets(
            requests=[_request("A", maximum=120.0)],
            response_models={"A": _model("A")},
            total_budget=10_000.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_UP_TO_BUDGET,
        )

        self.assertTrue(plan.is_optimized)
        self.assertLess(plan.allocated_budget, 10_000.0)


class ConstraintTest(unittest.TestCase):
    """Every Campaign bound must hold in the returned allocation."""

    def test_minimum_budgets_are_respected(self) -> None:
        """A Campaign never falls below its floor."""

        plan = optimize_campaign_budgets(
            requests=[_request("A", minimum=150.0), _request("B")],
            response_models={"A": _model("A", alpha=100.0), "B": _model("B")},
            total_budget=300.0,
        )
        allocations = {item.campaign_id: item for item in plan.allocations}

        self.assertTrue(plan.is_optimized)
        self.assertGreaterEqual(allocations["A"].optimized_budget, 150.0 - 1e-6)

    def test_maximum_budgets_are_respected(self) -> None:
        """A Campaign never exceeds its ceiling."""

        plan = optimize_campaign_budgets(
            requests=[_request("A", maximum=80.0), _request("B")],
            response_models={"A": _model("A", alpha=5000.0), "B": _model("B")},
            total_budget=400.0,
        )
        allocations = {item.campaign_id: item for item in plan.allocations}

        self.assertTrue(plan.is_optimized)
        self.assertLessEqual(allocations["A"].optimized_budget, 80.0 + 1e-6)

    def test_inactive_campaigns_are_excluded(self) -> None:
        """A paused Campaign receives no allocation."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B", is_active=False)],
            response_models={"A": _model("A"), "B": _model("B")},
            total_budget=200.0,
        )

        self.assertTrue(plan.is_optimized)
        self.assertEqual({item.campaign_id for item in plan.allocations}, {"A"})
        self.assertIn("B", plan.excluded_campaign_ids)

    def test_infeasible_minimum_budgets_are_rejected(self) -> None:
        """Floors above the authorized total cannot be satisfied."""

        plan = optimize_campaign_budgets(
            requests=[_request("A", minimum=200.0), _request("B", minimum=200.0)],
            response_models={"A": _model("A"), "B": _model("B")},
            total_budget=300.0,
        )

        self.assertFalse(plan.is_optimized)
        self.assertEqual(plan.recommendation_type, "INFEASIBLE_CONSTRAINTS")
        self.assertTrue(plan.infeasibility_reasons)

    def test_full_budget_infeasible_against_maximums(self) -> None:
        """Ceilings below the authorized total break an equality policy."""

        plan = optimize_campaign_budgets(
            requests=[_request("A", maximum=50.0), _request("B", maximum=50.0)],
            response_models={"A": _model("A"), "B": _model("B")},
            total_budget=300.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
        )

        self.assertFalse(plan.is_optimized)
        self.assertEqual(plan.recommendation_type, "INFEASIBLE_CONSTRAINTS")

    def test_mixed_currencies_are_rejected(self) -> None:
        """Budgets in different currencies are not comparable."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B", currency="EUR")],
            response_models={"A": _model("A"), "B": _model("B")},
            total_budget=300.0,
        )

        self.assertFalse(plan.is_optimized)
        self.assertEqual(plan.recommendation_type, "INFEASIBLE_REQUEST")

    def test_duplicate_campaign_identifiers_are_rejected(self) -> None:
        """One Campaign cannot appear twice in one allocation."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("A")],
            response_models={"A": _model("A")},
            total_budget=300.0,
        )

        self.assertFalse(plan.is_optimized)
        self.assertEqual(plan.recommendation_type, "INFEASIBLE_REQUEST")

    def test_negative_total_budget_is_rejected(self) -> None:
        """A negative authorized budget is structurally invalid."""

        plan = optimize_campaign_budgets(
            requests=[_request("A")],
            response_models={"A": _model("A")},
            total_budget=-1.0,
        )

        self.assertFalse(plan.is_optimized)


class SupportRequirementTest(unittest.TestCase):
    """Optimization requires response evidence, never attribution."""

    def test_campaign_without_response_support_is_excluded(self) -> None:
        """An unsupported Campaign cannot be optimized."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B")],
            response_models={"A": _model("A"), "B": _unusable("B")},
            total_budget=200.0,
        )

        self.assertTrue(plan.is_optimized)
        self.assertIn("B", plan.excluded_campaign_ids)
        self.assertEqual({item.campaign_id for item in plan.allocations}, {"A"})

    def test_no_supported_campaign_produces_no_optimum(self) -> None:
        """With no usable model the optimizer refuses rather than guesses."""

        plan = optimize_campaign_budgets(
            requests=[_request("A")],
            response_models={"A": _unusable("A")},
            total_budget=200.0,
        )

        self.assertFalse(plan.is_optimized)
        self.assertEqual(
            plan.recommendation_type, "NO_SUPPORTED_CAMPAIGN_RESPONSE"
        )
        self.assertEqual(plan.allocations, ())

    def test_missing_response_model_is_treated_as_unsupported(self) -> None:
        """A Campaign with no fitted model is excluded, not assumed."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B")],
            response_models={"A": _model("A")},
            total_budget=200.0,
        )

        self.assertIn("B", plan.excluded_campaign_ids)

    def test_pooled_transfer_support_is_reported_on_the_allocation(self) -> None:
        """A borrowed estimate stays labelled through to the output."""

        plan = optimize_campaign_budgets(
            requests=[_request("A")],
            response_models={
                "A": _model("A", support=ResponseSupport.POOLED_TRANSFER)
            },
            total_budget=200.0,
        )

        self.assertEqual(
            plan.allocations[0].response_support, ResponseSupport.POOLED_TRANSFER
        )


class OptimalityTest(unittest.TestCase):
    """An interior concave solution equalizes marginal expected revenue."""

    def test_interior_solution_equalizes_marginal_revenue(self) -> None:
        """Unconstrained Campaigns end at nearly equal marginal returns."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B"), _request("C")],
            response_models={
                "A": _model("A", alpha=900.0, kappa=90.0),
                "B": _model("B", alpha=1400.0, kappa=120.0),
                "C": _model("C", alpha=600.0, kappa=70.0),
            },
            total_budget=300.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
        )
        marginals = [item.marginal_expected_revenue for item in plan.allocations]

        self.assertTrue(plan.is_optimized)
        self.assertAlmostEqual(max(marginals), min(marginals), places=3)

    def test_higher_return_campaign_receives_more_budget(self) -> None:
        """Budget flows toward the more responsive Campaign."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B")],
            response_models={
                "A": _model("A", alpha=2000.0, kappa=100.0),
                "B": _model("B", alpha=300.0, kappa=100.0),
            },
            total_budget=300.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
        )
        allocations = {item.campaign_id: item for item in plan.allocations}

        self.assertGreater(
            allocations["A"].optimized_budget, allocations["B"].optimized_budget
        )

    def test_optimized_revenue_is_not_below_an_even_split(self) -> None:
        """The solver never does worse than the split it replaces."""

        requests = [_request("A", initial_budget=150.0), _request("B", initial_budget=150.0)]
        models = {
            "A": _model("A", alpha=2000.0, kappa=100.0),
            "B": _model("B", alpha=300.0, kappa=100.0),
        }
        plan = optimize_campaign_budgets(
            requests=requests,
            response_models=models,
            total_budget=300.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
        )

        self.assertGreaterEqual(
            plan.expected_optimized_revenue, plan.expected_initial_revenue - 1e-6
        )
        self.assertGreaterEqual(plan.expected_revenue_increase, -1e-6)

    def test_solution_is_deterministic(self) -> None:
        """Identical inputs produce an identical allocation."""

        def solve():
            return optimize_campaign_budgets(
                requests=[_request("A"), _request("B")],
                response_models={"A": _model("A"), "B": _model("B", alpha=500.0)},
                total_budget=250.0,
                budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
            )

        self.assertEqual(solve().to_dict(), solve().to_dict())


class ProfitObjectiveTest(unittest.TestCase):
    """Profit must not be silently reinterpreted as revenue."""

    def test_profit_objective_returns_unsupported(self) -> None:
        """A revenue model cannot answer a profit question."""

        plan = optimize_campaign_budgets(
            requests=[_request("A")],
            response_models={"A": _model("A")},
            total_budget=200.0,
            objective=StrategyObjective.MAXIMIZE_PROFIT,
        )

        self.assertFalse(plan.is_optimized)
        self.assertEqual(
            plan.recommendation_type, "PROFIT_OBJECTIVE_NOT_MODELED"
        )
        self.assertEqual(plan.objective, StrategyObjective.MAXIMIZE_PROFIT)


class OutputContractTest(unittest.TestCase):
    """The reported plan must carry the evidence a reader needs."""

    def test_allocation_reports_every_required_field(self) -> None:
        """Each Campaign's budget, spend, revenue, and support are present."""

        plan = optimize_campaign_budgets(
            requests=[_request("A")],
            response_models={"A": _model("A")},
            total_budget=200.0,
        )
        payload = plan.allocations[0].to_dict()

        for key in (
            "campaign_id",
            "current_budget",
            "initial_budget",
            "optimized_budget",
            "expected_spend_at_initial",
            "expected_spend_at_optimized",
            "expected_revenue_at_initial",
            "expected_revenue_at_optimized",
            "expected_revenue_delta",
            "marginal_expected_revenue",
            "response_support",
            "observed_budget_range",
            "observed_spend_range",
            "is_extrapolated",
            "model_version",
        ):
            self.assertIn(key, payload)

    def test_group_totals_decompose_into_campaign_deltas(self) -> None:
        """The group increase is the sum of Campaign increases."""

        plan = optimize_campaign_budgets(
            requests=[_request("A"), _request("B"), _request("C")],
            response_models={
                "A": _model("A"),
                "B": _model("B", alpha=500.0),
                "C": _model("C", alpha=1500.0),
            },
            total_budget=400.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
        )
        summed = sum(item.expected_revenue_delta for item in plan.allocations)

        self.assertAlmostEqual(plan.expected_revenue_increase, summed, places=4)

    def test_extrapolation_is_flagged_on_the_allocation(self) -> None:
        """A budget outside observed evidence is marked as extrapolated."""

        plan = optimize_campaign_budgets(
            requests=[_request("A", minimum=900.0)],
            response_models={"A": _model("A", observed_range=(40.0, 200.0))},
            total_budget=1000.0,
        )

        self.assertTrue(plan.allocations[0].is_extrapolated)

    def test_plan_does_not_claim_ad_group_optimization(self) -> None:
        """Any split below Campaign is labelled a projection."""

        plan = optimize_campaign_budgets(
            requests=[_request("A")],
            response_models={"A": _model("A")},
            total_budget=200.0,
        )

        self.assertEqual(
            plan.ad_group_projection_basis, AD_GROUP_PROJECTION_BASIS
        )
        self.assertEqual(
            plan.ad_group_optimization_claim, AD_GROUP_OPTIMIZATION_CLAIM
        )
        self.assertEqual(plan.ad_group_optimization_claim, "NOT_AD_GROUP_OPTIMIZED")

    def test_optimized_plan_is_never_labelled_initial_seed(self) -> None:
        """The optimizer's result is distinct from the initializer's."""

        plan = optimize_campaign_budgets(
            requests=[_request("A")],
            response_models={"A": _model("A")},
            total_budget=200.0,
        )

        self.assertEqual(plan.recommendation_type, "OPTIMIZED_CAMPAIGN_BUDGET")
        self.assertNotEqual(plan.recommendation_type, "INITIAL_SEED")

    def test_failed_plan_reports_is_optimized_false(self) -> None:
        """A refusal never presents itself as an optimized result."""

        plan = optimize_campaign_budgets(
            requests=[],
            response_models={},
            total_budget=200.0,
        )

        self.assertFalse(plan.is_optimized)
        self.assertEqual(plan.allocations, ())
        self.assertTrue(plan.infeasibility_reasons)


if __name__ == "__main__":
    unittest.main()
