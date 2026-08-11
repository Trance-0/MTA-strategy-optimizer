"""Tests for framework-only orchestration of registered attribution models."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.mta_standard.src.dataloader import load_mta_sim_dataset
from modules.mta_standard.src.model_pipeline import run_registered_models
from modules.mta_standard.src.touchpoint_adapter import SimulatorConfig
from modules.mta_standard.tests import mta_sim_fixtures as fixtures


class ModelPipelineTests(unittest.TestCase):
    """Verify orchestration without depending on a concrete model internally."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        paths = fixtures.write_dataset(root)
        self.dataset = load_mta_sim_dataset(
            paths["path_report"],
            paths["ads_performance"],
            config=SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES),
        )

    def test_runs_independently_registered_models(self) -> None:
        runs = run_registered_models(
            self.dataset,
            ("markov_removal_effect", "path_level_shapley", "uniform_credit"),
        )
        self.assertEqual(
            tuple(runs),
            ("markov_removal_effect", "path_level_shapley", "uniform_credit"),
        )
        self.assertTrue(all(run.rows for run in runs.values()))

    def test_rejects_empty_or_duplicate_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            run_registered_models(self.dataset, ())
        with self.assertRaisesRegex(ValueError, "distinct"):
            run_registered_models(self.dataset, ("uniform_credit", "uniform_credit"))


if __name__ == "__main__":
    unittest.main()
