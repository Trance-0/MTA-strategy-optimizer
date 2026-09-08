"""Persist dataset-bound plans and execute isolated model runs.

Validated registered observations are frozen before the shared worker queue;
only complete validated outputs become readable results. Runtime metadata is
independent of transient task objects and can be reconstructed after restart.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import REPO_ROOT, is_hosted, pipeline_output_directory, pipeline_runs_enabled
from backend.services.jobs import STAGES
from backend.services.model_outputs import ARTIFACTS, _validate_document
from backend.services.tasks import ACTIVE_STATES, manager
from modules.mta_common.src.enums import BudgetUsagePolicy
from modules.mta_standard.src.dataloader import MTA_SIM_ADS_FIELDS, MTA_SIM_PATH_REPORT_FIELDS
from modules.mta_standard.src.mta_sim_generator_adapter import prepare_single_scope_path_report


_lock = threading.RLock()
_operations: dict[str, "RunOperation"] = {}
_recovery_failures: dict[Path, dict] = {}
MAX_LOG_LINES = 200


class WorkbenchError(ValueError):
    """Carry a bounded public failure and its transport status."""

    def __init__(self, message: str, *, status: int = 400, code: str = "invalid_workbench_request"):
        super().__init__(message)
        self.status = status
        self.code = code


def get_dataset(identifier: str) -> dict:
    """Resolve the dataset service lazily to keep runtime boundaries separate."""
    from backend.services.datasets import get_dataset as read
    return read(identifier)


def dataset_inputs(identifier: str) -> dict:
    """Read validated native inputs without consulting legacy fallbacks."""
    from backend.services.datasets import dataset_inputs as read
    return read(identifier)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root() -> Path:
    root = pipeline_output_directory()
    if root is None:
        raise WorkbenchError("Configure writable runtime storage before using the workbench.", status=503, code="runtime_unavailable")
    return root / "workbench"


def _directory(kind: str, identifier: str) -> Path:
    prefix = "run" if kind == "runs" else "plan"
    if not isinstance(identifier, str) or not re.fullmatch(prefix + r"_[0-9a-f]{32}", identifier):
        raise WorkbenchError("Unknown workbench identifier.", status=404, code="not_found")
    return _root() / kind / identifier


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise WorkbenchError("The requested workbench record does not exist.", status=404, code="not_found") from None
    except (OSError, ValueError):
        raise WorkbenchError("The saved workbench record could not be read.", status=503, code="record_unavailable") from None
    if not isinstance(value, dict):
        raise WorkbenchError("The saved workbench record is invalid.", status=503, code="record_unavailable")
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        pending.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n", encoding="utf-8")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def _scrub(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {key: _scrub(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item, root) for item in value]
    if isinstance(value, str):
        return value.replace(str(root), "<runtime>").replace(str(REPO_ROOT), "<project>")
    return value


def _options(body: dict, stage: str) -> dict:
    nested = body.get("options", {})
    if not isinstance(nested, dict):
        raise WorkbenchError("options must be an object.")
    allowed = {"totalBudget", "budgetUsagePolicy"} if stage == "optimization" else set()
    if set(nested) - allowed:
        raise WorkbenchError("The selected stage does not support these options.")
    selected = dict(nested)
    for key in ("totalBudget", "budgetUsagePolicy"):
        if key in body:
            if key not in allowed:
                raise WorkbenchError("Budget options require the optimization stage.")
            if key in selected and selected[key] != body[key]:
                raise WorkbenchError(f"Conflicting {key} values.")
            selected[key] = body[key]
    if "totalBudget" in selected:
        value = selected["totalBudget"]
        try:
            number = float(value)
        except (ValueError, TypeError, OverflowError):
            number = float("nan")
        if isinstance(value, bool) or not math.isfinite(number) or number <= 0:
            raise WorkbenchError("totalBudget must be a finite positive number.")
        selected["totalBudget"] = number
    if "budgetUsagePolicy" in selected:
        if not isinstance(selected["budgetUsagePolicy"], str) or selected["budgetUsagePolicy"] not in {item.value for item in BudgetUsagePolicy}:
            raise WorkbenchError("budgetUsagePolicy is not a supported policy.")
    return selected


def _csv(path: Path, fields, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _plan_fields(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise WorkbenchError("A plan request must be an object.")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise WorkbenchError("Plan name must contain between 1 and 200 characters.")
    options = _options(payload, "optimization")
    if set(options) != {"totalBudget", "budgetUsagePolicy"}:
        raise WorkbenchError("A saved plan requires totalBudget and budgetUsagePolicy.")
    dataset = get_dataset(payload.get("datasetId"))
    return {"name": name.strip(), "datasetId": dataset["id"], **options}


def create_plan(payload: dict) -> dict:
    fields = _plan_fields(payload)
    identifier = "plan_" + uuid.uuid4().hex
    now = _now()
    plan = {"id": identifier, "revision": 1, "createdAt": now, "updatedAt": now, **fields}
    with _lock:
        directory = _directory("plans", identifier)
        try:
            _write(directory / "revisions/1.json", plan)
            _write(directory / "plan.json", plan)
        except OSError:
            shutil.rmtree(directory, ignore_errors=True)
            raise
    return copy.deepcopy(plan)


def _revision(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise WorkbenchError("revision must be a positive integer.")
    return value


def get_plan(identifier: str, revision: int | None = None) -> dict:
    with _lock:
        directory = _directory("plans", identifier)
        current = _read(directory / "plan.json")
        if revision is None:
            return current
        selected = _revision(revision)
        if selected > current["revision"]:
            raise WorkbenchError("The requested plan revision does not exist.", status=404)
        return _read(directory / "revisions" / f"{selected}.json")


def update_plan(identifier: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise WorkbenchError("A plan update must be an object.")
    expected = _revision(payload.get("revision"))
    with _lock:
        current = get_plan(identifier)
        if expected != current["revision"]:
            raise WorkbenchError("The plan changed. Reload latest before saving another revision.", status=409, code="revision_conflict")
        if payload.get("datasetId", current["datasetId"]) != current["datasetId"]:
            raise WorkbenchError("A saved plan cannot be moved to another dataset.", status=409, code="dataset_conflict")
        fields = _plan_fields({**current, **payload})
        plan = {**current, **fields, "revision": expected + 1, "updatedAt": _now()}
        directory = _directory("plans", identifier)
        revision_file = directory / "revisions" / f"{plan['revision']}.json"
        _write(revision_file, plan)
        try:
            _write(directory / "plan.json", plan)
        except OSError:
            revision_file.unlink(missing_ok=True)
            raise
        return copy.deepcopy(plan)


def list_plans(dataset_id: str | None = None) -> list[dict]:
    if dataset_id is not None:
        get_dataset(dataset_id)
    with _lock:
        rows = [_read(path) for path in (_root() / "plans").glob("plan_*/plan.json")]
        rows = [row for row in rows if dataset_id is None or row["datasetId"] == dataset_id]
        return sorted(rows, key=lambda row: (row["createdAt"], row["id"]), reverse=True)


def _prepare(record: dict, directory: Path, inputs: dict) -> list[str]:
    """Freeze native data and construct shell-free package command arguments."""
    source = directory / "inputs"
    output = directory / "outputs"
    source.mkdir(parents=True)
    output.mkdir()
    stage = record["stage"]
    module = STAGES[stage]["script"].removesuffix(".py").replace("/", ".")
    args = [sys.executable, "-X", "utf8", "-B", "-m", module]
    if stage == "attribution":
        performance = source / "amazon_ads_daily_touchpoint_performance.csv"
        paths = source / "amc_path_report.csv"
        _csv(performance, MTA_SIM_ADS_FIELDS, inputs["performance"])
        _csv(paths, MTA_SIM_PATH_REPORT_FIELDS, inputs["paths"])
        model_paths = prepare_single_scope_path_report(paths, performance, source / "model_paths.csv")
        return args + ["--amc-report", str(model_paths), "--amazon-ads-report", str(performance), "--output-dir", str(output)]
    if inputs.get("research") is not None:
        _write(source / "simulation_research.json", inputs["research"])
    if stage == "optimization":
        args += ["--research-snapshot", str(source / "simulation_research.json"), "--marketplace", record["scope"]["marketplace"], "--output", str(output / "campaign_strategy.json")]
        for key, flag in (("totalBudget", "--total-budget"), ("budgetUsagePolicy", "--budget-usage-policy")):
            if key in record["options"]:
                args += [flag, str(record["options"][key])]
        return args
    target = record["strategyRunId"]
    strategy = run_artifact_path(target, "campaign_strategy.json")
    shutil.copyfile(strategy, source / "campaign_strategy.json")
    currency = _read(source / "campaign_strategy.json").get("currency")
    if currency != record["scope"]["currency"]:
        raise WorkbenchError("The target strategy currency does not match this dataset.", status=409, code="dataset_conflict")
    args += ["--strategy-directory", str(source), "--output", str(output / "strategy_evaluation.json"),
             "--source-kind", "synthetic" if record["isSynthetic"] else "observed",
             "--currency", currency, "--advertiser-id", record["scope"]["advertiserId"],
             "--marketplace", record["scope"]["marketplace"]]
    if inputs.get("research") is not None:
        args += ["--research-snapshot", str(source / "simulation_research.json")]
    return args


class RunOperation:
    """Bridge TaskManager's transition protocol to a durable run record."""

    def __init__(self, record: dict, directory: Path, args: list[str]):
        self.record = record
        self.directory = directory
        self.args = args
        self.state = record["state"]
        self.percent = 0
        self.phase = "Waiting to start"
        self.started_at = None
        self.finished_at = None
        self.process = None
        self.error = None

    def append(self, stream: str, text: str) -> None:
        # TaskManager mutates attributes before each append, so this records
        # admission, queued cancellation and exception transitions too.
        with _lock:
            for line in str(text).splitlines():
                safe = _scrub(line, self.directory.parents[1])[:500]
                if not safe:
                    continue
                self.record.setdefault("logs", []).append({"at": _now(), "stream": stream, "text": safe})
                for at, pattern, label in STAGES[self.record["stage"]]["phases"]:
                    if at > self.percent and pattern.search(line):
                        self.percent, self.phase = at, label
            self.record["logs"] = self.record.get("logs", [])[-MAX_LOG_LINES:]
            self.record.update(state=self.state, percent=self.percent, phase=self.phase, startedAt=self.started_at, finishedAt=self.finished_at, error=_scrub(self.error, self.directory.parents[1]))
            _write(self.directory / "run.json", self.record)
            if self.state not in ACTIVE_STATES:
                _operations.pop(self.record["id"], None)

    def public_view(self) -> dict:
        return copy.deepcopy(self.record)


def start_run(payload: dict) -> dict:
    """Validate and freeze one independent run before queue admission."""
    if is_hosted() or not pipeline_runs_enabled():
        raise WorkbenchError("Model execution is disabled on this server.", status=403, code="pipeline_disabled")
    recovery_error = recovery_storage_error()
    if recovery_error:
        raise WorkbenchError(recovery_error, status=503, code="runtime_unavailable")
    if not isinstance(payload, dict):
        raise WorkbenchError("A run request must be an object.")
    stage = payload.get("stage")
    if not isinstance(stage, str) or stage not in STAGES:
        raise WorkbenchError("Unknown model stage.")
    dataset = get_dataset(payload.get("datasetId"))
    capability = dataset.get("capabilities", {}).get(stage, {})
    if stage != "evaluation" and not capability.get("available"):
        raise WorkbenchError(capability.get("reason") or "This dataset does not support the stage.", status=409, code="insufficient_evidence")
    plan = None
    if payload.get("planId"):
        if stage != "optimization":
            raise WorkbenchError("Budget plans can only start optimization.")
        plan = get_plan(payload["planId"], _revision(payload.get("revision")))
        if plan["datasetId"] != dataset["id"]:
            raise WorkbenchError("The saved plan belongs to another dataset.", status=409, code="dataset_conflict")
        options = {key: plan[key] for key in ("totalBudget", "budgetUsagePolicy")}
    else:
        if payload.get("revision") is not None:
            raise WorkbenchError("revision requires a planId.")
        options = _options(payload, stage)
    identifier = "run_" + uuid.uuid4().hex
    directory = _directory("runs", identifier)
    record = {"id": identifier, "datasetId": dataset["id"], "datasetDigest": dataset["digest"], "datasetName": dataset["name"], "scope": dataset["scope"], "isSynthetic": dataset.get("isSynthetic", False), "stage": stage, "model": STAGES[stage]["label"], "options": options, "planId": None, "revision": None, "strategyRunId": None, "createdAt": _now(), "startedAt": None, "finishedAt": None, "state": "queued", "percent": 0, "phase": "Preparing inputs", "taskId": None, "logs": [], "artifacts": []}
    if plan:
        record.update(planId=plan["id"], revision=plan["revision"])
    if stage == "evaluation":
        target = get_run(payload.get("strategyRunId"))
        if target["stage"] != "optimization" or target["state"] != "succeeded" or not target.get("artifacts"):
            raise WorkbenchError("Select a completed optimization run for evaluation.", status=409, code="strategy_unavailable")
        if target["datasetId"] != dataset["id"] or target["datasetDigest"] != dataset["digest"]:
            raise WorkbenchError("The target strategy belongs to another dataset or input fingerprint.", status=409, code="dataset_conflict")
        record["strategyRunId"] = target["id"]
    try:
        args = _prepare(record, directory, dataset_inputs(dataset["id"]))
    except (OSError, ValueError, KeyError, TypeError) as error:
        shutil.rmtree(directory, ignore_errors=True)
        if isinstance(error, WorkbenchError):
            raise
        raise WorkbenchError("Could not prepare this dataset for the selected model.") from error
    operation = RunOperation(record, directory, args)
    with _lock:
        _operations[identifier] = operation
        operation.append("meta", "Validated inputs frozen for the selected dataset.")
    # Do not hold the service lock while entering the manager's queue lock.
    try:
        task_id = manager.submit(operation, kind="model", action=stage, label=STAGES[stage]["label"], summary={"runId": identifier, "datasetId": dataset["id"]}, runner=lambda: _execute(operation))
    except Exception:
        operation.state = "failed"
        operation.phase = "Queue admission failed"
        operation.finished_at = _now()
        operation.append("stderr", operation.phase)
        raise WorkbenchError("The run could not enter the operator queue.", status=503, code="queue_unavailable") from None
    with _lock:
        record["taskId"] = task_id
        operation.append("meta", "Run linked to the operator queue.")
    return get_run(identifier)


def _execute(operation: RunOperation) -> None:
    """Run a package command and publish only its validated complete result."""
    with _lock:
        if operation.state in {"stopped", "stopping"}:
            operation.state = "stopped"
            operation.finished_at = _now()
            operation.append("queue", "Stopped before model execution.")
            return
        operation.state = "running"
        operation.started_at = operation.started_at or _now()
        operation.process = subprocess.Popen(operation.args, cwd=REPO_ROOT, env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False)
        operation.append("meta", "Model process started.")
    process = operation.process
    try:
        assert process.stdout is not None
        for line in process.stdout:
            operation.append("stdout", line)
        returncode = process.wait()
        with _lock:
            if operation.state in {"stopped", "stopping"}:
                operation.state = "stopped"
                operation.phase = "Stopped"
            elif returncode:
                operation.state = "failed"
                operation.phase = "Failed"
                operation.error = f"Model exited with code {returncode}; inspect the run log."
            else:
                _publish_result(operation)
                operation.state = "succeeded"
                operation.percent = 100
                operation.phase = "Complete"
            operation.finished_at = _now()
            operation.append("meta", operation.phase)
    finally:
        if process.stdout is not None:
            process.stdout.close()


def _publish_result(operation: RunOperation) -> None:
    stage = operation.record["stage"]
    output = operation.directory / "outputs"
    artifacts = []
    for name, mime, fields in ARTIFACTS[stage]:
        path = output / name
        text = path.read_text(encoding="utf-8")
        if fields is None:
            # Model diagnostics may name the private input directory. Strip
            # those locations from both download and parsed public result.
            parsed = json.loads(text)
            cleaned = _scrub(parsed, operation.directory.parents[1])
            if parsed != cleaned:
                _write(path, cleaned)
                text = path.read_text(encoding="utf-8")
        _validate_document(stage, name, text, fields)
        artifacts.append({"name": name, "mimeType": mime, "digest": hashlib.sha256(path.read_bytes()).hexdigest()})
    if stage == "attribution":
        result = _parse_attribution(output)
    else:
        result = _read(output / ARTIFACTS[stage][0][0])
    result = _scrub(result, operation.directory.parents[1])
    _write(operation.directory / "result.json", result)
    operation.record["artifacts"] = artifacts


def _parse_attribution(output: Path) -> dict:
    # Reuse only field constants and pure coercions; legacy loader entry points
    # can restore unrelated files and must never execute in registered context.
    from backend.repository import attribution as shape
    from backend.repository.coercion import boolean, dates, numeric, project, read_csv, split_touchpoint
    rows = read_csv(output / "amc_markov_attribution_results.csv") + read_csv(output / "amc_shapley_attribution_results.csv")
    result = {"attributionResults": project(numeric(split_touchpoint(rows), shape.ATTRIBUTION_NUMERIC), shape.ATTRIBUTION_FIELDS)}
    for key, filename, fields, numbers in (
        ("comparisonTouchpoints", "amc_mta_model_comparison_touchpoints.csv", shape.COMPARISON_FIELDS, shape.COMPARISON_NUMERIC),
        ("comparisonSummary", "amc_mta_model_comparison_summary.csv", shape.SUMMARY_FIELDS, shape.SUMMARY_NUMERIC),
        ("recommendedAttribution", "amc_mta_recommended_attribution.csv", shape.RECOMMENDED_FIELDS, shape.RECOMMENDED_NUMERIC),
    ):
        rows = boolean(dates(numeric(split_touchpoint(read_csv(output / filename)), numbers)))
        result[key] = project(rows, fields)
    return result


def get_run(identifier: str) -> dict:
    with _lock:
        directory = _directory("runs", identifier)
        record = _read_run(directory / "run.json")
        if record["state"] == "succeeded" and record.get("artifacts"):
            record["result"] = _read(directory / "result.json")
        return record


def list_runs(dataset_id: str | None = None) -> list[dict]:
    if dataset_id is not None:
        get_dataset(dataset_id)
    with _lock:
        root = _root() / "runs"
        records = []
        for path in root.glob("run_*/run.json"):
            record = _read_run(path)
            if dataset_id is None or record["datasetId"] == dataset_id:
                records.append(record)
        return sorted(records, key=lambda row: (row["createdAt"], row["id"]), reverse=True)


def latest_run(dataset_id: str, stage: str) -> dict | None:
    dataset = get_dataset(dataset_id)
    for record in list_runs(dataset_id):
        if record["stage"] == stage and record["datasetDigest"] == dataset["digest"] and record["state"] == "succeeded" and record.get("artifacts"):
            return get_run(record["id"])
    return None


def latest_result(dataset_id: str, stage: str) -> dict:
    record = latest_run(dataset_id, stage)
    return record.get("result", {}) if record else {}


def stop_run(identifier: str) -> dict:
    record = get_run(identifier)
    if record["state"] not in ACTIVE_STATES:
        raise WorkbenchError("This run is no longer active.", status=409, code="run_not_active")
    operation = _operations.get(identifier)
    if operation is None:
        recover_runs()
        return get_run(identifier)
    with _lock:
        if operation.state == "running" and operation.process is None:
            operation.state = "stopping"
            operation.append("meta", "Stop requested before process startup.")
            return get_run(identifier)
    result = manager.stop(record["taskId"])
    if result in {"missing", "terminal"}:
        raise WorkbenchError("The run cannot be stopped in its current state.", status=409, code="run_not_active")
    return get_run(identifier)


def _read_run(path: Path) -> dict:
    """Keep failed recovery writes visible without claiming they persisted."""
    return copy.deepcopy(_recovery_failures[path]) if path in _recovery_failures else _read(path)


def recovery_storage_error() -> str | None:
    root = pipeline_output_directory()
    if root is not None:
        with _lock:
            if any(path.is_relative_to(root / "workbench/runs") for path in _recovery_failures):
                return "Interrupted run recovery could not be saved. Repair runtime storage and restart the backend."
    return None


def recover_runs() -> None:
    if pipeline_output_directory() is None:
        return
    with _lock:
        for path in (_root() / "runs").glob("run_*/run.json"):
            try:
                record = _read(path)
            except WorkbenchError:
                # A damaged history record must not prevent Settings/health
                # from starting; an explicit history read still reports it.
                continue
            if record.get("id") != path.parent.name:
                continue
            if record.get("state") in ACTIVE_STATES and record["id"] not in _operations:
                record.update(state="interrupted", phase="Interrupted by backend restart", finishedAt=_now(), artifacts=[])
                try:
                    _write(path, record)
                except OSError:
                    # Startup must preserve access to Settings while keeping
                    # the uncommitted transition explicit in every run read.
                    _recovery_failures[path] = {**record, "recoveryPersisted": False,
                        "recoveryError": "Interrupted run recovery could not be saved to runtime storage."}
                    continue
            _recovery_failures.pop(path, None)


def run_artifact_path(identifier: str, filename: str) -> Path:
    record = get_run(identifier)
    descriptor = next((row for row in record.get("artifacts", []) if row["name"] == filename), None)
    if record["state"] != "succeeded" or descriptor is None or Path(filename).name != filename:
        raise WorkbenchError("This completed artifact is unavailable.", status=404, code="artifact_not_found")
    path = _directory("runs", identifier) / "outputs" / filename
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != descriptor["digest"]:
        raise WorkbenchError("The completed artifact no longer matches its recorded content.", status=409, code="artifact_changed")
    return path
