"""Dashboard snapshot contract and JavaScript parity tests.

These tests keep the Flask response at the exact shape the unchanged Vue
client and the static exporter already consume.
"""

from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api import dashboard as dashboard_api
from backend.app import create_app
from backend.repository import snapshot
from backend.repository import attribution, evaluation, strategy
from backend.repository.master_data import derive_master_data


EXPECTED_KEYS = {
    "mode",
    "source",
    "adsDaily",
    "attributionResults",
    "comparisonTouchpoints",
    "comparisonSummary",
    "recommendedAttribution",
    "entityBridge",
    "pathReport",
    "budgetRecommendation",
    "campaignStrategy",
    "strategyRequest",
    "candidatePool",
    "simulationResearch",
    "strategyEvaluation",
}

EXPECTED_RESOURCES = {
    "shell",
    "performance",
    "attribution",
    "budget",
    "strategy",
    "evaluation",
    "entity-bridge",
    "path-report",
    "research-overview",
    "research-providers",
    "research-products",
    "research-campaigns",
    "research-ad-groups",
    "research-touchpoints",
    "research-product-economics",
    "research-generation-configs",
    "research-campaign-history",
}


class SnapshotContractTests(unittest.TestCase):
    """Exercise the whole local-file snapshot through HTTP."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = patch.dict(os.environ, {"DATABASE": "false"})
        cls.environment.start()
        snapshot.clear_caches()
        cls.client = create_app().test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        snapshot.clear_caches()
        cls.environment.stop()

    def test_dashboard_has_the_complete_client_contract(self) -> None:
        response = self.client.get("/api/dashboard")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(set(payload), EXPECTED_KEYS)
        self.assertEqual(len(payload["adsDaily"]), 1530)
        self.assertEqual(len(payload["attributionResults"]), 34)
        self.assertEqual(len(payload["pathReport"]), 153)
        self.assertEqual(len(payload["simulationResearch"]), 13)
        self.assertEqual(payload["simulationResearch"]["history"], [])
        self.assertEqual(payload["simulationResearch"]["delivery"], [])
        self.assertEqual(payload["simulationResearch"]["touchpointObservations"], [])

    def test_research_history_is_a_route_owned_resource(self) -> None:
        expected = {
            "history": [{"campaign_id": "C1"}],
            "delivery": [{"campaign_id": "C1"}],
            "touchpointObservations": [],
        }
        with patch.object(
            dashboard_api,
            "load_resource",
            return_value={"simulationResearch": expected},
        ):
            response = self.client.get(
                "/api/dashboard/resources/research-campaign-history"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"simulationResearch": expected})

    def test_streamed_resource_reports_backend_phases_before_result(self) -> None:
        with patch.object(
            dashboard_api,
            "load_resource_with_progress",
            side_effect=lambda _name, progress: (
                progress(42, "Querying history") or {"simulationResearch": {}}
            ),
        ):
            response = self.client.get(
                "/api/dashboard/resources/research-campaign-history?stream=1"
            )
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/x-ndjson")
        self.assertIn('"phase": "Request accepted by the backend"', body)
        self.assertIn('"phase": "Querying history"', body)
        self.assertIn('"type": "result"', body)
        self.assertEqual(response.headers["X-Accel-Buffering"], "no")

    def test_unknown_resource_is_rejected_before_loading(self) -> None:
        with patch.object(dashboard_api, "load_resource") as load:
            response = self.client.get("/api/dashboard/resources/private-table")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "resource_not_found")
        load.assert_not_called()

    def test_each_registered_resource_returns_a_mergeable_object(self) -> None:
        self.assertEqual(set(snapshot.RESOURCE_LOADERS), EXPECTED_RESOURCES)
        for resource in snapshot.RESOURCE_LOADERS:
            with self.subTest(resource=resource):
                payload = snapshot.load_resource(resource)
                self.assertIsInstance(payload, dict)
                self.assertTrue(payload)

    def test_campaign_history_carries_its_delivery_filter_bridge(self) -> None:
        payload = snapshot.load_resource("research-campaign-history")

        self.assertIn("campaignProductLinks", payload["simulationResearch"])

    def test_reload_clears_the_snapshot_cache(self) -> None:
        with patch.object(dashboard_api, "clear_caches") as clear:
            response = self.client.post("/api/reload")

        self.assertEqual(response.status_code, 200)
        clear.assert_called_once_with()

    def test_zero_base_impressions_are_not_reported_as_missing(self) -> None:
        catalogue = derive_master_data(
            [
                {
                    "touchpoint": "AMAZON_DSP:AUDIO:UNSPECIFIED:UNSPECIFIED:IMPRESSION",
                    "impressions": 0,
                    "clicks": 0,
                    "cost": 0,
                    "cost_type": "CPM",
                    "currency": "USD",
                }
            ],
            [],
        )

        self.assertEqual(catalogue["touchpoints"][0]["base_impressions"], 0)

    def test_runtime_artifacts_take_precedence_only_when_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            attribution_runtime = runtime / "attribution"
            attribution_runtime.mkdir()
            for name in attribution._RUNTIME_FILES[:-1]:
                (attribution_runtime / name).touch()

            with patch.object(
                attribution, "pipeline_output_directory", return_value=runtime
            ):
                self.assertEqual(
                    attribution._completed_output_directory(),
                    attribution.ATTRIBUTION_OUTPUT_DIR,
                )
                (attribution_runtime / attribution._RUNTIME_FILES[-1]).touch()
                self.assertEqual(
                    attribution._completed_output_directory(), attribution_runtime
                )

            strategy_runtime = runtime / "strategy" / "campaign_strategy.json"
            evaluation_runtime = runtime / "evaluation" / "strategy_evaluation.json"
            strategy_runtime.parent.mkdir()
            evaluation_runtime.parent.mkdir()
            strategy_runtime.write_text(
                json.dumps({"source": "runtime strategy"}), encoding="utf-8"
            )
            evaluation_runtime.write_text(
                json.dumps({"source": "runtime evaluation"}), encoding="utf-8"
            )
            with (
                patch.object(
                    strategy,
                    "pipeline_artifact_path",
                    return_value=strategy_runtime,
                ),
                patch.object(
                    evaluation,
                    "pipeline_artifact_path",
                    return_value=evaluation_runtime,
                ),
            ):
                self.assertEqual(
                    strategy.campaign_strategy()["source"], "runtime strategy"
                )
                self.assertEqual(
                    evaluation.strategy_evaluation()["source"], "runtime evaluation"
                )


if __name__ == "__main__":
    unittest.main()
