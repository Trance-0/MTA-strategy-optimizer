"""Command contract tests for the strategy evaluation pipeline stage."""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from script import evaluate_strategies


PROJECT_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_STRATEGIES = (
    PROJECT_ROOT / "modules" / "mta_strategy_recommendation" / "outputs"
)


class EvaluateStrategiesCommandTests(unittest.TestCase):
    """Exercise command output, refusal handling, and optional fitting."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.strategies = self.root / "strategies"
        self.strategies.mkdir()
        for name in (
            "initial_budget_recommendation.json",
            "campaign_strategy.json",
        ):
            shutil.copyfile(COMMITTED_STRATEGIES / name, self.strategies / name)
        self.output = self.root / "strategy_evaluation.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run(self, *extra: str) -> tuple[int, str]:
        argv = [
            "evaluate_strategies.py",
            "--strategy-directory",
            str(self.strategies),
            "--output",
            str(self.output),
            *extra,
        ]
        stdout = io.StringIO()
        with patch.object(sys, "argv", argv), redirect_stdout(stdout):
            status = evaluate_strategies.main()
        return status, stdout.getvalue()

    def test_writes_two_deterministic_evaluations_and_all_phases(self) -> None:
        status, stdout = self._run()

        self.assertEqual(status, 0)
        phases = (
            "Projecting strategies",
            "Checking conservation",
            "Comparing against baselines",
            "Fitting the contributed model",
            "Writing the artifact",
        )
        offsets = [stdout.index(phase) for phase in phases]
        self.assertEqual(offsets, sorted(offsets))

        text = self.output.read_text(encoding="utf-8")
        artifact = json.loads(text)
        self.assertEqual(
            text,
            json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        )
        self.assertEqual(artifact["summary"]["projected"], 2)
        self.assertEqual(artifact["summary"]["conserved"], 2)
        self.assertEqual(artifact["summary"]["skipped"], [])
        self.assertEqual(artifact["contributed_models"], [])
        self.assertEqual(
            [item["strategy_id"] for item in artifact["strategies"]],
            ["deterministic_budget_seed", "campaign_response_optimizer"],
        )
        self.assertFalse(
            artifact["strategies"][0]["baseline_comparison"]["was_run"]
        )
        self.assertIn(
            "C_DEMO_SP",
            artifact["strategies"][0]["baseline_comparison"]["reason"],
        )
        self.assertTrue(
            artifact["strategies"][1]["baseline_comparison"]["was_run"]
        )
        self.assertFalse(artifact["strategies"][1]["ground_truth"]["was_run"])

    def test_returns_one_only_when_no_strategy_projects(self) -> None:
        for path in self.strategies.iterdir():
            path.unlink()

        status, _ = self._run()

        self.assertEqual(status, 1)
        artifact = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(artifact["summary"]["projected"], 0)
        self.assertEqual(len(artifact["summary"]["skipped"]), 2)
        self.assertTrue(
            all(item["reasons"] for item in artifact["summary"]["skipped"])
        )

    def test_optimizer_refusal_is_skipped_with_its_own_reason(self) -> None:
        path = self.strategies / "campaign_strategy.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["optimized_strategy"]["is_optimized"] = False
        document["optimized_strategy"]["infeasibility_reasons"] = [
            "authorized budget is below the minimum"
        ]
        path.write_text(json.dumps(document), encoding="utf-8")

        status, _ = self._run()

        self.assertEqual(status, 0)
        artifact = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(artifact["summary"]["projected"], 1)
        refusal = artifact["summary"]["skipped"][0]
        self.assertEqual(refusal["strategy_id"], "campaign_response_optimizer")
        self.assertIn("below the minimum", refusal["reasons"][0])

    def test_missing_optional_stack_is_reported_with_install_remedy(self) -> None:
        with patch.object(
            evaluate_strategies.importlib.util, "find_spec", return_value=None
        ), patch.object(evaluate_strategies, "contributed_model_report") as report:
            status, _ = self._run("--fit-contributed-model")

        self.assertEqual(status, 0)
        report.assert_not_called()
        artifact = json.loads(self.output.read_text(encoding="utf-8"))
        report = artifact["contributed_models"][0]
        self.assertFalse(report["available"])
        self.assertEqual(report["remedy"], "uv sync --extra strategy-evaluation")

    def test_response_rows_build_the_contributed_dataset(self) -> None:
        episodes = evaluate_strategies._load_observed_episodes(
            self.strategies, None
        )
        dataset = evaluate_strategies.build_campaign_response_dataset(episodes)

        self.assertEqual(len(episodes), 40)
        self.assertEqual(len(dataset), 40)
        self.assertEqual(
            dataset.campaign_ids, ("CAMPAIGN-DISPLAY", "CAMPAIGN-SEARCH")
        )


if __name__ == "__main__":
    unittest.main()
