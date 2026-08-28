"""Pipeline job capability, route, option, and command tests.

The deployment keeps settings configuration protected while allowing model
execution. These tests keep that permission split explicit and prove the
server reports unavailable stages before a disabled run is attempted.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app import create_app
from backend.services.jobs import (
    arguments_for,
    jobs_state,
    normalize_options,
    reset_state,
    start_job,
    start_refusal,
)
from modules.mta_standard.src.dataloader import MTA_SIM_ADS_FIELDS
from script.run_attribution_models import read_attribution_ads_rows


class JobServiceTests(unittest.TestCase):
    """Check the pure job contract before any child process is spawned."""

    def setUp(self) -> None:
        reset_state()

    def test_job_state_separates_server_permission_from_database_mode(self) -> None:
        disabled = jobs_state(execution_enabled=False, database_enabled=True)
        file_mode = jobs_state(execution_enabled=True, database_enabled=False)

        self.assertFalse(disabled["stages"]["attribution"]["available"])
        self.assertIn(
            "PIPELINE_RUNS_ENABLED",
            disabled["stages"]["attribution"]["unavailableReason"],
        )
        self.assertFalse(file_mode["stages"]["attribution"]["available"])
        self.assertIn(
            "connected database",
            file_mode["stages"]["attribution"]["unavailableReason"],
        )

    def test_database_attribution_has_no_refusal(self) -> None:
        self.assertIsNone(start_refusal("attribution", writable=True))

    def test_options_become_fixed_command_arguments(self) -> None:
        options = normalize_options(
            {"startDate": "2026-01-01", "endDate": "2026-01-31"}
        )
        arguments = arguments_for("attribution", options)

        self.assertEqual(arguments[:6], ["uv", "run", "python", "-X", "utf8", "-B"])
        self.assertIn("--report-start-date", arguments)
        self.assertIn("2026-01-31", arguments)

    def test_runtime_paths_are_passed_to_every_stage(self) -> None:
        runtime = Path("pipeline-test-output").resolve()
        snapshot = Path("simulation_research.json").resolve()
        with (
            patch(
                "backend.services.jobs.pipeline_output_directory",
                return_value=runtime,
            ),
            patch("backend.services.jobs.simulator_data_directory", return_value=None),
            patch(
                "backend.services.jobs.research_snapshot_path", return_value=snapshot
            ),
        ):
            attribution = arguments_for("attribution", {})
            optimization = arguments_for("optimization", {"_marketplace": "US"})
            evaluation = arguments_for("evaluation", {"_marketplace": "US"})

        self.assertEqual(
            attribution[attribution.index("--output-dir") + 1],
            str(runtime / "attribution"),
        )
        self.assertEqual(
            optimization[optimization.index("--output") + 1],
            str(runtime / "strategy" / "campaign_strategy.json"),
        )
        self.assertEqual(
            evaluation[evaluation.index("--output") + 1],
            str(runtime / "evaluation" / "strategy_evaluation.json"),
        )
        self.assertEqual(optimization[optimization.index("--marketplace") + 1], "US")
        self.assertEqual(evaluation[evaluation.index("--marketplace") + 1], "US")

    def test_aggregated_simulator_input_uses_direct_attribution_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            simulator = Path(temporary)
            (simulator / "amc_path_report.csv").touch()
            (simulator / "amazon_ads_daily_touchpoint_performance.csv").touch()
            with patch(
                "backend.services.jobs.simulator_data_directory",
                return_value=simulator,
            ):
                arguments = arguments_for("attribution", {})
                refusal = start_refusal(
                    "attribution",
                    writable=True,
                    options={"startDate": "2026-01-01"},
                )

        self.assertIn("script/run_attribution_models.py", arguments)
        self.assertIn("--amc-report", arguments)
        self.assertEqual(refusal["code"], "unsupported_options")
        self.assertIn("uploaded simulator", refusal["message"])

    def test_unwritable_runtime_directory_is_a_failed_job(self) -> None:
        with (
            patch("backend.services.jobs.arguments_for", return_value=["uv", "run"]),
            patch("backend.services.jobs.simulator_data_directory", return_value=None),
            patch("backend.services.jobs.research_snapshot_path", return_value=None),
            patch(
                "backend.services.jobs.prepare_runtime_inputs",
                side_effect=PermissionError("read-only mount"),
            ),
            patch("backend.services.jobs.subprocess.Popen") as popen,
        ):
            job = start_job("attribution", {})

        self.assertEqual(job.state, "failed")
        self.assertIn("Could not prepare", job.error)
        self.assertIn("read-only mount", job.lines[-1]["text"])
        popen.assert_not_called()

    def test_native_simulator_performance_restores_billing_fields(self) -> None:
        touchpoint = "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:IMAGE:CLICK"
        row = {
            "reportDate": "2026-01-01",
            "marketplace": "US",
            "accountId": "adv_test",
            "adProduct": "SPONSORED_PRODUCTS",
            "adType": "PRODUCT_AD",
            "creativeType": "IMAGE",
            "inventoryType": "",
            "placement": "TOP_OF_SEARCH",
            "normalizedTouchpoint": touchpoint,
            "currencyCode": "USD",
            "impressions": "0",
            "clicks": "1",
            "cost": "2.50",
            "purchases": "1",
            "sales": "20",
            "unitsSold": "1",
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "amazon_ads.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=MTA_SIM_ADS_FIELDS)
                writer.writeheader()
                writer.writerow(row)
            parsed = read_attribution_ads_rows(source)

        self.assertEqual(parsed[0]["interaction_type"], "CLICK")
        self.assertEqual(parsed[0]["cost_type"], "CPC")


class JobRouteTests(unittest.TestCase):
    """Check protected settings no longer block an enabled pipeline route."""

    def setUp(self) -> None:
        self.client = create_app().test_client()

    def test_protected_deployment_can_start_an_enabled_stage(self) -> None:
        job = SimpleNamespace(command="uv run python script/run_pipeline.py")
        with (
            patch("backend.api.jobs.is_hosted", return_value=False),
            patch("backend.api.jobs.pipeline_runs_enabled", return_value=True),
            patch("backend.api.jobs.use_database", return_value=True),
            patch("backend.api.jobs.start_refusal", return_value=None),
            patch("backend.api.jobs.start_job", return_value=job) as start,
            patch("backend.api.jobs.log"),
        ):
            response = self.client.post("/api/jobs/attribution", json={})

        self.assertEqual(response.status_code, 202)
        start.assert_called_once()
        self.assertTrue(response.get_json()["stages"]["attribution"]["available"])

    def test_disabled_pipeline_returns_a_specific_permission_remedy(self) -> None:
        with (
            patch("backend.api.jobs.is_hosted", return_value=False),
            patch("backend.api.jobs.pipeline_runs_enabled", return_value=False),
        ):
            response = self.client.post("/api/jobs/attribution", json={})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "pipeline_disabled")
        self.assertIn("PIPELINE_RUNS_ENABLED", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
