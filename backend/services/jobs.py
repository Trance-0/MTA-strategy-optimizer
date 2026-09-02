"""Run a pipeline stage as a child process and stream its progress back.

The three model stages already exist as command-line scripts. This module runs
one of those, exactly as the documented command would, and keeps its output
where the client can poll it. It does not reimplement any stage: a run started
here and a run started in a terminal execute the same script with the same
arguments, so the dashboard cannot drift from the pipeline it reports on, and
the command is shown verbatim so a reader can reproduce it.

Why a poll rather than a socket: the runs are minutes rather than
milliseconds, and a dropped connection during a five-minute fit should not
abandon the run. The job outlives the request that started it.

Running a stage writes files under `modules/`, so it is refused wherever the
deployment is read-only, and refused before anything is spawned so a refusal
never leaves a half-started run behind.

Data flow:
    POST /api/jobs/<stage> -> here -> python script/&#42;.py -> modules/&#42;/outputs
    GET  /api/jobs         -> here -> the Campaign Optimizer's log tabs
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.exc import SQLAlchemyError

from backend.config import (
    ATTRIBUTION_OUTPUT_DIR,
    REPO_ROOT,
    pipeline_output_directory,
)
from backend.services.model_datasets import (
    DatasetError,
    PreparedDataset,
    datasets_for,
    prepare_dataset,
    resolve_dataset,
)
from backend.services.model_outputs import (
    ArtifactError,
    artifact_manifest,
    restore_artifact_directory,
)
from backend.services.tasks import ACTIVE_STATES, manager, stop_task

_STRATEGY_OUTPUT_DIR = REPO_ROOT / "modules" / "mta_strategy_recommendation" / "outputs"

#: How many output lines one run keeps. A fit over a research-scale snapshot
#: can print thousands; the reader wants the shape of the run and its tail, and
#: an unbounded buffer in a long-lived server process is a leak. The count of
#: dropped lines is reported rather than hidden, so a truncated log never reads
#: as a complete one.
MAX_LINES = 600

#: Completed runs kept for inspection after they finish.
MAX_HISTORY = 6

#: The three dashboard-runnable model stages, in pipeline order. Each names
#: the script it runs and the
#: phases it passes through. The phases are matched against the script's own
#: standard output to advance the progress bar: a stage reports where it
#: actually is rather than against a timer, so a slow fit shows as a slow phase
#: instead of a bar that reaches 90% and stops.
STAGES: dict[str, dict[str, Any]] = {
    "attribution": {
        "label": "MTA attribution",
        "script": "script/run_attribution_models.py",
        "phases": [
            (
                8,
                re.compile(r"aggregated path report", re.I),
                "Building the aggregated path report",
            ),
            (
                30,
                re.compile(r"Markov removal-effect", re.I),
                "Running Markov removal-effect attribution",
            ),
            (
                55,
                re.compile(r"Shapley", re.I),
                "Running path-level Shapley attribution",
            ),
            (
                80,
                re.compile(r"Comparing models", re.I),
                "Comparing models and judging reliability",
            ),
            (
                92,
                re.compile(r"Publishing the attribution outputs", re.I),
                "Publishing the attribution outputs",
            ),
        ],
    },
    "optimization": {
        "label": "MTA strategy optimization",
        "script": "script/generate_campaign_strategy.py",
        "phases": [
            (
                10,
                re.compile(r"load|snapshot", re.I),
                "Loading Campaign budget observations",
            ),
            (
                35,
                re.compile(r"dataset|observation", re.I),
                "Building the response dataset",
            ),
            (
                60,
                re.compile(r"fit|model", re.I),
                "Fitting budget-to-spend and spend-to-revenue curves",
            ),
            (
                85,
                re.compile(r"optimi|allocat|solver", re.I),
                "Equalizing marginal return across Campaigns",
            ),
            (95, re.compile(r"wrote|written", re.I), "Writing the optimized strategy"),
        ],
    },
    "evaluation": {
        "label": "MTA strategy evaluation",
        "script": "script/evaluate_strategies.py",
        "phases": [
            (
                10,
                re.compile(r"projecting strategies", re.I),
                "Projecting strategy artifacts",
            ),
            (
                35,
                re.compile(r"checking conservation", re.I),
                "Checking allocation conservation",
            ),
            (
                60,
                re.compile(r"comparing against baselines", re.I),
                "Comparing strategies against baselines",
            ),
            (
                80,
                re.compile(r"fitting the contributed model", re.I),
                "Fitting the contributed model",
            ),
            (
                95,
                re.compile(r"writing the artifact", re.I),
                "Writing the strategy evaluation",
            ),
        ],
    },
}

STAGE_KEYS: tuple[str, ...] = tuple(STAGES)

#: Exactly the values `BudgetUsagePolicy` declares in
#: modules/mta_common/src/enums.py. Anything else would reach argparse's
#: `choices` and fail the run after it had already started.
BUDGET_USAGE_POLICIES = ("SPEND_FULL_BUDGET", "SPEND_UP_TO_BUDGET")

_running: dict[str, "Job"] = {}
_history: list["Job"] = []
_lock = threading.Lock()
_next_id = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OptionError(ValueError):
    """A run option the command line must never see, with the complaint."""


def normalize_options(body: dict | None = None) -> dict:
    """Validate what the client asked for, or raise with the specific complaint.

    Rejecting here rather than at the command line is what keeps an unchecked
    string out of the argument vector.
    """
    body = body or {}
    options: dict[str, Any] = {}

    dataset_id = str(body.get("datasetId") or "").strip()
    if not dataset_id:
        raise OptionError("datasetId is required for every model run.")
    options["datasetId"] = dataset_id

    total_budget = body.get("totalBudget")
    if total_budget not in (None, ""):
        try:
            budget = float(total_budget)
        except (TypeError, ValueError):
            raise OptionError("totalBudget must be a positive number.") from None
        if budget != budget or budget in (float("inf"), float("-inf")) or budget <= 0:
            raise OptionError("totalBudget must be a positive number.")
        options["totalBudget"] = budget

    policy = str(body.get("budgetUsagePolicy") or "").strip()
    if policy != "":
        if policy not in BUDGET_USAGE_POLICIES:
            raise OptionError("budgetUsagePolicy is not a recognized policy.")
        options["budgetUsagePolicy"] = policy

    return options


def arguments_for(
    stage: str, options: dict, prepared: PreparedDataset | None = None
) -> list[str]:
    """Build the argument vector for a stage.

    The dataset paths come only from ``prepare_dataset``. Browser values never
    become paths or query fragments in the argument vector.
    """
    runtime = pipeline_output_directory()
    script = script_for(stage)
    if prepared is None:
        raise DatasetError("A prepared server dataset is required.")
    args = [sys.executable, "-X", "utf8", "-B", script]
    if stage == "attribution":
        args += [
            "--amc-report",
            str(prepared.path_report),
            "--amazon-ads-report",
            str(prepared.performance_report),
        ]
        args += ["--output-dir", str(_attribution_output_directory())]
    if stage == "optimization":
        args += ["--research-snapshot", str(prepared.research_snapshot)]
        args += ["--marketplace", prepared.marketplace]
        if runtime is not None:
            args += ["--output", str(runtime / "strategy" / "campaign_strategy.json")]
        if options.get("totalBudget"):
            args += ["--total-budget", str(options["totalBudget"])]
        if options.get("budgetUsagePolicy"):
            args += ["--budget-usage-policy", options["budgetUsagePolicy"]]
    if stage == "evaluation" and runtime is not None:
        args += [
            "--strategy-directory",
            str(runtime / "strategy"),
            "--output",
            str(runtime / "evaluation" / "strategy_evaluation.json"),
        ]
        if prepared.research_snapshot is not None:
            args += ["--research-snapshot", str(prepared.research_snapshot)]
            args += ["--marketplace", prepared.marketplace]
    return args


def _attribution_output_directory():
    """Writable attribution root for this deployment."""
    runtime = pipeline_output_directory()
    return runtime / "attribution" if runtime else ATTRIBUTION_OUTPUT_DIR


def script_for(stage: str) -> str | None:
    """The command entry point this deployment will actually execute."""
    return STAGES[stage]["script"]


def prepare_runtime_inputs(stage: str, *, database_enabled: bool = True) -> None:
    """Create isolated output folders and seed evaluation's strategy inputs."""
    runtime = pipeline_output_directory()
    if runtime is not None:
        (runtime / "attribution").mkdir(parents=True, exist_ok=True)
        (runtime / "strategy").mkdir(parents=True, exist_ok=True)
        (runtime / "evaluation").mkdir(parents=True, exist_ok=True)
    if runtime is None:
        return
    if stage != "evaluation":
        return
    if database_enabled:
        restore_artifact_directory("optimization", database_enabled=True)
    for name in ("initial_budget_recommendation.json", "campaign_strategy.json"):
        target = runtime / "strategy" / name
        if target.is_file():
            continue
        source = _STRATEGY_OUTPUT_DIR / name
        if source.is_file():
            shutil.copyfile(source, target)


class Job:
    """One run of one stage, and everything the client polls about it."""

    def __init__(self, identifier: int, stage: str, command: str) -> None:
        self.id = identifier
        self.stage = stage
        self.state = "queued"
        self.percent = 0
        self.phase = "Preparing"
        self.command = command
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.exit_code: int | None = None
        self.error: str | None = None
        self.lines: list[dict] = []
        self.dropped_lines = 0
        self.process: subprocess.Popen | None = None
        self.task_id: str | None = None

    def public_view(self) -> dict:
        """The run's public shape.

        The command is included so a reader can reproduce the run in a
        terminal, which is the point of running the real script rather than a
        reimplementation.
        """
        return {
            "id": self.id,
            "taskId": self.task_id,
            "stage": self.stage,
            "label": STAGES.get(self.stage, {}).get("label", self.stage),
            "state": self.state,
            "percent": self.percent,
            "phase": self.phase,
            "command": self.command,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "exitCode": self.exit_code,
            "error": self.error,
            "lines": list(self.lines),
            "droppedLines": self.dropped_lines,
        }

    def append(self, stream: str, text: str) -> None:
        """Record one chunk of output and advance the progress bar."""
        for raw in str(text).splitlines():
            line = raw.rstrip()
            if line == "":
                continue
            self.lines.append(
                {
                    "at": _now(),
                    "stream": stream,
                    "level": "ERROR" if stream == "stderr" else "INFO",
                    "text": line[:500],
                }
            )
            if len(self.lines) > MAX_LINES:
                overflow = len(self.lines) - MAX_LINES
                self.dropped_lines += overflow
                del self.lines[:overflow]
            self._advance(line)

    def _advance(self, line: str) -> None:
        """Move the bar to the furthest phase the output has reached.

        Monotonic by construction: a later line matching an earlier phase never
        walks the bar backwards, which a naive last-match-wins rule would do as
        soon as one stage's summary mentions a previous stage by name.
        """
        for at, pattern, message in STAGES.get(self.stage, {}).get("phases", []):
            if at > self.percent and pattern.search(line):
                self.percent = at
                self.phase = message


def active_job(stage: str) -> Job | None:
    """The run of `stage` that is still going, if any."""
    job = _running.get(stage)
    return job if job is not None and job.state in ACTIVE_STATES else None


def jobs_state(execution_enabled: bool = True, database_enabled: bool = True) -> dict:
    """Every stage's current or most recent run, plus what each stage can do.

    Returned whole rather than per stage, because the view shows three tabs at
    once and polling three endpoints to fill them would be three times the
    requests for one screen.
    """
    stages = {}
    for key in STAGE_KEYS:
        definition = STAGES[key]
        script = script_for(key)
        job = _running.get(key)
        try:
            datasets = datasets_for(key, database_enabled=database_enabled)
        except (OSError, ValueError, SQLAlchemyError):
            datasets = []
        try:
            artifacts = artifact_manifest(key, database_enabled=database_enabled)
        except (OSError, RuntimeError, ArtifactError, SQLAlchemyError):
            artifacts = {
                "files": [],
                "complete": False,
                "canUpload": False,
                "canImport": False,
            }
        available = (
            bool(script)
            and execution_enabled
            and pipeline_output_directory() is not None
            and bool(datasets)
        )
        stages[key] = {
            "key": key,
            "label": definition["label"],
            "script": script,
            "available": available,
            "unavailableReason": (
                (
                    "Pipeline execution is disabled on this server. Set "
                    "PIPELINE_RUNS_ENABLED=true in its deployment configuration."
                )
                if not execution_enabled
                else (
                    "PIPELINE_OUTPUT_DIR must name a writable runtime directory."
                    if pipeline_output_directory() is None
                    else (
                        "No compatible server-owned dataset is available for this model."
                        if not datasets
                        else definition.get("unavailableReason")
                    )
                )
            ),
            "datasets": datasets,
            "defaultDataset": datasets[0]["id"] if datasets else None,
            "current": job.public_view() if job else None,
            "artifacts": artifacts,
        }
    return {"stages": stages, "history": [job.public_view() for job in _history]}


def start_refusal(
    stage: str,
    writable: bool,
    options: dict | None = None,
    database_enabled: bool = True,
) -> dict | None:
    """Why `stage` cannot be started right now, or None when it can.

    Every reason is checked before anything is spawned, and each names the
    remedy rather than only the fault.
    """
    definition = STAGES.get(stage)
    if definition is None:
        return {"code": "unknown_stage", "message": f"Unknown stage: {stage}."}
    if not definition["script"]:
        return {"code": "stage_unavailable", "message": definition["unavailableReason"]}
    if not writable:
        return {
            "code": "runtime_unwritable",
            "message": "PIPELINE_OUTPUT_DIR must name a writable runtime directory.",
        }
    if active_job(stage) is not None:
        return {
            "code": "already_running",
            "message": f"{definition['label']} is already running.",
        }
    try:
        resolve_dataset(
            stage,
            (options or {}).get("datasetId"),
            database_enabled=database_enabled,
        )
    except DatasetError as error:
        return {
            "code": "missing_input",
            "message": str(error),
        }
    return None


def start_job(
    stage: str,
    options: dict,
    on_finish: Callable[[Job], None] | None = None,
    database_enabled: bool = True,
) -> Job:
    """Start `stage` and return its run immediately.

    The caller has already checked `start_refusal`. Preparation is synchronous
    so an invalid dataset fails immediately; the validated command then enters
    the shared single-worker queue and the client polls for the rest.
    """
    global _next_id
    with _lock:
        identifier = _next_id
        _next_id += 1
    job = Job(identifier, stage, STAGES[stage]["script"] or stage)
    _running[stage] = job

    try:
        selected = resolve_dataset(
            stage, options.get("datasetId"), database_enabled=database_enabled
        )
        prepare_runtime_inputs(stage, database_enabled=database_enabled)
        prepared = prepare_dataset(stage, selected)
        args = arguments_for(stage, options, prepared)
        job.command = " ".join(args)
        job.append("meta", f"Selected dataset: {selected['label']}")
        job.append("meta", f"$ {job.command}")
    except (OSError, ValueError, SQLAlchemyError) as error:
        _finish(
            job,
            error=(
                "Could not prepare the pipeline runtime inputs: "
                f"{type(error).__name__}: {error}"
            ),
            on_finish=on_finish,
        )
        job.task_id = manager.register_terminal(
            job,
            kind="model",
            action=stage,
            label=STAGES[stage]["label"],
            summary={"stage": stage, "datasetId": options.get("datasetId")},
        )
        return job

    summary = {
        "stage": stage,
        "datasetId": selected.get("id"),
        "dataset": selected.get("label"),
        "marketplace": selected.get("marketplace") or prepared.marketplace,
    }
    for key in ("totalBudget", "budgetUsagePolicy"):
        if key in options:
            summary[key] = options[key]

    def run() -> None:
        _run_job(job, args, on_finish)

    job.task_id = manager.submit(
        job,
        kind="model",
        action=stage,
        label=STAGES[stage]["label"],
        summary=summary,
        runner=run,
    )
    return job


def _run_job(
    job: Job,
    args: list[str],
    on_finish: Callable[[Job], None] | None,
) -> None:
    """Spawn and drain a prepared model command when the queue selects it."""
    job.phase = "Starting model command"
    job.percent = 2

    try:
        process = subprocess.Popen(  # noqa: S603 - a fixed vector, never a shell
            args,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            # `shell=False` is the default and is what keeps the arguments an
            # argument vector rather than a string a shell would re-parse.
            shell=False,
            text=True,
            bufsize=1,
            env=_child_environment(),
        )
    except FileNotFoundError:
        _finish(
            job,
            error=(
                "The server's Python interpreter could not be started. Rebuild "
                "the deployment with the project's backend dependencies."
            ),
            on_finish=on_finish,
        )
        return
    except OSError as error:
        _finish(job, error=f"{type(error).__name__}: {error}", on_finish=on_finish)
        return

    job.process = process
    job.append("meta", "Model command started; streaming output follows.")
    _drain(job, process, on_finish)


def _child_environment() -> dict:
    """The environment a stage runs under.

    Output is unbuffered and UTF-8 so a phase line reaches the reader when the
    stage begins rather than when a block buffer happens to fill.
    """
    import os

    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}


def _drain(
    job: Job, process: subprocess.Popen, on_finish: Callable[[Job], None] | None
) -> None:
    """Read the child's output to completion, then record how it ended."""
    try:
        if process.stdout is not None:
            for line in process.stdout:
                job.append("stdout", line)
    finally:
        code = process.wait()
        if job.state in {"running", "stopping"}:
            _finish(job, exit_code=code, on_finish=on_finish)


def _finish(
    job: Job,
    exit_code: int | None = None,
    error: str | None = None,
    on_finish: Callable[[Job], None] | None = None,
) -> None:
    """Record a run's outcome and retire it into the history."""
    if job.state == "stopping":
        job.state = "stopped"
    else:
        job.state = "failed" if error or exit_code != 0 else "succeeded"
    job.exit_code = exit_code
    job.error = error
    job.finished_at = _now()
    job.process = None
    if job.state == "succeeded":
        job.percent = 100
        job.phase = "Complete"
        job.append("meta", "Stage completed. Reloading the dashboard's data.")
    elif job.state == "stopped":
        job.append("meta", "Stage stopped by the operator.")
        job.phase = "Stopped"
    else:
        job.append("meta", error or f"Stage failed with exit code {exit_code}.")
        job.phase = "Failed"

    with _lock:
        _history.insert(0, job)
        del _history[MAX_HISTORY:]

    # Only a successful run changed what the dashboard reads.
    if job.state == "succeeded" and on_finish is not None:
        on_finish(job)


def stop_job(stage: str) -> bool:
    """Stop a running stage. Used by the view's Stop control."""
    job = active_job(stage)
    if job is None or job.task_id is None:
        return False
    return stop_task(job.task_id) in {"stopped", "stopping"}


def reset_state() -> None:
    """Forget every run. Used by tests to isolate one case from the next."""
    global _next_id
    with _lock:
        _running.clear()
        _history.clear()
        _next_id = 1
    manager.reset()
