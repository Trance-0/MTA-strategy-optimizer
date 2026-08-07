"""Tests for the DNN credit model.

Covers feature derivation, the reserved unknown bucket that makes new-campaign
prediction possible, convergence towards the Shapley training target, bit-identical
determinism, weight persistence, and the zero-outcome rule.
"""

from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from attribution_src_path import ensure_attribution_src_on_path  # noqa: E402

ensure_attribution_src_on_path()

import mta_sim_fixtures as fixtures  # noqa: E402
from dataloader import load_mta_sim_dataset  # noqa: E402
from shapley_attribution_model import run_shapley_attribution  # noqa: E402
from dnn_attribution_model import (  # noqa: E402
    NUMERIC_FEATURE_NAMES,
    SEGMENT_NAMES,
    DeepNeuralAttributionModel,
    _FeatureEncoder,
    build_touchpoint_features,
)
from attribution_model_comparison import OUTCOME_FIELDS  # noqa: E402
from model_registry import MODEL_REGISTRY, build_model  # noqa: E402
from output_contract import (  # noqa: E402
    SUPPORTED_OUTCOMES,
    ZERO_OUTCOME_WARNING,
    validate_standard_output,
)
from touchpoint_adapter import SimulatorConfig, to_four_segment  # noqa: E402


NEW_CAMPAIGN = (
    "SPONSORED_PRODUCTS:PRODUCT_AD:REST_OF_SEARCH:UNSPECIFIED",
    "AMAZON_DSP:DISPLAY:UNSPECIFIED:IMAGE",
)
ZERO_OUTCOME_PATHS = (
    (f"{fixtures.DISPLAY} > {fixtures.SEARCH}", 100, 0, 0, "0.00"),
    (fixtures.BRAND, 40, 0, 0, "0.00"),
)


class DnnTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mta_sim_")
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        self.paths = fixtures.write_dataset(self.directory)
        self.config = SimulatorConfig.from_mapping(fixtures.SIMULATOR_COST_TYPES)
        self.dataset = load_mta_sim_dataset(
            self.paths["path_report"], self.paths["ads_performance"], config=self.config
        )


class RegistrationTest(DnnTestCase):
    def test_model_is_registered(self) -> None:
        self.assertIn("dnn_credit", MODEL_REGISTRY)
        self.assertIs(MODEL_REGISTRY["dnn_credit"], DeepNeuralAttributionModel)
        self.assertIsInstance(build_model("dnn_credit"), DeepNeuralAttributionModel)

    def test_capabilities_describe_a_trained_persistent_model(self) -> None:
        capabilities = DeepNeuralAttributionModel.capabilities
        self.assertTrue(capabilities.requires_fit)
        self.assertTrue(capabilities.supports_persistence)
        self.assertTrue(capabilities.deterministic)
        self.assertEqual(capabilities.supported_outcomes, SUPPORTED_OUTCOMES)

    def test_hyperparameters_are_validated(self) -> None:
        for kwargs in (
            {"epochs": 0},
            {"learning_rate": 0.0},
            {"hidden_sizes": ()},
            {"hidden_sizes": (4, 0)},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    DeepNeuralAttributionModel(**kwargs)


class FeatureTest(DnnTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.features = build_touchpoint_features(self.dataset)

    def test_features_cover_every_dataset_touchpoint(self) -> None:
        self.assertEqual(set(self.features), set(self.dataset.touchpoints))
        for item in self.features.values():
            self.assertEqual(len(item.segments), len(SEGMENT_NAMES))
            self.assertEqual(len(item.numeric), len(NUMERIC_FEATURE_NAMES))

    def test_appearance_ratio_counts_paths(self) -> None:
        # SEARCH appears in three of the four fixture paths, DISPLAY in two.
        self.assertAlmostEqual(self.features[fixtures.SEARCH].numeric[0], 0.75)
        self.assertAlmostEqual(self.features[fixtures.DISPLAY].numeric[0], 0.50)

    def test_relative_position_distinguishes_first_from_last(self) -> None:
        # DISPLAY only ever opens a two-step path; SEARCH only ever closes one
        # except for the single-touchpoint path scored at 0.5.
        self.assertAlmostEqual(self.features[fixtures.DISPLAY].numeric[1], 0.0)
        self.assertAlmostEqual(
            self.features[fixtures.SEARCH].numeric[1], (1.0 + 0.5 + 1.0) / 3
        )

    def test_user_share_is_weighted_by_path_users(self) -> None:
        self.assertAlmostEqual(
            self.features[fixtures.DISPLAY].numeric[3], 160 / 290
        )

    def test_features_never_expose_ground_truth(self) -> None:
        for item in self.features.values():
            for value in item.numeric:
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)


class EncoderTest(DnnTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.features = build_touchpoint_features(self.dataset)
        self.encoder = _FeatureEncoder.fit(self.features)

    def test_width_matches_the_encoded_vector(self) -> None:
        item = self.features[fixtures.SEARCH]
        self.assertEqual(len(self.encoder.encode(item.segments, item.numeric)),
                         self.encoder.width)

    def test_known_value_sets_its_own_bucket(self) -> None:
        item = self.features[fixtures.SEARCH]
        vector = self.encoder.encode(item.segments, item.numeric)
        # The first block is ad_product; index 0 is the reserved unknown bucket.
        self.assertEqual(vector[0], 0.0)
        self.assertEqual(sum(vector[: len(self.encoder.vocabularies[0]) + 1]), 1.0)

    def test_unseen_value_falls_into_the_unknown_bucket(self) -> None:
        vector = self.encoder.encode(("NEW_PRODUCT", "NEW_FORMAT", "X", "Y"))
        self.assertEqual(vector[0], 1.0)

    def test_missing_numeric_features_fall_back_to_training_means(self) -> None:
        vector = self.encoder.encode(("NEW_PRODUCT", "NEW_FORMAT", "X", "Y"))
        self.assertEqual(
            tuple(vector[-len(NUMERIC_FEATURE_NAMES):]), self.encoder.numeric_means
        )

    def test_segment_count_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.encoder.encode(("AMAZON_DSP", "OTT"))

    def test_payload_round_trip(self) -> None:
        restored = _FeatureEncoder.from_payload(self.encoder.to_payload())
        item = self.features[fixtures.SEARCH]
        self.assertEqual(
            restored.encode(item.segments, item.numeric),
            self.encoder.encode(item.segments, item.numeric),
        )


class TrainingTest(DnnTestCase):
    def test_output_satisfies_the_standard_contract(self) -> None:
        rows = DeepNeuralAttributionModel().fit(self.dataset).attribute(self.dataset)
        summary = validate_standard_output(
            rows,
            outcome_totals=self.dataset.outcome_totals,
            expected_touchpoints=self.dataset.touchpoints,
        )
        self.assertEqual(summary["row_count"], 9)
        self.assertEqual(summary["models"], [("dnn_credit", "1.0.0")])

    def test_training_converges_towards_the_shapley_target(self) -> None:
        model = DeepNeuralAttributionModel().fit(self.dataset)
        predicted = model.predicted_shares(self.dataset)
        for result in run_shapley_attribution(list(self.dataset.path_rows)):
            touchpoint = to_four_segment(result.touchpoint)
            for outcome in SUPPORTED_OUTCOMES:
                share_field, _ = OUTCOME_FIELDS[outcome]
                with self.subTest(touchpoint=touchpoint, outcome=outcome):
                    self.assertAlmostEqual(
                        predicted[outcome][touchpoint],
                        getattr(result, share_field),
                        places=4,
                    )

    def test_softmax_conserves_share_before_any_rounding(self) -> None:
        predicted = DeepNeuralAttributionModel().fit(self.dataset).predicted_shares(
            self.dataset
        )
        for outcome, shares in predicted.items():
            with self.subTest(outcome=outcome):
                self.assertAlmostEqual(math.fsum(shares.values()), 1.0, places=12)

    def test_repeated_training_is_bit_identical(self) -> None:
        first = DeepNeuralAttributionModel().fit(self.dataset).attribute(self.dataset)
        second = DeepNeuralAttributionModel().fit(self.dataset).attribute(self.dataset)
        self.assertEqual(first, second)

    def test_a_different_seed_changes_the_learned_parameters(self) -> None:
        default = DeepNeuralAttributionModel().fit(self.dataset)
        reseeded = DeepNeuralAttributionModel(seed=7, epochs=5).fit(self.dataset)
        self.assertNotEqual(
            default.attribute(self.dataset), reseeded.attribute(self.dataset)
        )

    def test_attribute_requires_fit(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires fit"):
            DeepNeuralAttributionModel().attribute(self.dataset)

    def test_attribute_rejects_a_different_report_scope(self) -> None:
        other = load_mta_sim_dataset(
            fixtures.write_path_report(self.directory / "uk", marketplace="UK"),
            config=self.config,
        )
        model = DeepNeuralAttributionModel().fit(self.dataset)
        with self.assertRaisesRegex(RuntimeError, "different report scope"):
            model.attribute(other)


class ZeroOutcomeTest(DnnTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.zero_dataset = load_mta_sim_dataset(
            fixtures.write_path_report(self.directory / "zero", rows=ZERO_OUTCOME_PATHS),
            config=self.config,
        )

    def test_zero_outcomes_are_not_redistributed(self) -> None:
        rows = (
            DeepNeuralAttributionModel()
            .fit(self.zero_dataset)
            .attribute(self.zero_dataset)
        )
        for row in rows:
            self.assertEqual(row.attribution_share, 0.0)
            self.assertEqual(row.attributed_value, 0.0)
            self.assertEqual(row.warnings, (ZERO_OUTCOME_WARNING,))
        validate_standard_output(
            rows, outcome_totals=self.zero_dataset.outcome_totals
        )


class NewCampaignPredictionTest(DnnTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.model = DeepNeuralAttributionModel().fit(self.dataset)

    def test_predicts_for_touchpoints_absent_from_training(self) -> None:
        for touchpoint in NEW_CAMPAIGN:
            self.assertNotIn(touchpoint, self.dataset.touchpoints)
        predicted = self.model.predict_new_campaign(NEW_CAMPAIGN)
        self.assertEqual(set(predicted), set(SUPPORTED_OUTCOMES))
        for outcome, shares in predicted.items():
            with self.subTest(outcome=outcome):
                self.assertEqual(set(shares), set(NEW_CAMPAIGN))
                self.assertAlmostEqual(math.fsum(shares.values()), 1.0, places=12)
                for share in shares.values():
                    self.assertGreater(share, 0.0)

    def test_prediction_is_deterministic(self) -> None:
        self.assertEqual(
            self.model.predict_new_campaign(NEW_CAMPAIGN),
            self.model.predict_new_campaign(NEW_CAMPAIGN),
        )

    def test_prediction_is_independent_of_input_order(self) -> None:
        self.assertEqual(
            self.model.predict_new_campaign(NEW_CAMPAIGN),
            self.model.predict_new_campaign(tuple(reversed(NEW_CAMPAIGN))),
        )

    def test_single_touchpoint_campaign_takes_all_credit(self) -> None:
        predicted = self.model.predict_new_campaign([NEW_CAMPAIGN[0]])
        for shares in predicted.values():
            self.assertAlmostEqual(shares[NEW_CAMPAIGN[0]], 1.0, places=12)

    def test_requires_fit(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires fit"):
            DeepNeuralAttributionModel().predict_new_campaign(NEW_CAMPAIGN)

    def test_rejects_empty_campaign(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one touchpoint"):
            self.model.predict_new_campaign([])

    def test_rejects_duplicate_touchpoints(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct touchpoints"):
            self.model.predict_new_campaign([NEW_CAMPAIGN[0], NEW_CAMPAIGN[0]])

    def test_rejects_a_five_segment_key(self) -> None:
        with self.assertRaises(ValueError):
            self.model.predict_new_campaign([f"{fixtures.DISPLAY}:IMPRESSION"])


class PersistenceTest(DnnTestCase):
    def test_round_trip_reproduces_identical_output(self) -> None:
        model = DeepNeuralAttributionModel().fit(self.dataset)
        destination = model.save(self.directory / "dnn.json")
        restored = DeepNeuralAttributionModel.load(destination)
        self.assertEqual(
            restored.attribute(self.dataset), model.attribute(self.dataset)
        )
        self.assertEqual(
            restored.predict_new_campaign(NEW_CAMPAIGN),
            model.predict_new_campaign(NEW_CAMPAIGN),
        )

    def test_saving_before_fit_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires fit"):
            DeepNeuralAttributionModel().save(self.directory / "unfitted.json")

    def test_loading_another_model_file_is_rejected(self) -> None:
        destination = (
            build_model("path_level_shapley").fit(self.dataset).save(
                self.directory / "shapley.json"
            )
        )
        with self.assertRaisesRegex(ValueError, "expected dnn_credit"):
            DeepNeuralAttributionModel.load(destination)


if __name__ == "__main__":
    unittest.main()
