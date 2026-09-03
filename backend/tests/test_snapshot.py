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
            side_effect=lambda _name, progress, _window=None: (
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

    def test_a_history_window_is_validated_before_it_reaches_a_query(self) -> None:
        # The bounds are bound parameters by the time they reach SQL, so this
        # is not what makes the query safe. It is what stops a malformed bound
        # from being compared against a `YYYY-MM-DD` column as a string, which
        # would silently return nothing rather than reporting a bad request.
        self.assertEqual(
            snapshot.parse_history_window("2026-01-01", "2026-03-01"),
            {"start": "2026-01-01", "end": "2026-03-01"},
        )
        self.assertEqual(
            snapshot.parse_history_window(None, None), {"start": None, "end": None}
        )
        self.assertEqual(
            snapshot.parse_history_window("2026-01-01'; drop table x --", None),
            {"start": None, "end": None},
        )
        # A reversed range is read as the range the reader described rather
        # than refused: it names a window, just in the other order.
        self.assertEqual(
            snapshot.parse_history_window("2026-05-01", "2026-01-01"),
            {"start": "2026-01-01", "end": "2026-05-01"},
        )

    def test_a_window_reaches_the_loader_and_is_reported_back(self) -> None:
        seen: dict = {}

        def record(*names, history=False, progress=None, window=None):
            seen["window"] = window
            return {"simulationResearch": {name: [] for name in names}}

        with patch.object(snapshot, "_research_fields", side_effect=record):
            snapshot.load_resource(
                "research-campaign-history", {"start": "2026-02-01", "end": None}
            )

        self.assertEqual(seen["window"], {"start": "2026-02-01", "end": None})

    def test_a_windowed_history_states_the_range_it_was_taken_from(self) -> None:
        # A reader cannot infer the excluded range from the rows that survived
        # a window, so the applied bounds travel beside the full observed range.
        payload = snapshot.load_resource(
            "research-campaign-history", {"start": "2026-02-01", "end": "2026-02-28"}
        )
        window = payload["simulationResearch"]["historyWindow"]

        self.assertEqual(window["start"], "2026-02-01")
        self.assertEqual(window["end"], "2026-02-28")
        self.assertIn("earliest", window)
        self.assertIn("latest", window)

    def test_a_widened_window_is_not_served_from_the_narrower_cache(self) -> None:
        # Keyed by name alone, widening a window would return the narrower
        # slice already cached and the view would silently show too little.
        snapshot.clear_caches()
        calls: list = []

        def record(progress=None, window=None):
            calls.append(window)
            return {"history": [], "delivery": [], "touchpointObservations": []}

        with patch.object(snapshot, "simulation_research_history", side_effect=record):
            snapshot.load_research_history(window={"start": "2026-02-01"})
            snapshot.load_research_history(window={"start": "2026-02-01"})
            snapshot.load_research_history(window={"start": "2026-01-01"})

        self.assertEqual(len(calls), 2)
        snapshot.clear_caches()

    def test_resources_without_observations_ignore_a_window(self) -> None:
        # Every other resource would only fragment its cache entry under a
        # window it does not read.
        self.assertEqual(
            snapshot.WINDOWED_RESOURCES,
            {"research-overview", "research-campaign-history"},
        )
        with patch.object(snapshot, "_windowed_resource") as windowed:
            snapshot.load_resource("research-providers", {"start": "2026-02-01"})

        windowed.assert_not_called()

    def test_a_browser_asking_for_no_window_is_given_the_recent_quarter(self) -> None:
        # A full history is 100,000 rows and above 50 MB of JSON. Serving that
        # for a first view of a chart is the wait this default removes; the
        # view is told what it did not load and can still ask for all of it.
        observed = {"earliest": "2026-01-01", "latest": "2026-09-07"}
        with patch.object(snapshot, "load_history_bounds", return_value=observed):
            defaulted = snapshot.resolve_history_window(None, None)
            requested = snapshot.resolve_history_window("2026-01-01", None)
            junk = snapshot.resolve_history_window("not-a-date", "")

        self.assertEqual(defaulted, {"start": "2026-06-10", "end": "2026-09-07"})
        # A named bound is honoured exactly, never widened to the default.
        self.assertEqual(requested, {"start": "2026-01-01", "end": None})
        # A malformed bound names no window, so the default applies to it too.
        self.assertEqual(junk, defaulted)

    def test_a_short_history_is_reported_whole_rather_than_as_a_window(self) -> None:
        # Bounding a range that is already shorter than the default would make
        # the view describe a complete history as a partial one.
        short = {"earliest": "2026-08-01", "latest": "2026-09-07"}
        with patch.object(snapshot, "load_history_bounds", return_value=short):
            self.assertEqual(
                snapshot.resolve_history_window(None, None),
                {"start": None, "end": None},
            )
        # A source with nothing recorded has no range to bound.
        with patch.object(
            snapshot,
            "load_history_bounds",
            return_value={"earliest": None, "latest": None},
        ):
            self.assertEqual(
                snapshot.resolve_history_window(None, None),
                {"start": None, "end": None},
            )

    def test_the_default_window_applies_only_where_a_browser_is_served(self) -> None:
        # The exporter and the compatibility snapshot depend on an unbounded
        # load meaning the whole history, so the default lives on the route.
        with patch.object(dashboard_api, "load_resource", return_value={}) as load:
            self.client.get("/api/dashboard/resources/research-campaign-history")
            self.client.get("/api/dashboard/resources/research-providers")

        windowed, unwindowed = load.call_args_list
        self.assertEqual(windowed.args[0], "research-campaign-history")
        self.assertIsNotNone(windowed.args[1])
        # A resource carrying no observations is asked for without a window.
        self.assertEqual(unwindowed.args, ("research-providers", None))

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
