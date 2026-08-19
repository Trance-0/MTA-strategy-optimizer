"""Integration tests for the pinned ZheyuanWu generator adapter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUBMODULE_ROOT = PROJECT_ROOT / "external" / "mta_sim_dataset"

from modules.mta_standard.src.evaluation import load_simulation_ground_truth
from modules.mta_standard.src.mta_sim_generator_adapter import (
    _simulator_config,
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
            # The toy fixture declares two Touchpoints, each able to realize an
            # IMPRESSION and a CLICK, so the observed five-segment keys are a
            # subset of four and must cover both configured Touchpoints.
            self.assertGreaterEqual(len(generated.dataset.touchpoints), 2)
            self.assertLessEqual(len(generated.dataset.touchpoints), 4)
            self.assertEqual(
                {key.split(":", 1)[0] for key in generated.dataset.touchpoints},
                {"AMAZON_DSP", "SPONSORED_PRODUCTS"},
            )
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
                generated.ground_truth,
                scope=generated.dataset.scope,
                config=generated.simulator_config,
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

    def test_provider_capabilities_are_forwarded_for_current_configs(self) -> None:
        """A synthetic Provider must not receive Amazon's default profile."""

        provider = object()
        capabilities = SimpleNamespace(provider=provider)

        class CurrentTouchpoint:
            identifier = "limited-display"
            cost_per_click = None
            cost_per_thousand_impressions = 10.0

            def __init__(self, provider_value):
                self.provider = provider_value

            def normalized_key(self, interaction, supplied_capabilities):
                self.last_capabilities = supplied_capabilities
                return f"DISPLAY:IMAGE:UNSPECIFIED:UNSPECIFIED:{interaction}"

        touchpoint = CurrentTouchpoint(provider)
        configuration = SimpleNamespace(
            touchpoints=(touchpoint,),
            provider_capabilities=(capabilities,),
        )
        adapted = _simulator_config(configuration)
        self.assertIs(touchpoint.last_capabilities, capabilities)
        self.assertEqual(
            adapted.cost_type_by_touchpoint[
                "DISPLAY:IMAGE:UNSPECIFIED:UNSPECIFIED"
            ],
            "CPM",
        )


if __name__ == "__main__":
    unittest.main()
