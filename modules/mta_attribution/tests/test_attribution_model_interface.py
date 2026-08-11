"""Tests for the standardized model interface and its wrappers.

The central regression test lives here: the Markov and Shapley wrappers must
produce values bit-identical to a direct call on the underlying estimators, and
pinned fixture values catch a change in the mathematics itself.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.mta_attribution.src.attribution_model_comparison import OUTCOME_FIELDS
from modules.mta_attribution.src.attribution_model_interface import MtaAttributionModel
from modules.mta_attribution.src.markov_attribution_model import run_markov_attribution
from modules.mta_attribution.src.markov_standard_attribution_model import (
    MarkovRemovalEffectModel,
)
from modules.mta_attribution.src.shapley_attribution_model import (
    run_shapley_attribution,
)
from modules.mta_attribution.src.shapley_standard_attribution_model import (
    PathLevelShapleyModel,
)
from modules.mta_attribution.src.uniform_attribution_model import UniformCreditModel
from modules.mta_standard.src.dataloader import load_mta_sim_dataset
from modules.mta_standard.src.model_registry import MODEL_REGISTRY, build_model
from modules.mta_standard.src.output_contract import (
    SUPPORTED_OUTCOMES,
    validate_standard_output,
)
from modules.mta_standard.src.touchpoint_adapter import SimulatorConfig, to_four_segment
from modules.mta_standard.tests import mta_sim_fixtures as fixtures


# Pinned expected shares. These are the values the existing five-segment
# estimators produce for the fixture, recorded at the four-segment grain so a
# change to Markov or Shapley mathematics fails here rather than silently
# altering published attribution.
EXPECTED_MARKOV_CONVERTED_USER_SHARES = {
    fixtures.DISPLAY: 0.36666666666666664,
    fixtures.BRAND: 0.1666666666666667,
    fixtures.SEARCH: 0.46666666666666673,
}
EXPECTED_SHAPLEY_CONVERTED_USERS = {
    fixtures.DISPLAY: 27.5,
    fixtures.BRAND: 12.5,
    fixtures.SEARCH: 45.0,
}


class ModelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mta_sim_")
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self.paths = fixtures.write_dataset(self.directory)
        self.config = SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES)
        self.dataset = load_mta_sim_dataset(
            self.paths["path_report"], self.paths["ads_performance"], config=self.config
        )


class InterfaceTest(ModelTestCase):
    def test_every_registered_model_implements_the_interface(self) -> None:
        for model_id, model_class in MODEL_REGISTRY.items():
            with self.subTest(model_id=model_id):
                self.assertTrue(issubclass(model_class, MtaAttributionModel))
                self.assertEqual(model_class.model_id, model_id)
                self.assertTrue(model_class.model_version)
                self.assertEqual(
                    model_class.capabilities.supported_outcomes, SUPPORTED_OUTCOMES
                )
                self.assertEqual(
                    model_class.capabilities.grain, "four_segment_touchpoint"
                )

    def test_build_model_returns_an_unfitted_instance(self) -> None:
        model = build_model("markov_removal_effect")
        self.assertIsInstance(model, MarkovRemovalEffectModel)
        self.assertIsNone(model.fitted_scope)

    def test_build_model_rejects_unknown_identifier(self) -> None:
        with self.assertRaises(KeyError):
            build_model("no_such_model")

    def test_fit_records_the_report_scope(self) -> None:
        model = MarkovRemovalEffectModel()
        self.assertIs(model.fit(self.dataset), model)
        self.assertEqual(model.fitted_scope["marketplace"], fixtures.MARKETPLACE)

    def test_every_model_emits_four_segment_touchpoints(self) -> None:
        for model_id in MODEL_REGISTRY:
            with self.subTest(model_id=model_id):
                rows = build_model(model_id).fit(self.dataset).attribute(self.dataset)
                self.assertTrue(rows)
                for row in rows:
                    self.assertEqual(len(row.touchpoint.split(":")), 4)
                    self.assertIn(row.outcome, SUPPORTED_OUTCOMES)


class WrappedAlgorithmRegressionTest(ModelTestCase):
    """The wrappers must relabel results without changing any number."""

    def _standard_shares(self, model: MtaAttributionModel) -> dict:
        rows = model.fit(self.dataset).attribute(self.dataset)
        return {(row.touchpoint, row.outcome): row for row in rows}

    def test_markov_matches_a_direct_call_exactly(self) -> None:
        standard = self._standard_shares(MarkovRemovalEffectModel())
        for result in run_markov_attribution(list(self.dataset.path_rows)):
            four = to_four_segment(result.touchpoint)
            for outcome in SUPPORTED_OUTCOMES:
                share_field, value_field = OUTCOME_FIELDS[outcome]
                row = standard[(four, outcome)]
                with self.subTest(touchpoint=four, outcome=outcome):
                    self.assertEqual(
                        row.attribution_share, getattr(result, share_field)
                    )
                    self.assertEqual(
                        row.attributed_value, getattr(result, value_field)
                    )

    def test_shapley_matches_a_direct_call_exactly(self) -> None:
        standard = self._standard_shares(PathLevelShapleyModel())
        for result in run_shapley_attribution(list(self.dataset.path_rows)):
            four = to_four_segment(result.touchpoint)
            for outcome in SUPPORTED_OUTCOMES:
                share_field, value_field = OUTCOME_FIELDS[outcome]
                row = standard[(four, outcome)]
                with self.subTest(touchpoint=four, outcome=outcome):
                    self.assertEqual(
                        row.attribution_share, getattr(result, share_field)
                    )
                    self.assertEqual(
                        row.attributed_value, getattr(result, value_field)
                    )

    def test_markov_shares_match_the_pinned_values(self) -> None:
        standard = self._standard_shares(MarkovRemovalEffectModel())
        for touchpoint, share in EXPECTED_MARKOV_CONVERTED_USER_SHARES.items():
            with self.subTest(touchpoint=touchpoint):
                self.assertEqual(
                    standard[(touchpoint, "converted_users")].attribution_share, share
                )

    def test_shapley_values_match_the_pinned_values(self) -> None:
        standard = self._standard_shares(PathLevelShapleyModel())
        for touchpoint, value in EXPECTED_SHAPLEY_CONVERTED_USERS.items():
            with self.subTest(touchpoint=touchpoint):
                self.assertEqual(
                    standard[(touchpoint, "converted_users")].attributed_value, value
                )

    def test_repeated_runs_are_byte_identical(self) -> None:
        for model_id in MODEL_REGISTRY:
            with self.subTest(model_id=model_id):
                first = build_model(model_id).fit(self.dataset).attribute(self.dataset)
                second = build_model(model_id).fit(self.dataset).attribute(self.dataset)
                self.assertEqual(first, second)


class PersistenceTest(ModelTestCase):
    def test_round_trip_preserves_identity_and_scope(self) -> None:
        model = MarkovRemovalEffectModel().fit(self.dataset)
        destination = model.save(self.directory / "markov.json")
        restored = MarkovRemovalEffectModel.load(destination)
        self.assertEqual(restored.model_id, model.model_id)
        self.assertEqual(restored.fitted_scope, model.fitted_scope)
        self.assertEqual(restored.attribute(self.dataset), model.attribute(self.dataset))

    def test_loading_another_model_file_is_rejected(self) -> None:
        destination = PathLevelShapleyModel().fit(self.dataset).save(
            self.directory / "shapley.json"
        )
        with self.assertRaisesRegex(ValueError, "expected markov_removal_effect"):
            MarkovRemovalEffectModel.load(destination)

    def test_unsupported_persistence_raises_not_implemented(self) -> None:
        self.assertFalse(UniformCreditModel.capabilities.supports_persistence)
        with self.assertRaises(NotImplementedError):
            UniformCreditModel().save(self.directory / "uniform.json")
        with self.assertRaises(NotImplementedError):
            UniformCreditModel.load(self.directory / "uniform.json")


class PluggableModelTest(ModelTestCase):
    """A model sharing no code with the wrapped estimators must still fit in."""

    def test_uniform_model_requires_fit(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires fit"):
            UniformCreditModel().attribute(self.dataset)

    def test_uniform_model_rejects_a_different_scope(self) -> None:
        other_directory = self.directory / "other"
        other = load_mta_sim_dataset(
            fixtures.write_path_report(other_directory, marketplace="UK"),
            config=self.config,
        )
        self.assertNotEqual(other.scope, self.dataset.scope)
        model = UniformCreditModel().fit(self.dataset)
        with self.assertRaisesRegex(RuntimeError, "different report scope"):
            model.attribute(other)

    def test_uniform_model_satisfies_the_standard_contract(self) -> None:
        rows = UniformCreditModel().fit(self.dataset).attribute(self.dataset)
        summary = validate_standard_output(
            rows,
            outcome_totals=self.dataset.outcome_totals,
            expected_touchpoints=self.dataset.touchpoints,
        )
        self.assertEqual(summary["row_count"], 9)
        self.assertEqual(summary["group_count"], len(SUPPORTED_OUTCOMES))

    def test_uniform_model_splits_each_outcome_equally(self) -> None:
        rows = UniformCreditModel().fit(self.dataset).attribute(self.dataset)
        revenue = [row for row in rows if row.outcome == "revenue"]
        self.assertEqual(sum(row.attributed_value for row in revenue), 10500.0)
        self.assertEqual({row.attributed_value for row in revenue}, {3500.0})


if __name__ == "__main__":
    unittest.main()
