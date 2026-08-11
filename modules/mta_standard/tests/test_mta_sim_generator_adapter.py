"""Integration tests for the pinned ZheyuanWu generator adapter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUBMODULE_ROOT = PROJECT_ROOT / "external" / "mta_sim_dataset"

from modules.mta_standard.src.evaluation import load_simulation_ground_truth
from modules.mta_standard.src.mta_sim_generator_adapter import (
    generate_and_load_mta_sim_dataset,
)


class MtaSimGeneratorAdapterTests(unittest.TestCase):
    """Verify real submodule generation and local contract adaptation."""

    def test_generates_and_loads_baseline_toy_dataset(self) -> None:
        """Generate the public toy fixture and keep ground truth evaluation-only."""

        configuration = (
            SUBMODULE_ROOT / "ZheyuanWu" / "examples" / "baseline.toy.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            generated = generate_and_load_mta_sim_dataset(
                submodule_root=SUBMODULE_ROOT,
                configuration_path=configuration,
                output_directory=directory,
            )

            self.assertEqual(
                generated.manifest["repository_url"],
                "https://github.com/Trance-0/MTA-SIM-dataset",
            )
            self.assertTrue(generated.path_report.is_file())
            self.assertTrue(generated.performance_report.is_file())
            self.assertTrue(generated.ground_truth.is_file())
            self.assertGreater(len(generated.dataset.path_rows), 0)
            self.assertGreater(len(generated.dataset.ads_rows), 0)
            self.assertEqual(len(generated.dataset.touchpoints), 2)
            self.assertFalse(hasattr(generated.dataset, "ground_truth"))
            self.assertEqual(
                set(generated.simulator_config.cost_type_by_touchpoint.values()),
                {"CPC", "CPM"},
            )
            self.assertEqual(
                {key.rsplit(":", 1)[-1] for key in generated.dataset.five_segment_touchpoints()},
                {"CLICK", "IMPRESSION"},
            )
            ground_truth = load_simulation_ground_truth(
                generated.ground_truth, scope=generated.dataset.scope
            )
            self.assertEqual(
                set(ground_truth.touchpoints), set(generated.dataset.touchpoints)
            )

    def test_rejects_an_uninitialized_submodule(self) -> None:
        """Explain how to initialize the submodule when its checkout is absent."""

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "submodule update"):
                generate_and_load_mta_sim_dataset(
                    submodule_root=directory,
                    configuration_path=Path(directory) / "missing.json",
                    output_directory=Path(directory) / "output",
                )


if __name__ == "__main__":
    unittest.main()
