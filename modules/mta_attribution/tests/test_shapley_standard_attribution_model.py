"""Tests for the independently packaged standardized Shapley model."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.mta_attribution.src.shapley_standard_attribution_model import (
    PathLevelShapleyModel,
)
from modules.mta_standard.src.dataloader import load_mta_sim_dataset
from modules.mta_standard.src.output_contract import validate_standard_output
from modules.mta_standard.src.touchpoint_adapter import SimulatorConfig
from modules.mta_standard.tests import mta_sim_fixtures as fixtures


class ShapleyStandardAttributionModelTests(unittest.TestCase):
    """Verify the Shapley model through only its public standard contract."""

    def test_emits_valid_standard_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = fixtures.write_dataset(Path(directory))
            dataset = load_mta_sim_dataset(
                paths["path_report"],
                paths["ads_performance"],
                config=SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES),
            )
            rows = PathLevelShapleyModel().attribute(dataset)
            validate_standard_output(rows, outcome_totals=dataset.outcome_totals)


if __name__ == "__main__":
    unittest.main()
