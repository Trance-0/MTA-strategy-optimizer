"""Tests for the readers that project committed artifacts into StrategyOutput.

Projects both artifacts this repository actually commits and asserts each
conserves, then covers the refusals: a plan the optimizer declined, an artifact
with no currency supplied, and a file that is not there.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from modules.mta_strategy_evaluation.src.strategy_output import (
    ALLOCATION_TYPE_INITIAL_SEED,
    ALLOCATION_TYPE_OPTIMIZED,
)
from modules.mta_strategy_evaluation.src.strategy_projection import (
    CAMPAIGN_STRATEGY_ARTIFACT,
    INITIAL_BUDGET_ARTIFACT,
    STRATEGY_ID_CAMPAIGN_RESPONSE_OPTIMIZER,
    STRATEGY_ID_DETERMINISTIC_SEED,
    UNRECORDED_ADVERTISER,
    StrategyProjectionError,
    load_strategy_outputs,
    strategy_output_from_campaign_strategy,
    strategy_output_from_initial_budget,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
STRATEGY_OUTPUT_DIR = REPO_ROOT / "modules" / "mta_strategy_recommendation" / "outputs"


def _document(name: str) -> dict:
    return json.loads((STRATEGY_OUTPUT_DIR / name).read_text(encoding="utf-8"))


class CommittedArtifactTest(unittest.TestCase):
    """Both committed artifacts project and conserve."""

    def test_initial_budget_artifact_projects_and_conserves(self) -> None:
        """The deterministic seed reads into a conserving allocation."""

        output = strategy_output_from_initial_budget(
            _document(INITIAL_BUDGET_ARTIFACT), currency="USD"
        )
        report = output.conservation()

        self.assertEqual(output.strategy_id, STRATEGY_ID_DETERMINISTIC_SEED)
        self.assertEqual(output.allocation_type, ALLOCATION_TYPE_INITIAL_SEED)
        self.assertTrue(report.is_conserving, report.violations)

    def test_the_seed_keeps_its_ad_group_slots(self) -> None:
        """This is the only artifact where constraints (1) and (3) bite."""

        output = strategy_output_from_initial_budget(
            _document(INITIAL_BUDGET_ARTIFACT), currency="USD"
        )

        self.assertTrue(any(decision.ad_groups for decision in output.campaigns))

    def test_the_seed_records_that_attribution_informed_it(self) -> None:
        """An Initial Strategy may use attribution, and says so."""

        output = strategy_output_from_initial_budget(
            _document(INITIAL_BUDGET_ARTIFACT), currency="USD"
        )

        self.assertTrue(output.uses_attribution)

    def test_campaign_strategy_artifact_projects_and_conserves(self) -> None:
        """The optimized plan reads into a conserving allocation."""

        output = strategy_output_from_campaign_strategy(
            _document(CAMPAIGN_STRATEGY_ARTIFACT)
        )
        report = output.conservation()

        self.assertEqual(
            output.strategy_id, STRATEGY_ID_CAMPAIGN_RESPONSE_OPTIMIZER
        )
        self.assertEqual(output.allocation_type, ALLOCATION_TYPE_OPTIMIZED)
        self.assertTrue(report.is_conserving, report.violations)

    def test_the_optimizer_does_not_use_attribution(self) -> None:
        """It fits response curves; attribution is never one of its inputs."""

        output = strategy_output_from_campaign_strategy(
            _document(CAMPAIGN_STRATEGY_ARTIFACT)
        )

        self.assertFalse(output.uses_attribution)

    def test_the_optimizer_invents_no_ad_group_slots(self) -> None:
        """It claims NOT_AD_GROUP_OPTIMIZED, so its slots stay empty."""

        output = strategy_output_from_campaign_strategy(
            _document(CAMPAIGN_STRATEGY_ARTIFACT)
        )

        self.assertTrue(all(not row.ad_groups for row in output.campaigns))

    def test_unrecorded_advertiser_is_a_visible_sentinel(self) -> None:
        """The artifact records no advertiser, so the default is not an id."""

        output = strategy_output_from_campaign_strategy(
            _document(CAMPAIGN_STRATEGY_ARTIFACT)
        )

        self.assertEqual(output.scope.advertiser_id, UNRECORDED_ADVERTISER)

    def test_campaign_order_follows_the_artifact(self) -> None:
        """Never alphabetical, matching how the backend reassembles them."""

        document = _document(CAMPAIGN_STRATEGY_ARTIFACT)
        output = strategy_output_from_campaign_strategy(document)

        self.assertEqual(
            [row.campaign_id for row in output.campaigns],
            [
                str(row["campaign_id"])
                for row in document["optimized_strategy"]["allocations"]
            ],
        )


class RefusalTest(unittest.TestCase):
    """A refusal is reported with its reason, never scored as a zero."""

    def test_a_plan_the_optimizer_declined_raises_with_its_reasons(self) -> None:
        """An unoptimized plan names its own infeasibility reasons."""

        with self.assertRaises(StrategyProjectionError) as raised:
            strategy_output_from_campaign_strategy(
                {
                    "optimized_strategy": {
                        "is_optimized": False,
                        "infeasibility_reasons": ["NO_RESPONSE_SUPPORT"],
                    }
                }
            )

        self.assertIn("NO_RESPONSE_SUPPORT", str(raised.exception))

    def test_an_empty_document_raises(self) -> None:
        """Nothing to project is not an allocation of nothing."""

        with self.assertRaises(StrategyProjectionError):
            strategy_output_from_campaign_strategy({})
        with self.assertRaises(StrategyProjectionError):
            strategy_output_from_initial_budget({}, currency="USD")

    def test_an_optimized_plan_without_observations_raises(self) -> None:
        """Marketplace and window are recoverable only from observations."""

        with self.assertRaises(StrategyProjectionError):
            strategy_output_from_campaign_strategy(
                {
                    "optimized_strategy": {
                        "is_optimized": True,
                        "allocations": [
                            {"campaign_id": "C-1", "optimized_budget": 10.0}
                        ],
                        "allocated_budget": 10.0,
                    }
                }
            )

    def test_a_seed_without_a_reporting_window_raises(self) -> None:
        """A decision that cannot be scoped cannot be scored."""

        with self.assertRaises(StrategyProjectionError):
            strategy_output_from_initial_budget(
                {"campaigns": [{"campaign_id": "C-1", "budget_seed_share": 1.0}]},
                currency="USD",
            )


class LoadStrategyOutputsTest(unittest.TestCase):
    """Every artifact yields an attempt, including the ones that failed."""

    def test_both_artifacts_project_when_a_currency_is_supplied(self) -> None:
        """The committed directory yields two successful attempts."""

        attempts = load_strategy_outputs(STRATEGY_OUTPUT_DIR, currency="USD")

        self.assertEqual(len(attempts), 2)
        for attempt in attempts:
            with self.subTest(artifact=attempt.artifact):
                self.assertTrue(attempt.succeeded, attempt.error)

    def test_attempts_are_in_pipeline_order(self) -> None:
        """The seed first, then the optimized plan."""

        attempts = load_strategy_outputs(STRATEGY_OUTPUT_DIR, currency="USD")

        self.assertEqual(
            [attempt.artifact for attempt in attempts],
            [INITIAL_BUDGET_ARTIFACT, CAMPAIGN_STRATEGY_ARTIFACT],
        )

    def test_a_missing_currency_skips_the_seed_with_its_reason(self) -> None:
        """The reader will not guess a currency, and says why it stopped."""

        attempts = load_strategy_outputs(STRATEGY_OUTPUT_DIR)
        seed = attempts[0]

        self.assertFalse(seed.succeeded)
        self.assertIn("currency", seed.error)
        self.assertTrue(attempts[1].succeeded, attempts[1].error)

    def test_a_missing_file_is_an_attempt_rather_than_an_omission(self) -> None:
        """An artifact that has not been produced is reported, not dropped."""

        attempts = load_strategy_outputs(REPO_ROOT / "does-not-exist", currency="USD")

        self.assertEqual(len(attempts), 2)
        for attempt in attempts:
            with self.subTest(artifact=attempt.artifact):
                self.assertFalse(attempt.succeeded)
                self.assertIn("does not exist", attempt.error)


if __name__ == "__main__":
    unittest.main()
