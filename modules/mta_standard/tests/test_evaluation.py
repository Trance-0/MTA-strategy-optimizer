"""Tests for ground-truth loading and model evaluation.

Covers both ground-truth grains, the aggregate-and-renormalise rule, metric
bounds, determinism across runs, and the structural checks proving ground truth
is unreachable from any model entry point.
"""

from __future__ import annotations

import csv
import dataclasses
import inspect
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

import mta_sim_fixtures as fixtures  # noqa: E402
from dataloader import load_mta_sim_dataset  # noqa: E402
from evaluation import (  # noqa: E402
    MTA_SIM_GROUND_TRUTH_FIELDS,
    GroundTruth,
    compare_models,
    evaluate_model,
    evaluate_standard_output,
    load_simulation_ground_truth,
)
from model_registry import MODEL_REGISTRY, build_model  # noqa: E402
from output_contract import (  # noqa: E402
    SUPPORTED_OUTCOMES,
    StandardAttributionRow,
)
from touchpoint_adapter import SimulatorConfig  # noqa: E402


class EvaluationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mta_sim_")
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self.paths = fixtures.write_dataset(self.directory)
        self.config = SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES)
        self.dataset = load_mta_sim_dataset(
            self.paths["path_report"], self.paths["ads_performance"], config=self.config
        )
        self.ground_truth = load_simulation_ground_truth(
            self.paths["ground_truth"], scope=self.dataset.scope
        )


class GroundTruthLoadingTest(EvaluationTestCase):
    def test_normalised_table_is_loaded_unchanged(self) -> None:
        self.assertEqual(self.ground_truth.row_count, 3)
        self.assertEqual(
            dict(self.ground_truth.credit_share),
            {fixtures.DISPLAY: 0.30, fixtures.SEARCH: 0.50, fixtures.BRAND: 0.20},
        )

    def test_path_grain_table_is_aggregated_and_renormalised(self) -> None:
        path = fixtures.write_ground_truth(
            self.directory / "per_path", per_path=True
        )
        truth = load_simulation_ground_truth(path, scope=self.dataset.scope)
        self.assertEqual(truth.row_count, 7)
        self.assertAlmostEqual(sum(truth.credit_share.values()), 1.0, places=12)
        # DISPLAY 0.30 + 0.10 of a 1.50 total.
        self.assertAlmostEqual(truth.credit_share[fixtures.DISPLAY], 0.4 / 1.5, places=12)
        self.assertAlmostEqual(truth.credit_share[fixtures.SEARCH], 0.9 / 1.5, places=12)
        self.assertAlmostEqual(truth.credit_share[fixtures.BRAND], 0.2 / 1.5, places=12)

    def test_causal_increment_is_summed_but_not_normalised(self) -> None:
        self.assertAlmostEqual(
            self.ground_truth.causal_increment[fixtures.SEARCH], 0.20, places=12
        )

    def test_touchpoints_are_four_segment(self) -> None:
        for touchpoint in self.ground_truth.touchpoints:
            self.assertEqual(len(touchpoint.split(":")), 4)

    def test_missing_file_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_simulation_ground_truth(self.directory / "absent.csv")

    def test_unexpected_header_is_rejected(self) -> None:
        target = self.directory / "bad_header.csv"
        with target.open("w", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(MTA_SIM_GROUND_TRUTH_FIELDS[:-1])
            writer.writerow(["x"] * (len(MTA_SIM_GROUND_TRUTH_FIELDS) - 1))
        with self.assertRaisesRegex(ValueError, "header must exactly match"):
            load_simulation_ground_truth(target)

    def test_scope_mismatch_is_rejected(self) -> None:
        other = load_mta_sim_dataset(
            fixtures.write_path_report(self.directory / "uk", marketplace="UK"),
            config=self.config,
        )
        with self.assertRaisesRegex(ValueError, "does not match dataset scope"):
            load_simulation_ground_truth(self.paths["ground_truth"], scope=other.scope)


class GroundTruthIsolationTest(EvaluationTestCase):
    """Ground truth must be reachable only through the evaluation API."""

    def test_evaluation_owns_the_only_ground_truth_loader(self) -> None:
        import dataloader

        loaders = [
            name
            for name in dir(dataloader)
            if name.startswith("load") and "ground_truth" in name.lower()
        ]
        self.assertEqual(loaders, [])
        self.assertTrue(callable(load_simulation_ground_truth))

    def test_no_model_entry_point_accepts_ground_truth(self) -> None:
        for model_id, model_class in MODEL_REGISTRY.items():
            for method in ("fit", "attribute"):
                with self.subTest(model_id=model_id, method=method):
                    parameters = set(
                        inspect.signature(getattr(model_class, method)).parameters
                    )
                    self.assertEqual(parameters, {"self", "dataset"})

    def test_attribution_never_sees_ground_truth_values(self) -> None:
        rows = build_model("markov_removal_effect").fit(self.dataset).attribute(
            self.dataset
        )
        truth_values = set(self.ground_truth.credit_share.values())
        self.assertFalse(
            truth_values & {row.attribution_share for row in rows},
            "attribution shares must not reproduce ground-truth credit shares",
        )


class MetricsTest(EvaluationTestCase):
    def test_every_registered_model_can_be_evaluated(self) -> None:
        for model_id in MODEL_REGISTRY:
            with self.subTest(model_id=model_id):
                report = evaluate_model(
                    build_model(model_id), self.dataset, self.ground_truth
                )
                self.assertEqual(report.model_id, model_id)
                self.assertEqual(set(report.metrics), set(SUPPORTED_OUTCOMES))
                self.assertGreaterEqual(report.runtime_seconds, 0.0)
                self.assertEqual(report.missing_in_model, ())
                self.assertEqual(report.missing_in_ground_truth, ())

    def test_metrics_are_within_their_definitional_bounds(self) -> None:
        report = evaluate_model(
            build_model("path_level_shapley"), self.dataset, self.ground_truth
        )
        for outcome, metrics in report.metrics.items():
            with self.subTest(outcome=outcome):
                self.assertEqual(metrics.touchpoint_count, 3)
                self.assertEqual(metrics.top_k, 3)
                self.assertGreaterEqual(metrics.credit_share_mae, 0.0)
                self.assertGreaterEqual(
                    metrics.credit_share_rmse, metrics.credit_share_mae
                )
                self.assertGreaterEqual(metrics.total_variation_distance, 0.0)
                self.assertLessEqual(metrics.total_variation_distance, 1.0)
                self.assertGreaterEqual(metrics.top_k_overlap, 0.0)
                self.assertLessEqual(metrics.top_k_overlap, 1.0)
                self.assertLess(metrics.conservation_error, 1e-9)

    def test_a_perfect_model_scores_perfectly(self) -> None:
        rows = [
            StandardAttributionRow(
                model_id="oracle",
                model_version="1.0.0",
                report_start_date=self.dataset.scope.report_start_date,
                report_end_date=self.dataset.scope.report_end_date,
                marketplace=self.dataset.scope.marketplace,
                touchpoint=touchpoint,
                outcome=outcome,
                attribution_share=share,
                attributed_value=share * self.dataset.outcome_totals[outcome],
            )
            for touchpoint, share in self.ground_truth.credit_share.items()
            for outcome in SUPPORTED_OUTCOMES
        ]
        report = evaluate_standard_output(rows, self.dataset, self.ground_truth)
        for outcome, metrics in report.metrics.items():
            with self.subTest(outcome=outcome):
                self.assertAlmostEqual(metrics.credit_share_mae, 0.0, places=12)
                self.assertAlmostEqual(metrics.credit_share_rmse, 0.0, places=12)
                self.assertAlmostEqual(metrics.total_variation_distance, 0.0, places=12)
                self.assertAlmostEqual(metrics.spearman_rho, 1.0, places=12)
                self.assertEqual(metrics.top_k_overlap, 1.0)

    def test_metrics_are_deterministic_across_runs(self) -> None:
        first = evaluate_model(
            build_model("markov_removal_effect"), self.dataset, self.ground_truth
        )
        second = evaluate_model(
            build_model("markov_removal_effect"), self.dataset, self.ground_truth
        )
        self.assertEqual(dict(first.metrics), dict(second.metrics))

    def test_missing_touchpoints_are_reported_and_penalised(self) -> None:
        model_rows = [
            row
            for row in build_model("path_level_shapley")
            .fit(self.dataset)
            .attribute(self.dataset)
            if row.touchpoint != fixtures.BRAND
        ]
        # Re-conserve the remaining rows so the contract check still passes and
        # the metrics, not the validator, register the omission.
        rebalanced = []
        for outcome in SUPPORTED_OUTCOMES:
            group = [row for row in model_rows if row.outcome == outcome]
            share_total = sum(row.attribution_share for row in group)
            value_total = self.dataset.outcome_totals[outcome]
            shares = [row.attribution_share / share_total for row in group]
            values = [share * value_total for share in shares]
            # The last row absorbs the residual so both sums conserve exactly.
            shares[-1] = 1.0 - sum(shares[:-1])
            values[-1] = value_total - sum(values[:-1])
            for row, share, value in zip(group, shares, values):
                rebalanced.append(
                    dataclasses.replace(
                        row, attribution_share=share, attributed_value=value
                    )
                )
        report = evaluate_standard_output(rebalanced, self.dataset, self.ground_truth)
        self.assertEqual(report.missing_in_model, (fixtures.BRAND,))
        self.assertEqual(report.missing_in_ground_truth, ())
        for metrics in report.metrics.values():
            self.assertEqual(metrics.touchpoint_count, 3)
            self.assertGreater(metrics.credit_share_mae, 0.0)

    def test_top_k_is_capped_by_the_touchpoint_count(self) -> None:
        report = evaluate_model(
            build_model("uniform_credit"), self.dataset, self.ground_truth, top_k=99
        )
        for metrics in report.metrics.values():
            self.assertEqual(metrics.top_k, 3)

    def test_non_positive_top_k_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "top_k must be a positive integer"):
            evaluate_model(
                build_model("uniform_credit"), self.dataset, self.ground_truth, top_k=0
            )

    def test_mixed_model_versions_are_rejected(self) -> None:
        markov = build_model("markov_removal_effect").fit(self.dataset).attribute(
            self.dataset
        )
        shapley = build_model("path_level_shapley").fit(self.dataset).attribute(
            self.dataset
        )
        with self.assertRaisesRegex(ValueError, "exactly one model version"):
            evaluate_standard_output(
                [*markov, *shapley], self.dataset, self.ground_truth
            )

    def test_ground_truth_scope_mismatch_is_rejected(self) -> None:
        mismatched = GroundTruth(
            report_start_date="2025-01-01",
            report_end_date=self.ground_truth.report_end_date,
            marketplace=self.ground_truth.marketplace,
            credit_share=self.ground_truth.credit_share,
            causal_increment=self.ground_truth.causal_increment,
            row_count=self.ground_truth.row_count,
        )
        with self.assertRaisesRegex(ValueError, "does not match the dataset scope"):
            evaluate_model(
                build_model("uniform_credit"), self.dataset, mismatched
            )


class ComparisonTest(EvaluationTestCase):
    def test_models_are_compared_under_identical_conditions(self) -> None:
        reports = compare_models(
            [build_model(model_id) for model_id in sorted(MODEL_REGISTRY)],
            self.dataset,
            self.ground_truth,
        )
        self.assertEqual(
            [report.model_id for report in reports], sorted(MODEL_REGISTRY)
        )
        for report in reports:
            self.assertEqual(report.scope, self.dataset.scope)
            self.assertEqual(set(report.metrics), set(SUPPORTED_OUTCOMES))


if __name__ == "__main__":
    unittest.main()
