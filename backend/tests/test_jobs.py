"""Pipeline job capability, route, option, and command tests.

The deployment keeps settings configuration protected while allowing model
execution. These tests keep that permission split explicit and prove the
server reports unavailable stages before a disabled run is attempted.
"""

from __future__ import annotations

import copy
import csv
from datetime import date, timedelta
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app import create_app
from backend import config as backend_config
from backend.services.jobs import (
    OptionError,
    arguments_for,
    jobs_state,
    normalize_options,
    reset_state,
    start_job,
    start_refusal,
)
from backend.services.model_datasets import DatasetError, PreparedDataset
from backend.services import model_datasets
from modules.mta_standard.src.dataloader import MTA_SIM_ADS_FIELDS
from modules.mta_attribution.src.run_attribution_models import read_attribution_ads_rows


class JobServiceTests(unittest.TestCase):
    """Check the pure job contract before any child process is spawned."""

    def setUp(self) -> None:
        reset_state()

    def test_job_state_separates_server_permission_from_database_mode(self) -> None:
        with (
            patch("backend.services.jobs.datasets_for", return_value=[{"id": "scope"}]),
            patch(
                "backend.services.jobs.pipeline_output_directory",
                return_value=Path("runtime"),
            ),
        ):
            disabled = jobs_state(execution_enabled=False, database_enabled=True)
            file_mode = jobs_state(execution_enabled=True, database_enabled=False)

        self.assertFalse(disabled["stages"]["attribution"]["available"])
        self.assertIn(
            "PIPELINE_RUNS_ENABLED",
            disabled["stages"]["attribution"]["unavailableReason"],
        )
        self.assertTrue(file_mode["stages"]["attribution"]["available"])
        self.assertTrue(file_mode["stages"]["attribution"]["artifacts"]["canUpload"])
        self.assertFalse(file_mode["stages"]["attribution"]["artifacts"]["canImport"])

    def test_available_stage_declares_datasets_and_default(self) -> None:
        choices = [
            {"id": "scope-a", "label": "Scope A"},
            {"id": "scope-b", "label": "Scope B"},
        ]
        with (
            patch("backend.services.jobs.datasets_for", return_value=choices),
            patch(
                "backend.services.jobs.pipeline_output_directory",
                return_value=Path("runtime"),
            ),
        ):
            stage = jobs_state()["stages"]["attribution"]

        self.assertTrue(stage["available"])
        self.assertEqual(stage["datasets"], choices)
        self.assertEqual(stage["defaultDataset"], "scope-a")

    def test_unset_output_directory_uses_a_verified_ignored_runtime(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict("os.environ", {}, clear=False),
            patch.object(backend_config, "_load_env"),
            patch.object(
                backend_config,
                "DEFAULT_PIPELINE_OUTPUT_DIR",
                Path(temporary) / "generated" / "pipeline-output",
            ),
        ):
            import os

            os.environ.pop("PIPELINE_OUTPUT_DIR", None)
            runtime = backend_config.pipeline_output_directory()
            self.assertIsNotNone(runtime)
            self.assertTrue(runtime.is_dir())

    def test_database_attribution_has_no_refusal(self) -> None:
        with patch(
            "backend.services.jobs.resolve_dataset", return_value={"id": "scope"}
        ):
            self.assertIsNone(
                start_refusal(
                    "attribution", writable=True, options={"datasetId": "scope"}
                )
            )

    def test_evaluation_keeps_strategy_only_fallback_without_research_tables(
        self,
    ) -> None:
        with patch.object(model_datasets, "table_exists", return_value=False):
            evaluation = model_datasets.datasets_for(
                "evaluation", database_enabled=True
            )
            optimization = model_datasets.datasets_for(
                "optimization", database_enabled=True
            )

        self.assertEqual(evaluation[0]["id"], "files|evaluation|strategy-artifacts")
        self.assertEqual(optimization, [])

    def test_options_become_fixed_command_arguments(self) -> None:
        options = normalize_options({"datasetId": "server-scope", "totalBudget": "125"})
        prepared = PreparedDataset(
            dataset_id="server-scope",
            marketplace="US",
            path_report=Path("path.csv"),
            performance_report=Path("ads.csv"),
        )
        arguments = arguments_for("attribution", options, prepared)

        self.assertEqual(
            arguments[:6],
            [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                "-m",
                "modules.mta_attribution.src.run_attribution_models",
            ],
        )
        self.assertEqual(arguments[arguments.index("--amc-report") + 1], "path.csv")
        self.assertEqual(
            arguments[arguments.index("--amazon-ads-report") + 1], "ads.csv"
        )

    def test_runtime_paths_are_passed_to_every_stage(self) -> None:
        runtime = Path("pipeline-test-output").resolve()
        snapshot = Path("simulation_research.json").resolve()
        with (
            patch(
                "backend.services.jobs.pipeline_output_directory",
                return_value=runtime,
            ),
        ):
            attribution = arguments_for(
                "attribution",
                {"datasetId": "a"},
                PreparedDataset("a", "US", Path("path.csv"), Path("ads.csv")),
            )
            research = PreparedDataset("r", "US", research_snapshot=snapshot)
            optimization = arguments_for("optimization", {"datasetId": "r"}, research)
            evaluation = arguments_for("evaluation", {"datasetId": "r"}, research)

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

    def test_missing_dataset_is_rejected_before_spawn(self) -> None:
        with self.assertRaisesRegex(OptionError, "datasetId is required"):
            normalize_options({})
        with patch(
            "backend.services.jobs.resolve_dataset",
            side_effect=DatasetError("stale dataset"),
        ):
            refusal = start_refusal(
                "attribution", writable=True, options={"datasetId": "stale"}
            )
        self.assertEqual(refusal["code"], "missing_input")
        self.assertIn("stale dataset", refusal["message"])

    def test_unwritable_runtime_directory_is_a_failed_job(self) -> None:
        with (
            patch(
                "backend.services.jobs.resolve_dataset",
                return_value={"id": "scope", "label": "Scope"},
            ),
            patch(
                "backend.services.jobs.prepare_runtime_inputs",
                side_effect=PermissionError("read-only mount"),
            ),
            patch("backend.services.jobs.subprocess.Popen") as popen,
        ):
            job = start_job("attribution", {"datasetId": "scope"})

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

    def test_database_attribution_normalizes_only_proven_simulator_boundary(self) -> None:
        """Exercise prepared CSVs through the real attribution entry point."""
        from modules.mta_attribution.src.run_attribution_models import run_attribution_models

        key = "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:IMAGE:CLICK"
        for start, end in [("2025-01-01", "2025-12-31"), ("2024-02-29", "2024-02-29")]:
            with self.subTest(start=start):
                first, last = date.fromisoformat(start), date.fromisoformat(end)
                boundary = (last + timedelta(days=1)).isoformat()
                dataset = {"id": "scope", "reportStartDate": start, "reportEndDate": boundary,
                           "marketplace": "US", "advertiserId": "synthetic_kfc_us_experiment"}
                paths = [{"report_start_date": first, "report_end_date": date.fromisoformat(boundary),
                          "marketplace": "US", "advertiser_id": dataset["advertiserId"], "path": key,
                          "users": 10, "converted_users": 5, "purchase_count": 5, "revenue": 100}]
                performance = [{"reportDate": first + timedelta(days=offset), "marketplace": "US",
                                "accountId": dataset["advertiserId"], "adProduct": "SPONSORED_PRODUCTS",
                                "adType": "PRODUCT_AD", "creativeType": "IMAGE", "inventoryType": "",
                                "placement": "TOP_OF_SEARCH", "interaction_type": "CLICK", "cost_type": "CPC",
                                "normalizedTouchpoint": key, "currencyCode": "USD", "impressions": 0,
                                "clicks": 10, "cost": 2, "purchases": 5, "sales": 100}
                               for offset in range((last - first).days + 1)]
                run = {"run_id": "run-1", "effective_configuration": {
                    "advertiser_id": dataset["advertiserId"], "report_start_date": start, "report_end_date": end}}
                original = copy.deepcopy(paths)
                with tempfile.TemporaryDirectory() as directory:
                    target = Path(directory)
                    path_file, ads_file = target / "paths.csv", target / "ads.csv"
                    with patch.object(model_datasets, "sql", side_effect=[paths, performance, [run]]), patch.object(model_datasets, "table_exists", return_value=True):
                        model_datasets._write_attribution_inputs(dataset, path_file, ads_file)
                    with path_file.open(encoding="utf-8") as handle:
                        prepared = list(csv.DictReader(handle))
                    self.assertEqual(prepared[0]["report_end_date"], end)
                    self.assertEqual(paths, original, "source records must not be rewritten")
                    outputs = run_attribution_models(path_file, target / "outputs", ads_file)
                    self.assertEqual(len(outputs), 5)
                    self.assertTrue(all(Path(value).is_file() for value in outputs))

                    # A known next-day difference without matching provenance is
                    # still an error, not permission to discard a missing day.
                    invalid_cases = [
                        (paths, performance, [], "report date mismatch"),
                        (paths, performance, [run, run], "report date mismatch"),
                        (paths, performance, [{**run, "effective_configuration": {**run["effective_configuration"], "report_end_date": boundary}}], "report date mismatch"),
                        (paths, performance + [performance[0]], [run], "duplicate"),
                    ]
                    if len(performance) > 2:
                        invalid_cases.extend([
                            (paths, performance[:-1], [run], "report date mismatch"),
                            (paths, performance[:1] + performance[2:], [run], "continuous"),
                            (paths, performance[1:], [run], "report date mismatch"),
                        ])
                    for bad_paths, bad_ads, runs, reason in invalid_cases:
                        before = (path_file.read_bytes(), ads_file.read_bytes())
                        with patch.object(model_datasets, "sql", side_effect=[bad_paths, bad_ads, runs]), patch.object(model_datasets, "table_exists", return_value=True):
                            with self.assertRaisesRegex(ValueError, reason):
                                model_datasets._write_attribution_inputs(dataset, path_file, ads_file)
                        self.assertEqual((path_file.read_bytes(), ads_file.read_bytes()), before)

                    # Inclusive datasets retain their exact bounds without needing
                    # simulator metadata, including a single leap day.
                    inclusive = {**dataset, "reportEndDate": end}
                    inclusive_paths = [{**paths[0], "report_end_date": last}]
                    with patch.object(model_datasets, "sql", side_effect=[inclusive_paths, performance]), patch.object(model_datasets, "table_exists") as tables:
                        model_datasets._write_attribution_inputs(inclusive, path_file, ads_file)
                        tables.assert_not_called()

    def test_research_materialization_excludes_evaluation_only_outcomes(self) -> None:
        statements = []

        def rows(statement, _parameters=None):
            statements.append(statement)
            if "from mta_simulation_run" in statement:
                return [
                    {
                        "run_id": "run-1",
                        "seed": 7,
                        "configuration_sha256": "abc",
                        "effective_configuration": {},
                    }
                ]
            if "min(report_date)" in statement:
                return [
                    {
                        "advertiser_id": "adv",
                        "currency": "USD",
                        "report_start_date": "2026-01-01",
                        "report_end_date": "2026-01-01",
                    }
                ]
            if "from mta_sim_budget_observation" in statement:
                return [
                    {
                        "id": 1,
                        "run_id": "run-1",
                        "campaign_id": "C1",
                        "marketplace": "US",
                        "advertiser_id": "adv",
                        "currency": "USD",
                        "report_date": "2026-01-01",
                        "budget_level": 1.0,
                        "configured_budget": 10.0,
                        "actual_spend": 9.0,
                    }
                ]
            if "from mta_sim_outcome_observation" in statement:
                return [
                    {
                        "id": 2,
                        "run_id": "run-1",
                        "campaign_id": "C1",
                        "product_id": None,
                        "marketplace": "US",
                        "advertiser_id": "adv",
                        "currency": "USD",
                        "report_date": "2026-01-01",
                        "provider": "AMAZON_ADS",
                        "touchpoint_key": "SPONSORED_PRODUCTS:PRODUCT_AD:TOP_OF_SEARCH:IMAGE:CLICK",
                        "placement_availability": "AVAILABLE",
                        "creative_availability": "AVAILABLE",
                        "interaction_type_availability": "AVAILABLE",
                        "total_units": 1,
                        "total_revenue": 20.0,
                        "evaluation_only": False,
                    }
                ]
            return []

        dataset = {"id": "research|run-1|US", "runId": "run-1", "marketplace": "US"}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(model_datasets, "sql", side_effect=rows),
        ):
            destination = Path(temporary) / "research.json"
            model_datasets._write_research_snapshot(dataset, destination)
            payload = json.loads(destination.read_text(encoding="utf-8"))

        self.assertEqual(len(payload["outcome_observations"]), 1)
        self.assertEqual(payload["evaluation_outcome_observations"], [])
        self.assertTrue(
            any("evaluation_only = false" in statement for statement in statements)
        )


class JobRouteTests(unittest.TestCase):
    """Check protected settings no longer block an enabled pipeline route."""

    def setUp(self) -> None:
        self.client = create_app().test_client()

    def test_protected_deployment_can_start_an_enabled_stage(self) -> None:
        job = SimpleNamespace(command="uv run python -m modules.mta_attribution.src.run_pipeline")
        with (
            patch("backend.api.jobs.is_hosted", return_value=False),
            patch("backend.api.jobs.pipeline_runs_enabled", return_value=True),
            patch("backend.api.jobs.use_database", return_value=True),
            patch("backend.api.jobs.start_refusal", return_value=None),
            patch("backend.api.jobs.start_job", return_value=job) as start,
            patch(
                "backend.services.jobs.datasets_for",
                return_value=[{"id": "scope", "label": "Scope"}],
            ),
            patch(
                "backend.services.jobs.pipeline_output_directory",
                return_value=Path("runtime"),
            ),
            patch("backend.api.jobs.log"),
        ):
            response = self.client.post(
                "/api/jobs/attribution", json={"datasetId": "scope"}
            )

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
