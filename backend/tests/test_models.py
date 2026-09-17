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
            "modules/mta_strategy_evaluation/src/evaluate_strategies.py",
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


class CampaignPreviewTests(unittest.TestCase):
    """Verify real scoped fitting, source isolation and ordinary-only outcomes."""

    def research(self):
        import math
        budgets, outcomes = [], []
        for index, budget in enumerate((20, 40, 80, 120, 160)):
            scope = {"advertiser_id": "account", "marketplace": "US", "currency": "USD",
                     "report_start_date": f"2026-01-0{index + 1}", "report_end_date": f"2026-01-0{index + 1}"}
            spend = 100 * (1 - math.exp(-budget / 100))
            common = {"campaign_id": "A", "budget_level": budget / 80, "reporting_scope": scope}
            budgets.append({**common, "configured_budget": budget, "actual_spend": spend})
            outcomes.append({**common, "total_revenue": 10 + 500 * (1 - math.exp(-spend / 40))})
        return {"simulation_runs": [{"campaigns": [{"campaign_id": "A", "provider": "AMAZON_ADS", "ad_product": "Sponsored Products", "status": "ACTIVE"}]}],
                "budget_observations": budgets, "outcome_observations": outcomes,
                "evaluation_outcome_observations": [{"total_revenue": 999999999}]}

    def test_selected_campaign_fits_real_history_without_evaluation_truth(self):
        from backend.services.models import optimize
        with patch("backend.services.datasets.dataset_inputs", return_value={"research": self.research()}):
            result = optimize({"datasetId": "selected", "campaignId": "A", "marketplace": "US"})
        self.assertEqual(result["campaign_id"], "A")
        self.assertEqual(result["observation_count"], 5)
        self.assertEqual(result["response_observations"][0]["report_date"], "2026-01-01")
        self.assertNotIn("impressions", result["response_observations"][0])
        self.assertEqual(result["optimized_strategy"]["allocated_budget"], 160)
        self.assertEqual([row["campaign_id"] for row in result["optimized_strategy"]["allocations"]], ["A"])
        self.assertLess(result["optimized_strategy"]["expected_optimized_revenue"], 1000)

    def test_unknown_source_never_falls_back(self):
        from backend.services.models import optimize, ModelUnavailableError
        with patch("backend.services.datasets.dataset_inputs", side_effect=ValueError("missing")):
            with self.assertRaises(ModelUnavailableError):
                optimize({"datasetId": "unknown", "campaignId": "A", "marketplace": "US"})

    def test_missing_ordinary_revenue_refuses_instead_of_using_evaluation(self):
        from backend.services.models import optimize, ModelUnavailableError
        research = self.research(); research["outcome_observations"] = []
        with patch("backend.services.datasets.dataset_inputs", return_value={"research": research}):
            with self.assertRaises(ModelUnavailableError):
                optimize({"datasetId": "selected", "campaignId": "A", "marketplace": "US"})

    def test_scope_and_finite_values_are_validated(self):
        from backend.services.models import optimize, ModelRequestError, ModelUnavailableError
        research = self.research()
        with patch("backend.services.datasets.dataset_inputs", return_value={"research": research}):
            with self.assertRaises(ModelRequestError):
                optimize({"datasetId": "selected", "campaignId": "A"})
            research["budget_observations"][0]["actual_spend"] = float("nan")
            result = optimize({"datasetId": "selected", "campaignId": "A", "marketplace": "US"})
            self.assertEqual(result["observation_count"], 4)
            self.assertEqual(result["history_selection"]["excluded_observation_count"], 1)


    def test_full_history_transfers_to_target_without_relabeling_public_evidence(self):
        import copy
        from backend.services.models import optimize, ModelUnavailableError
        research = self.research()
        research["simulation_runs"][0]["campaigns"].append({"campaign_id": "B", "provider": "AMAZON_ADS", "ad_product": "Sponsored Products", "status": "ACTIVE"})
        target = copy.deepcopy(research["budget_observations"][0]); target["campaign_id"] = "B"
        research["budget_observations"].append(target)
        with patch("backend.services.datasets.dataset_inputs", return_value={"research": research}):
            result = optimize({"datasetId": "selected", "campaignId": "B", "marketplace": "US"})
            self.assertTrue(result["optimized_strategy"]["is_optimized"])
            self.assertEqual(result["optimized_strategy"]["allocations"][0]["campaign_id"], "B")
            self.assertEqual(result["history_selection"]["reference_campaign_ids"], ["A"])
            self.assertEqual({row["campaign_id"] for row in result["response_observations"]}, {"A"})
            self.assertEqual(result["response_models"]["campaign_models"]["B"]["diagnostics"]["support"], "POOLED_TRANSFER")
            with self.assertRaises(ModelUnavailableError):
                optimize({"datasetId": "selected", "campaignId": "B", "marketplace": "US", "historyMode": "campaign"})

    def test_unleveled_outcomes_match_only_baseline_and_return_historical_reference(self):
        import copy
        from backend.services.models import optimize
        research = self.research()
        base = copy.deepcopy(research["budget_observations"][2])
        research["budget_observations"] = [base, {**base, "budget_level": 1.5, "configured_budget": 120}]
        outcome = copy.deepcopy(research["outcome_observations"][2]); outcome.pop("budget_level")
        research["outcome_observations"] = [outcome]
        with patch("backend.services.datasets.dataset_inputs", return_value={"research": research}):
            result = optimize({"datasetId": "selected", "campaignId": "A", "marketplace": "US"})
        self.assertEqual(result["observation_count"], 1)
        self.assertEqual(result["historical_recommendation"]["recommended_budget"], 80)
        self.assertEqual(result["optimized_strategy"]["recommendation_type"], "HISTORICAL_BASELINE")
        self.assertFalse(result["optimized_strategy"]["is_optimized"])

    def test_full_history_excludes_other_accounts_and_currencies(self):
        import copy
        from backend.services.models import optimize, ModelUnavailableError
        research = self.research()
        research["simulation_runs"][0]["campaigns"].append({"campaign_id": "B", "provider": "AMAZON_ADS", "ad_product": "Sponsored Products"})
        target = copy.deepcopy(research["budget_observations"][0]); target["campaign_id"] = "B"
        target["reporting_scope"]["advertiser_id"] = "other"
        research["budget_observations"].append(target)
        with patch("backend.services.datasets.dataset_inputs", return_value={"research": research}):
            with self.assertRaises(ModelUnavailableError):
                optimize({"datasetId": "selected", "campaignId": "B", "marketplace": "US"})


    def test_initial_budget_and_similarity_threshold_change_the_request(self):
        import copy
        from backend.services.models import optimize, ModelUnavailableError, ModelRequestError
        research = self.research()
        research["simulation_runs"][0]["campaigns"].append({"campaign_id": "B", "provider": "AMAZON_ADS", "ad_product": "Sponsored Products"})
        target = copy.deepcopy(research["budget_observations"][0]); target["campaign_id"] = "B"
        research["budget_observations"].append(target)
        with patch("backend.services.datasets.dataset_inputs", return_value={"research": research}):
            body = {"datasetId": "selected", "campaignId": "B", "marketplace": "US", "initialBudget": 80, "similarityThreshold": 1}
            result = optimize(body)
            self.assertEqual(result["observation_count"], 1)
            self.assertEqual(result["initial_strategy"]["allocations"][0]["initial_budget"], 80)
            self.assertEqual(result["initial_strategy"]["allocations"][0]["allocation_basis"], "USER_SPECIFIED")
            self.assertEqual(result["history_selection"]["similarity_threshold"], 1)
            self.assertEqual(result["historical_recommendation"]["recommended_budget"], 80)
            with self.assertRaises(ModelUnavailableError):
                optimize({**body, "initialBudget": 81})
            for fields in ({"initialBudget": -1}, {"initialBudget": float("inf")}, {"similarityThreshold": 1.1}, {"similarityThreshold": True}):
                with self.assertRaises(ModelRequestError):
                    optimize({**body, **fields})
            own = optimize({**body, "campaignId": "A", "initialBudget": 81})
            self.assertEqual(own["observation_count"], 5)
