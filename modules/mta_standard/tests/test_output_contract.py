"""Tests for the standard output row and its validation.

Covers the standard invariants and the zero-outcome rule, asserting that every
registered model satisfies the contract and that each individual violation is
rejected with a specific message.
"""

from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path

from modules.mta_standard.src.dataloader import load_mta_sim_dataset
from modules.mta_standard.src.model_registry import MODEL_REGISTRY, build_model
from modules.mta_standard.src.output_contract import (
    STANDARD_OUTPUT_FIELDS,
    SUPPORTED_OUTCOMES,
    ZERO_OUTCOME_WARNING,
    StandardAttributionRow,
    standard_rows_to_dicts,
    validate_standard_output,
)
from modules.mta_standard.src.touchpoint_adapter import SimulatorConfig
from modules.mta_standard.tests import mta_sim_fixtures as fixtures


ZERO_OUTCOME_PATHS = (
    (f"{fixtures.DISPLAY} > {fixtures.SEARCH}", 100, 0, 0, "0.00"),
    (fixtures.BRAND, 40, 0, 0, "0.00"),
)


class OutputContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mta_sim_")
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self.paths = fixtures.write_dataset(self.directory)
        self.config = SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES)
        self.dataset = load_mta_sim_dataset(
            self.paths["path_report"], self.paths["ads_performance"], config=self.config
        )
        self.rows = (
            build_model("markov_removal_effect").fit(self.dataset).attribute(self.dataset)
        )

    def replace(self, index: int, **changes) -> list[StandardAttributionRow]:
        rows = list(self.rows)
        rows[index] = dataclasses.replace(rows[index], **changes)
        return rows


class SchemaTest(OutputContractTestCase):
    def test_row_renders_every_standard_field(self) -> None:
        rendered = self.rows[0].as_dict()
        self.assertEqual(tuple(rendered), STANDARD_OUTPUT_FIELDS)
        self.assertEqual(rendered["valid"], "true")
        self.assertEqual(rendered["warnings"], "")

    def test_warnings_are_pipe_joined(self) -> None:
        row = dataclasses.replace(self.rows[0], warnings=("A", "B"))
        self.assertEqual(row.as_dict()["warnings"], "A|B")

    def test_rows_render_in_bulk(self) -> None:
        rendered = standard_rows_to_dicts(self.rows)
        self.assertEqual(len(rendered), len(self.rows))
        self.assertTrue(all(tuple(row) == STANDARD_OUTPUT_FIELDS for row in rendered))

    def test_scope_and_identity_are_stamped_on_every_row(self) -> None:
        for row in self.rows:
            self.assertEqual(row.model_id, "markov_removal_effect")
            self.assertEqual(row.model_version, "1.0.0")
            self.assertEqual(row.report_start_date, fixtures.REPORT_START)
            self.assertEqual(row.report_end_date, fixtures.REPORT_END)
            self.assertEqual(row.marketplace, fixtures.MARKETPLACE)


class ValidationTest(OutputContractTestCase):
    def test_every_registered_model_passes(self) -> None:
        for model_id in MODEL_REGISTRY:
            with self.subTest(model_id=model_id):
                rows = build_model(model_id).fit(self.dataset).attribute(self.dataset)
                summary = validate_standard_output(
                    rows,
                    outcome_totals=self.dataset.outcome_totals,
                    expected_touchpoints=self.dataset.touchpoints,
                )
                self.assertEqual(summary["row_count"], 9)
                self.assertEqual(summary["group_count"], len(SUPPORTED_OUTCOMES))

    def test_empty_output_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one row"):
            validate_standard_output([], outcome_totals=self.dataset.outcome_totals)

    def test_negative_share_is_rejected(self) -> None:
        rows = self.replace(0, attribution_share=-0.1)
        with self.assertRaisesRegex(ValueError, "attribution_share must be non-negative"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_negative_value_is_rejected(self) -> None:
        rows = self.replace(0, attributed_value=-1.0)
        with self.assertRaisesRegex(ValueError, "attributed_value must be non-negative"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_non_finite_share_is_rejected(self) -> None:
        rows = self.replace(0, attribution_share=float("inf"))
        with self.assertRaisesRegex(ValueError, "must be finite"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_duplicate_row_identity_is_rejected(self) -> None:
        rows = [*self.rows, self.rows[0]]
        with self.assertRaisesRegex(ValueError, "duplicate standard row identity"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_share_conservation_is_enforced(self) -> None:
        rows = self.replace(0, attribution_share=self.rows[0].attribution_share + 0.05)
        with self.assertRaisesRegex(ValueError, "shares must sum to 1.0"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_outcome_conservation_is_enforced(self) -> None:
        rows = self.replace(0, attributed_value=self.rows[0].attributed_value + 1.0)
        with self.assertRaisesRegex(ValueError, "must sum to the observed total"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_non_canonical_touchpoint_is_rejected(self) -> None:
        rows = self.replace(
            0,
            touchpoint=f"{fixtures.DISPLAY}:IMPRESSION".lower(),
        )
        with self.assertRaisesRegex(ValueError, "canonical five-segment key"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_four_segment_touchpoint_is_rejected(self) -> None:
        rows = self.replace(0, touchpoint=fixtures.DISPLAY)
        with self.assertRaises(ValueError):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_unknown_outcome_is_rejected(self) -> None:
        rows = self.replace(0, outcome="clicks")
        with self.assertRaisesRegex(ValueError, "outcome must be one of"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_repeated_warning_is_rejected(self) -> None:
        rows = self.replace(0, warnings=("A", "A"))
        with self.assertRaisesRegex(ValueError, "warnings must not repeat"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_missing_outcome_total_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing outcome"):
            validate_standard_output(self.rows, outcome_totals={"revenue": 1.0})

    def test_unexpected_touchpoint_set_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "touchpoint set differs"):
            validate_standard_output(
                self.rows,
                outcome_totals=self.dataset.outcome_totals,
                expected_touchpoints=(f"{fixtures.SEARCH}:CLICK",),
            )


class ZeroOutcomeTest(unittest.TestCase):
    """A zero observed outcome must stay zero rather than being redistributed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mta_sim_")
        self.addCleanup(self._tmp.cleanup)
        directory = Path(self._tmp.name)
        config = SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES)
        self.dataset = load_mta_sim_dataset(
            fixtures.write_path_report(directory, rows=ZERO_OUTCOME_PATHS),
            config=config,
        )
        self.rows = (
            build_model("markov_removal_effect").fit(self.dataset).attribute(self.dataset)
        )

    def test_all_outcome_totals_are_zero(self) -> None:
        self.assertEqual(
            dict(self.dataset.outcome_totals),
            {"converted_users": 0.0, "purchase_count": 0.0, "revenue": 0.0},
        )

    def test_shares_and_values_are_zero_and_warned(self) -> None:
        for row in self.rows:
            self.assertEqual(row.attribution_share, 0.0)
            self.assertEqual(row.attributed_value, 0.0)
            self.assertEqual(row.warnings, (ZERO_OUTCOME_WARNING,))
        validate_standard_output(self.rows, outcome_totals=self.dataset.outcome_totals)

    def test_missing_zero_outcome_warning_is_rejected(self) -> None:
        rows = list(self.rows)
        rows[0] = dataclasses.replace(rows[0], warnings=())
        with self.assertRaisesRegex(ValueError, ZERO_OUTCOME_WARNING):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)

    def test_redistributed_share_is_rejected(self) -> None:
        rows = list(self.rows)
        rows[0] = dataclasses.replace(rows[0], attribution_share=1.0)
        with self.assertRaisesRegex(ValueError, "shares must sum to 0.0"):
            validate_standard_output(rows, outcome_totals=self.dataset.outcome_totals)


if __name__ == "__main__":
    unittest.main()
