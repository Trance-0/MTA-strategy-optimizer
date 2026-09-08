"""Verify persistent workbench runs and plans without a user's database.

Temporary runtime inputs and a controlled queue prove isolation, publication,
revision conflict and restart behavior before real module smoke tests.
"""

from __future__ import annotations

import json
import copy
import io
import time
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services import workbench


class ControlledQueue:
    """Hold accepted operations until a test explicitly executes them."""

    def __init__(self):
        self.entries = {}

    def submit(self, operation, **kwargs):
        task_id = f"task-{len(self.entries) + 1}"
        operation.state = "queued"
        operation.append("queue", "Accepted")
        self.entries[task_id] = (operation, kwargs["runner"])
        return task_id

    def stop(self, task_id):
        operation, _ = self.entries[task_id]
        operation.state = "stopped"
        operation.finished_at = "2026-09-08T00:00:00+00:00"
        operation.append("queue", "Cancelled")
        return "stopped"


class WorkbenchTests(unittest.TestCase):
    """Run the persistence contract with deterministic local observations."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.queue = ControlledQueue()
        self.descriptor = {
            "id": "ds_" + "a" * 32, "name": "First", "digest": "first-digest",
            "isSynthetic": False,
            "scope": {"advertiserId": "a", "marketplace": "US", "currency": "USD", "start": "2026-01-01", "end": "2026-01-01"},
            "capabilities": {key: {"available": True, "reason": None} for key in ("attribution", "optimization", "evaluation")},
        }
        self.inputs = {"performance": [], "paths": [], "research": {"simulation_runs": []}}
        for target, value in (
            ("pipeline_output_directory", self.root),
            ("pipeline_runs_enabled", True), ("is_hosted", False),
            ("get_dataset", self.descriptor), ("dataset_inputs", self.inputs),
        ):
            patcher = patch.object(workbench, target, return_value=value)
            patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(workbench, "manager", self.queue)
        patcher.start(); self.addCleanup(patcher.stop)

    def start(self):
        return workbench.start_run({"datasetId": self.descriptor["id"], "stage": "optimization", "totalBudget": 100})

    def test_runs_freeze_inputs_without_overwriting_other_runs(self):
        first = self.start()
        self.inputs["research"]["marker"] = "second"
        second = self.start()
        base = self.root / "workbench/runs"
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotIn("marker", json.loads((base / first["id"] / "inputs/simulation_research.json").read_text()))
        self.assertEqual("second", json.loads((base / second["id"] / "inputs/simulation_research.json").read_text())["marker"])
        self.assertEqual({}, workbench.latest_result(self.descriptor["id"], "optimization"))

    def test_queued_cancellation_is_durable_and_has_no_result(self):
        run = self.start()
        stopped = workbench.stop_run(run["id"])
        self.assertEqual("stopped", stopped["state"])
        self.assertNotIn("result", stopped)
        stored = json.loads((self.root / "workbench/runs" / run["id"] / "run.json").read_text())
        self.assertEqual("stopped", stored["state"])

    def test_restart_marks_active_run_interrupted_without_requeue(self):
        run = self.start()
        malformed = self.root / "workbench/runs" / ("run_" + "f" * 32) / "run.json"
        malformed.parent.mkdir()
        malformed.write_text('{"state":"running"}', encoding="utf-8")
        with patch.dict(workbench._operations, {}, clear=True):
            workbench.recover_runs()
        self.assertEqual("interrupted", workbench.get_run(run["id"])["state"])
        self.assertEqual(1, len(self.queue.entries))

    def test_execution_disabled_and_unknown_stage_are_refused(self):
        with patch.object(workbench, "pipeline_runs_enabled", return_value=False):
            with self.assertRaises(workbench.WorkbenchError) as error:
                self.start()
            self.assertEqual(403, error.exception.status)
        with self.assertRaises(workbench.WorkbenchError):
            workbench.start_run({"datasetId": self.descriptor["id"], "stage": "arbitrary"})
        for malformed in ({"stage": []}, {"options": []}, {"budgetUsagePolicy": {}}):
            with self.subTest(malformed=malformed), self.assertRaises(workbench.WorkbenchError):
                workbench.start_run({"datasetId": self.descriptor["id"], "stage": "optimization", **malformed})

    def test_recovery_write_failure_keeps_app_and_truthful_history_available(self):
        from backend.app import create_app
        from backend.api import workbench as api
        run = self.start()
        path = self.root / "workbench/runs" / run["id"] / "run.json"
        with patch.dict(workbench._operations, {}, clear=True), patch.object(workbench, "_write", side_effect=OSError("private full volume")), patch.object(api, "pipeline_output_directory", return_value=self.root):
            client = create_app().test_client()
            self.assertEqual(200, client.get("/api/workbench/runs").status_code)
            result = client.get("/api/workbench/runs").get_json()
            self.assertFalse(result["storageAvailable"])
            self.assertFalse(result["executionAvailable"])
            self.assertEqual("interrupted", result["runs"][0]["state"])
            detail = client.get(f'/api/workbench/runs/{run["id"]}').get_json()
            self.assertFalse(detail["recoveryPersisted"])
            self.assertNotIn("private", detail["recoveryError"])
            self.assertEqual("queued", json.loads(path.read_text())["state"])
            refused = client.post("/api/workbench/runs", json={"datasetId": self.descriptor["id"], "stage": "optimization"})
            self.assertEqual(503, refused.status_code)
            self.assertEqual(1, len(self.queue.entries))
        with patch.dict(workbench._operations, {}, clear=True):
            workbench.recover_runs()
        self.assertIsNone(workbench.recovery_storage_error())
        self.assertEqual("interrupted", json.loads(path.read_text())["state"])
        self.assertNotIn("recoveryError", workbench.get_run(run["id"]))

    def test_successful_process_with_missing_artifact_is_failed_by_shared_queue(self):
        from backend.services.tasks import TaskManager
        manager = TaskManager()
        process = SimpleNamespace(stdout=io.StringIO("Model finished\n"), wait=lambda: 0)
        with patch.object(workbench, "manager", manager), patch.object(workbench.subprocess, "Popen", return_value=process):
            run = self.start()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                current = workbench.get_run(run["id"])
                if current["state"] not in {"queued", "running", "stopping"}:
                    break
                time.sleep(0.01)
        self.assertEqual("failed", current["state"])
        self.assertNotIn("result", current)
        self.assertEqual([], current["artifacts"])
        self.assertNotIn(str(self.root), json.dumps(current))

    def test_unknown_or_traversal_identifiers_and_files_are_refused(self):
        with self.assertRaises(workbench.WorkbenchError):
            workbench.get_run("../../outside")
        run = self.start()
        with self.assertRaises(workbench.WorkbenchError):
            workbench.run_artifact_path(run["id"], "../run.json")

    def test_complete_artifacts_publish_but_partial_sets_do_not(self):
        run = self.start()
        operation = workbench._operations[run["id"]]
        artifact = {"currency": "USD", "initial_strategy": {}, "optimized_strategy": {"is_optimized": False}, "response_models": {}}
        (operation.directory / "outputs/campaign_strategy.json").write_text(json.dumps(artifact))
        workbench._publish_result(operation)
        operation.state = "succeeded"
        operation.append("meta", "Completed")
        self.assertFalse(workbench.get_run(run["id"])["result"]["optimized_strategy"]["is_optimized"])
        self.assertTrue(workbench.run_artifact_path(run["id"], "campaign_strategy.json").is_file())
        (operation.directory / "outputs/campaign_strategy.json").write_text("{}")
        with self.assertRaises(workbench.WorkbenchError):
            workbench.run_artifact_path(run["id"], "campaign_strategy.json")
        second = self.start()
        op2 = workbench._operations[second["id"]]
        with self.assertRaises(FileNotFoundError):
            workbench._publish_result(op2)
        self.assertNotIn("result", workbench.get_run(second["id"]))

    def test_plan_revision_conflict_and_frozen_run_options(self):
        payload = {"name": "Monthly", "datasetId": self.descriptor["id"], "totalBudget": 100, "budgetUsagePolicy": "SPEND_FULL_BUDGET"}
        first = workbench.create_plan(payload)
        second = workbench.update_plan(first["id"], {**payload, "revision": 1, "totalBudget": 200})
        self.assertEqual(2, second["revision"])
        self.assertEqual(100, workbench.get_plan(first["id"], 1)["totalBudget"])
        with self.assertRaises(workbench.WorkbenchError) as error:
            workbench.update_plan(first["id"], {**payload, "revision": 1})
        self.assertEqual(409, error.exception.status)
        run = workbench.start_run({"datasetId": self.descriptor["id"], "stage": "optimization", "planId": first["id"], "revision": 1, "totalBudget": 999})
        self.assertEqual(100, run["options"]["totalBudget"])
        self.assertEqual(1, run["revision"])

    def test_plan_invalid_numbers_and_dataset_retarget_are_rejected(self):
        payload = {"name": "P", "datasetId": self.descriptor["id"], "totalBudget": 100, "budgetUsagePolicy": "SPEND_UP_TO_BUDGET"}
        for number in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(number=number), self.assertRaises(workbench.WorkbenchError):
                workbench.create_plan({**payload, "totalBudget": number})
        saved = workbench.create_plan(payload)
        with self.assertRaises(workbench.WorkbenchError):
            workbench.update_plan(saved["id"], {**payload, "revision": 1, "datasetId": "ds_" + "b" * 32})

    def test_evaluation_requires_matching_completed_target(self):
        run = self.start()
        payload = {"stage": "evaluation", "datasetId": self.descriptor["id"], "strategyRunId": run["id"]}
        with self.assertRaises(workbench.WorkbenchError):
            workbench.start_run(payload)
        operation = workbench._operations[run["id"]]
        artifact = {"currency": "USD", "initial_strategy": {}, "optimized_strategy": {}, "response_models": {}}
        (operation.directory / "outputs/campaign_strategy.json").write_text(json.dumps(artifact))
        workbench._publish_result(operation)
        operation.state = "succeeded"; operation.append("meta", "Completed")
        self.descriptor["digest"] = "different"
        with self.assertRaises(workbench.WorkbenchError):
            workbench.start_run(payload)
        self.descriptor["digest"] = "first-digest"
        evaluation = workbench.start_run(payload)
        op = workbench._operations[evaluation["id"]]
        self.assertIn("--source-kind", op.args)
        self.assertIn("observed", op.args)
        self.assertFalse((op.directory / "inputs/initial_budget_recommendation.json").exists())
        self.assertEqual(run["id"], evaluation["strategyRunId"])


class RealWorkbenchTests(unittest.TestCase):
    """Exercise registered inputs with the actual attribution command."""

    def test_registered_attribution_runs_and_retains_native_results(self):
        from backend.services import datasets
        from backend.tests.test_datasets import envelope
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = ControlledQueue()
            with patch.object(datasets, "pipeline_output_directory", return_value=root), patch.object(workbench, "pipeline_output_directory", return_value=root), patch.object(workbench, "pipeline_runs_enabled", return_value=True), patch.object(workbench, "is_hosted", return_value=False), patch.object(workbench, "manager", queue):
                payload = envelope()
                payload["performance"][0]["impressions"] = 0
                dataset = datasets.register_dataset(payload)
                run = workbench.start_run({"datasetId": dataset["id"], "stage": "attribution"})
                operation, execute = queue.entries[run["taskId"]]
                execute()
                completed = workbench.get_run(run["id"])
                self.assertEqual("succeeded", completed["state"], completed.get("logs"))
                self.assertEqual(5, len(completed["artifacts"]))
                self.assertEqual(2, len(completed["result"]["attributionResults"]))
                self.assertNotIn(str(root), json.dumps(completed))
                self.assertTrue(workbench.latest_result(dataset["id"], "attribution")["comparisonSummary"])

    def test_routes_share_errors_and_expose_runtime_capabilities(self):
        from flask import Flask
        from backend.api.workbench import blueprint
        app = Flask(__name__); app.register_blueprint(blueprint)
        client = app.test_client()
        self.assertEqual(400, client.post("/api/workbench/plans", json=[]).status_code)
        with patch.object(workbench, "pipeline_runs_enabled", return_value=False):
            self.assertEqual(403, client.post("/api/workbench/runs", json={"stage": "attribution"}).status_code)
        with patch("backend.api.workbench.pipeline_output_directory", return_value=None):
            response = client.get("/api/workbench/runs").get_json()
            self.assertEqual([], response["runs"])
            self.assertFalse(response["storageAvailable"])

    def test_registered_optimization_and_evaluation_use_the_same_inputs(self):
        from backend.services import datasets
        from backend.tests.test_datasets import envelope
        from modules.mta_standard.tests.test_mta_sim_research_adapter import _snapshot_payload
        payload = envelope()
        research = _snapshot_payload()
        # Four distinct ordinary periods provide actual response support;
        # simulator-only outcomes are not part of the model-facing fixture.
        research["evaluation_outcome_observations"] = []
        research["touchpoint_observations"] = []
        research["data_lineage"] = []
        original = copy.deepcopy(research)
        payload["performance"] = []
        for role in ("budget_observations", "delivery_observations", "outcome_observations"):
            research[role] = []
        for i, (budget, spend, revenue) in enumerate(((50, 40, 100), (100, 70, 160), (150, 85, 200), (200, 95, 220)), 1):
            day = f"2025-01-{i:02}"
            payload["performance"].append({**envelope()["performance"][0], "reportDate": day, "impressions": 0})
            for role in ("budget_observations", "delivery_observations", "outcome_observations"):
                row = copy.deepcopy(original[role][0])
                row["reporting_scope"].update(report_start_date=day, report_end_date=day)
                row["budget_level"] = budget / 100
                if role == "budget_observations": row.update(configured_budget=budget, actual_spend=spend)
                elif role == "delivery_observations": row.update(cost=spend, reported_sales=revenue)
                else: row.update(total_revenue=revenue)
                research[role].append(row)
        payload["research"] = research
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); queue = ControlledQueue()
            with patch.object(datasets, "pipeline_output_directory", return_value=root), patch.object(workbench, "pipeline_output_directory", return_value=root), patch.object(workbench, "pipeline_runs_enabled", return_value=True), patch.object(workbench, "is_hosted", return_value=False), patch.object(workbench, "manager", queue):
                dataset = datasets.register_dataset(payload)
                self.assertTrue(dataset["capabilities"]["optimization"]["available"])
                plan = workbench.create_plan({"name": "Budget", "datasetId": dataset["id"], "totalBudget": 100, "budgetUsagePolicy": "SPEND_FULL_BUDGET"})
                run = workbench.start_run({"datasetId": dataset["id"], "stage": "optimization", "planId": plan["id"], "revision": 1})
                queue.entries[run["taskId"]][1]()
                optimized = workbench.get_run(run["id"])
                self.assertEqual("succeeded", optimized["state"], optimized["logs"])
                self.assertTrue(optimized["result"]["optimized_strategy"]["is_optimized"])
                evaluation = workbench.start_run({"datasetId": dataset["id"], "stage": "evaluation", "strategyRunId": run["id"]})
                queue.entries[evaluation["taskId"]][1]()
                evaluated = workbench.get_run(evaluation["id"])
                self.assertEqual("succeeded", evaluated["state"], evaluated["logs"])
                self.assertEqual(1, evaluated["result"]["summary"]["projected"])
                self.assertNotIn(str(root), json.dumps(evaluated))
                self.assertIn('"is_synthetic": false', json.dumps(evaluated["result"]))
                self.assertNotIn(str(root), workbench.run_artifact_path(evaluation["id"], "strategy_evaluation.json").read_text())


if __name__ == "__main__":
    unittest.main()
