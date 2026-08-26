"""End-to-end test over real MTA-SIM output, not hand-built fixtures.

Generates a dataset with the pinned simulator, adapts its research snapshot
into Campaign episodes, builds the response dataset, fits response models, and
optimizes Campaign budgets. This is what proves the file contract between the
two repositories actually holds.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from modules.mta_common.src.budget import BudgetConstraints
from modules.mta_common.src.enums import BudgetUsagePolicy
from modules.mta_standard.src.mta_sim_research_adapter import (
    load_mta_sim_research_snapshot,
)
from modules.mta_strategy_recommendation.src.budget_optimizer import (
    CampaignBudgetRequest,
    optimize_campaign_budgets,
)
from modules.mta_strategy_recommendation.src.episode_bridge import (
    campaign_episodes_from_research_snapshot,
)
from modules.mta_strategy_recommendation.src.response_dataset import (
    build_campaign_response_dataset,
)
from modules.mta_strategy_recommendation.src.response_model import (
    ResponseSupport,
    fit_campaign_response_models,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUBMODULE_ROOT = PROJECT_ROOT / "external" / "mta_sim_dataset"

# This suite runs the vendored MTA-SIM simulator to produce its fixture, so a
# checkout without that submodule has nothing to generate from. Skipped rather
# than failed for the same reason as in
# `modules/mta_standard/tests/test_mta_sim_generator_adapter.py`: the absence
# of a separate repository is not a defect in this one.
SUBMODULE_AVAILABLE = (SUBMODULE_ROOT / "ZheyuanWu" / "simulations").is_dir()


def _generate_snapshot(directory: Path, display_budget: float = 6.0) -> Path:
    """Run the pinned simulator over a small intervention configuration."""

    import subprocess
    import sys

    zheyuanwu = SUBMODULE_ROOT / "ZheyuanWu"
    payload = json.loads(
        (zheyuanwu / "examples" / "baseline.toy.json").read_text(encoding="utf-8")
    )
    payload["report_start_date"] = "2026-01-01"
    payload["report_end_date"] = "2026-01-20"
    payload["campaigns"] = [
        {
            "campaign_id": "CAMPAIGN-SEARCH",
            "campaign_name": "Search Campaign",
            "ad_product": "SPONSORED_PRODUCTS",
            "status": "ACTIVE",
            "baseline_daily_budget": 60.0,
            "touchpoint_identifiers": ["search_ad"],
        },
        {
            "campaign_id": "CAMPAIGN-DISPLAY",
            "campaign_name": "Display Campaign",
            "ad_product": "AMAZON_DSP",
            "status": "ACTIVE",
            # Below the display Touchpoint's cost-per-mille capacity of 10.0,
            # so this Campaign's budget genuinely binds and its spend varies.
            "baseline_daily_budget": display_budget,
            "touchpoint_identifiers": ["display_ad"],
        },
    ]
    payload["budget_experiment"] = {
        "multipliers": [0.5, 0.75, 1.0, 1.25, 1.5],
        "spend_capacity_multiplier": 1.0,
        "saturation_spend": 50.0,
        "assignment_type": "SCHEDULED",
    }
    configuration = directory / "intervention.json"
    configuration.write_text(json.dumps(payload), encoding="utf-8")

    output = directory / "generated"
    subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-B",
            "-m",
            "simulations.baseline.mta_dataset",
            "--config",
            str(configuration),
            "--output",
            str(output),
            "--storage",
            "csv",
        ],
        cwd=zheyuanwu,
        check=True,
        capture_output=True,
    )
    return output / "simulation_research.json"


@unittest.skipUnless(
    SUBMODULE_AVAILABLE,
    f"the MTA-SIM submodule is not checked out at {SUBMODULE_ROOT}",
)
class ResponsePipelineTest(unittest.TestCase):
    """The simulator's file contract must carry a learnable budget response."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        path = _generate_snapshot(Path(cls._directory.name))
        cls.snapshot = load_mta_sim_research_snapshot(path)
        cls.episodes = campaign_episodes_from_research_snapshot(cls.snapshot)
        cls.dataset = build_campaign_response_dataset(cls.episodes)
        cls.models = fit_campaign_response_models(cls.dataset)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_snapshot_carries_intervention_metadata(self) -> None:
        """The adapter reads the simulator's own assignment metadata."""

        budgets = self.snapshot.budget_observations

        self.assertTrue(budgets)
        for item in budgets:
            self.assertIsNotNone(item.intervention_id)
            self.assertIsNotNone(item.baseline_budget)
            self.assertIsNotNone(item.assignment_type)

    def test_episodes_compose_one_period_per_campaign(self) -> None:
        """Each Campaign-period becomes exactly one response observation."""

        keys = [item.period_key for item in self.dataset]

        self.assertTrue(keys)
        self.assertEqual(len(keys), len(set(keys)))

    def test_dataset_shows_real_budget_variation(self) -> None:
        """Scheduled assignment produces varied budgets to learn from."""

        budgets = {item.configured_budget for item in self.dataset}

        self.assertGreater(len(budgets), 2)

    def test_spend_never_exceeds_configured_budget(self) -> None:
        """The generated world respects the budget it was given."""

        for item in self.dataset:
            self.assertLessEqual(item.actual_spend, item.configured_budget + 1e-6)

    def test_campaigns_fit_from_their_own_history(self) -> None:
        """Both Campaigns have enough variation for a target-history fit."""

        for campaign_id in ("CAMPAIGN-SEARCH", "CAMPAIGN-DISPLAY"):
            with self.subTest(campaign=campaign_id):
                model = self.models[campaign_id]

                self.assertEqual(
                    model.diagnostics.support, ResponseSupport.TARGET_HISTORY
                )
                self.assertTrue(model.is_usable)

    def test_fitted_response_is_monotone_and_concave(self) -> None:
        """Learned curves keep the shape the optimizer depends on."""

        model = self.models["CAMPAIGN-SEARCH"]
        budgets = [20.0, 40.0, 60.0, 80.0, 100.0]
        revenues = [model.expected_revenue(item) for item in budgets]
        marginals = [model.marginal_expected_revenue(item) for item in budgets]

        for first, second in zip(revenues, revenues[1:]):
            self.assertGreaterEqual(second, first - 1e-9)
        for first, second in zip(marginals, marginals[1:]):
            self.assertLessEqual(second, first + 1e-9)

    def test_optimizer_produces_a_validated_plan(self) -> None:
        """The full chain ends in an optimized, constraint-respecting plan."""

        requests = [
            CampaignBudgetRequest(
                campaign_id=campaign_id,
                constraints=BudgetConstraints(
                    campaign_id=campaign_id,
                    budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
                    minimum_daily_budget=10.0,
                    maximum_daily_budget=150.0,
                ),
                initial_budget=50.0,
                currency="USD",
                current_budget=50.0,
            )
            for campaign_id in ("CAMPAIGN-SEARCH", "CAMPAIGN-DISPLAY")
        ]
        plan = optimize_campaign_budgets(
            requests=requests,
            response_models=self.models,
            total_budget=100.0,
            budget_usage_policy=BudgetUsagePolicy.SPEND_FULL_BUDGET,
        )

        self.assertTrue(plan.is_optimized)
        self.assertAlmostEqual(plan.allocated_budget, 100.0, places=3)
        self.assertEqual(len(plan.allocations), 2)
        self.assertGreaterEqual(plan.expected_revenue_increase, -1e-6)

    def test_no_evaluation_truth_reaches_the_response_dataset(self) -> None:
        """Evaluation-only outcomes stay out of the model-facing rows."""

        self.assertTrue(self.snapshot.evaluation_outcome_observations)
        for episode in self.episodes:
            for outcome in episode.outcome_observations:
                self.assertIsNone(outcome.incremental_revenue)
                self.assertIsNone(outcome.expected_organic_revenue)

    def test_attribution_is_absent_from_every_episode(self) -> None:
        """The response path never needs attribution evidence."""

        for episode in self.episodes:
            self.assertEqual(episode.attribution_evidence, ())

    def test_a_campaign_whose_budget_never_binds_is_unsupported(self) -> None:
        """Constant spend across budgets cannot teach a budget response.

        A Campaign budgeted far above what its Touchpoints can absorb spends
        the same amount at every level, so its history says nothing about how
        spend would respond to a budget change. The model must report
        insufficient support rather than fit a curve to a vertical line.
        """

        directory = tempfile.TemporaryDirectory()
        try:
            path = _generate_snapshot(Path(directory.name), display_budget=40.0)
            dataset = build_campaign_response_dataset(
                campaign_episodes_from_research_snapshot(
                    load_mta_sim_research_snapshot(path)
                )
            )
            rows = dataset.for_campaign("CAMPAIGN-DISPLAY")
            models = fit_campaign_response_models(dataset)

            self.assertGreater(len({item.configured_budget for item in rows}), 2)
            self.assertEqual(len({item.actual_spend for item in rows}), 1)
            self.assertEqual(
                models["CAMPAIGN-DISPLAY"].diagnostics.support,
                ResponseSupport.INSUFFICIENT_SUPPORT,
            )
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
