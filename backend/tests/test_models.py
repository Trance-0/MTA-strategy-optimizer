"""HTTP contracts for attribution, recommendation, and evaluation models."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import create_app
from backend.services.models import load_dataset


class ModelEndpointTests(unittest.TestCase):
    """Exercise real light-weight models and unavailable-capability paths."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = patch.dict(os.environ, {"DATABASE": "false"})
        cls.environment.start()
        cls.client = create_app().test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.environment.stop()

    def test_catalogue_lists_registered_models_and_capabilities(self) -> None:
        response = self.client.get("/api/models")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        identifiers = {
            item["model_id"] for item in payload["attribution"]["models"]
        }
        self.assertEqual(
            identifiers,
            {
                "dnn_credit",
                "markov_removal_effect",
                "path_level_shapley",
                "uniform_credit",
            },
        )
        self.assertTrue(payload["recommendation"]["available"])
        self.assertTrue(payload["evaluation"]["strategyEvaluation"]["available"])
        self.assertEqual(
            payload["evaluation"]["strategyEvaluation"]["script"],
            "script/evaluate_strategies.py",
        )

    def test_uniform_attribution_executes_against_the_default_report(self) -> None:
        response = self.client.post(
            "/api/models/uniform_credit/attribute", json={}
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["model_id"], "uniform_credit")
        self.assertEqual(payload["row_count"], 51)
        self.assertEqual(len(payload["rows"]), 51)

    def test_model_comparison_executes_once_per_requested_model(self) -> None:
        response = self.client.post(
            "/api/models/compare",
            json={"modelIds": ["uniform_credit", "markov_removal_effect"]},
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(
            set(response.get_json()["runs"]),
            {"uniform_credit", "markov_removal_effect"},
        )

    def test_recommendation_executes_against_committed_inputs(self) -> None:
        response = self.client.post("/api/models/recommend", json={})

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertFalse(payload["is_optimized"])
        self.assertGreater(len(payload["campaigns"]), 0)

    def test_optimizer_names_the_missing_research_snapshot(self) -> None:
        response = self.client.post("/api/models/optimize", json={})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "model_unavailable")
        self.assertIn("research snapshot", response.get_json()["message"])

    def test_evaluation_names_the_missing_ground_truth(self) -> None:
        response = self.client.post(
            "/api/models/evaluate", json={"modelId": "uniform_credit"}
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "model_unavailable")
        self.assertIn("ground truth", response.get_json()["message"])

    def test_evaluation_executes_when_ground_truth_is_supplied(self) -> None:
        dataset = load_dataset()
        with tempfile.TemporaryDirectory(prefix="backend_evaluation_") as temporary:
            truth = Path(temporary) / "simulation_ground_truth.csv"
            share = 1.0 / len(dataset.touchpoints)
            with truth.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "report_start_date",
                        "report_end_date",
                        "marketplace",
                        "path",
                        "normalized_touchpoint",
                        "causal_increment",
                        "credit_share",
                        "expected_conversion_probability",
                    ],
                    lineterminator="\n",
                )
                writer.writeheader()
                for touchpoint in dataset.touchpoints:
                    writer.writerow(
                        {
                            "report_start_date": dataset.scope.report_start_date,
                            "report_end_date": dataset.scope.report_end_date,
                            "marketplace": dataset.scope.marketplace,
                            "path": touchpoint,
                            "normalized_touchpoint": touchpoint,
                            "causal_increment": share,
                            "credit_share": share,
                            "expected_conversion_probability": share,
                        }
                    )

            response = self.client.post(
                "/api/models/evaluate",
                json={"modelId": "uniform_credit", "groundTruth": str(truth)},
            )

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(len(payload["reports"]), 1)
        self.assertEqual(payload["reports"][0]["model_id"], "uniform_credit")

    def test_unknown_model_is_a_bad_request(self) -> None:
        response = self.client.post("/api/models/unknown/attribute", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_request")

    def test_evaluation_rejects_a_non_positive_top_k(self) -> None:
        response = self.client.post(
            "/api/models/evaluate",
            json={
                "modelId": "uniform_credit",
                "groundTruth": __file__,
                "topK": 0,
            },
        )

        # Ground truth is opened after request validation, so an invalid
        # ranking boundary never causes file parsing or model execution.
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_request")
        self.assertIn("positive integer", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
