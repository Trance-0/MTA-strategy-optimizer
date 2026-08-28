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
    POST /api/jobs/<stage> -> here -> uv run script/&#42;.py -> modules/&#42;/outputs
    GET  /api/jobs         -> here -> the Campaign Optimizer's log tabs
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import distinct, select
from sqlalchemy.exc import SQLAlchemyError

from backend.config import (
    ATTRIBUTION_OUTPUT_DIR,
    REPO_ROOT,
    pipeline_output_directory,
    research_snapshot_path,
    simulator_data_directory,
)
from backend.database import orm_rows
from modules.mta_standard.src.mta_sim_generator_adapter import (
    prepare_single_scope_reports,
)
from dashboard.models import Advertiser

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
        # `run_pipeline.py` rather than `run_attribution_models.py`: the
        # pipeline script rebuilds the path report from the touchpoint events
        # first and publishes all five outputs atomically, which is what the
        # documented command does and what keeps a failed run from leaving half
        # a result.
        "script": "script/run_pipeline.py",
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
        # Needs a research snapshot to fit budget response against, which is
        # the one input the committed reports do not supply: fitting a
        # budget-to-revenue curve needs the same Campaign observed at several
        # budget levels, and a single reporting window carries one.
        "requiresResearchSnapshot": True,
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

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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

    for key in ("startDate", "endDate"):
        value = str(body.get(key) or "").strip()
        if value == "":
            continue
        if not ISO_DATE.match(value):
            raise OptionError(f"{key} must be a YYYY-MM-DD date.")
        options[key] = value
    if (
        options.get("startDate")
        and options.get("endDate")
        and options["startDate"] > options["endDate"]
    ):
        raise OptionError("startDate must not be after endDate.")

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


def arguments_for(stage: str, options: dict) -> list[str]:
    """Build the argument vector for a stage.

    A date range narrows the reporting window the stage reads. It is validated
    to `YYYY-MM-DD` before it reaches the command line rather than passed
    through, so a value from the browser cannot become part of a command.
    """
    runtime = pipeline_output_directory()
    script = script_for(stage)
    simulator_inputs = _simulator_attribution_inputs()
    if (
        stage == "attribution"
        and simulator_inputs is not None
        and (options.get("startDate") or options.get("endDate"))
    ):
        raise OptionError(
            "Reporting date filters cannot be applied to an uploaded simulator "
            "path report. Remove the date range or provide the "
            "unaggregated attribution inputs."
        )
    args = ["uv", "run", "python", "-X", "utf8", "-B", script]
    if stage == "attribution" and script == "script/run_attribution_models.py":
        simulator_path, simulator_ads = simulator_inputs
        args += [
            "--amc-report",
            str(_prepared_attribution_path()),
            "--amazon-ads-report",
            str(_prepared_performance_path()),
        ]
        args += ["--output-dir", str(_attribution_output_directory())]
    elif stage == "attribution" and runtime is not None:
        args += [
            "--path-report",
            str(runtime / "attribution" / "amc_mta_path_report_raw_sample.csv"),
            "--output-dir",
            str(runtime / "attribution"),
        ]
    if stage == "attribution":
        # The window narrows both the Ads report and the touchpoint events, so
        # the two stay coherent: the pipeline rejects a conversion whose event
        # time falls outside the window its Ads report infers.
        if options.get("startDate"):
            args += ["--report-start-date", options["startDate"]]
        if options.get("endDate"):
            args += ["--report-end-date", options["endDate"]]
    if stage == "optimization":
        args += ["--research-snapshot", str(research_snapshot_path())]
        if options.get("_marketplace"):
            args += ["--marketplace", options["_marketplace"]]
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
        snapshot = research_snapshot_path()
        if snapshot is not None:
            args += ["--research-snapshot", str(snapshot)]
        if options.get("_marketplace"):
            args += ["--marketplace", options["_marketplace"]]
    return args


def _simulator_attribution_inputs():
    """Return a complete aggregated simulator input pair, or None."""
    simulator = simulator_data_directory()
    if simulator is None:
        return None
    path_report = simulator / "amc_path_report.csv"
    ads_report = simulator / "amazon_ads_daily_touchpoint_performance.csv"
    return (
        (path_report, ads_report)
        if path_report.is_file() and ads_report.is_file()
        else None
    )


def _attribution_output_directory():
    """Writable attribution root for this deployment."""
    runtime = pipeline_output_directory()
    return runtime / "attribution" if runtime else ATTRIBUTION_OUTPUT_DIR


def _prepared_attribution_path():
    """Single-scope model input derived from uploaded daily path windows."""
    return _attribution_output_directory() / "model_input_amc_path_report.csv"


def _prepared_performance_path():
    """Marketplace-scoped performance input paired with the prepared paths."""
    return _attribution_output_directory() / "model_input_amazon_ads_report.csv"


def _selected_marketplace() -> str:
    """The one advertiser marketplace in the selected dashboard schema."""
    rows = orm_rows(select(distinct(Advertiser.marketplace).label("marketplace")))
    marketplaces = sorted(
        {str(row.get("marketplace") or "").strip() for row in rows} - {""}
    )
    if len(marketplaces) != 1:
        raise ValueError(
            "the selected dashboard schema must contain exactly one advertiser "
            f"marketplace before attribution can select an upload scope; found "
            f"{marketplaces}"
        )
    return marketplaces[0]


def script_for(stage: str) -> str | None:
    """The command entry point this deployment will actually execute."""
    if stage == "attribution" and _simulator_attribution_inputs() is not None:
        return "script/run_attribution_models.py"
    return STAGES[stage]["script"]


def prepare_runtime_inputs(stage: str, marketplace: str | None = None) -> None:
    """Create isolated output folders and seed evaluation's strategy inputs."""
    runtime = pipeline_output_directory()
    if runtime is not None:
        (runtime / "attribution").mkdir(parents=True, exist_ok=True)
        (runtime / "strategy").mkdir(parents=True, exist_ok=True)
        (runtime / "evaluation").mkdir(parents=True, exist_ok=True)
    simulator_inputs = _simulator_attribution_inputs()
    if stage == "attribution" and simulator_inputs is not None:
        path_report, performance_report = simulator_inputs
        prepare_single_scope_reports(
            path_report,
            performance_report,
            _prepared_attribution_path(),
            _prepared_performance_path(),
            marketplace=marketplace,
        )
    if runtime is None:
        return
    if stage != "evaluation":
        return
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
        self.state = "running"
        self.percent = 2
        self.phase = "Starting"
        self.command = command
        self.started_at = _now()
        self.finished_at: str | None = None
        self.exit_code: int | None = None
        self.error: str | None = None
        self.lines: list[dict] = []
        self.dropped_lines = 0
        self.process: subprocess.Popen | None = None

    def public_view(self) -> dict:
        """The run's public shape.

        The command is included so a reader can reproduce the run in a
        terminal, which is the point of running the real script rather than a
        reimplementation.
        """
        return {
            "id": self.id,
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
            self.lines.append({"at": _now(), "stream": stream, "text": line[:500]})
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
    return job if job is not None and job.state == "running" else None


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
        available = bool(script) and execution_enabled and database_enabled
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
                    "Running a stage writes new outputs, so it needs a connected "
                    "database deployment. This deployment reads committed files."
                    if not database_enabled
                    else definition.get("unavailableReason")
                )
            ),
            "requiresResearchSnapshot": bool(
                definition.get("requiresResearchSnapshot")
            ),
            "current": job.public_view() if job else None,
        }
    return {"stages": stages, "history": [job.public_view() for job in _history]}


def start_refusal(
    stage: str, writable: bool, options: dict | None = None
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
            "code": "read_only",
            "message": (
                "Running a stage writes new outputs, so it needs a connected "
                "database deployment. This deployment reads committed files."
            ),
        }
    if (
        stage == "attribution"
        and _simulator_attribution_inputs() is not None
        and ((options or {}).get("startDate") or (options or {}).get("endDate"))
    ):
        return {
            "code": "unsupported_options",
            "message": (
                "Reporting date filters cannot be applied to an already "
                "uploaded simulator path report. Remove the date range or "
                "provide the unaggregated attribution inputs."
            ),
        }
    if active_job(stage) is not None:
        return {
            "code": "already_running",
            "message": f"{definition['label']} is already running.",
        }
    if definition.get("requiresResearchSnapshot") and research_snapshot_path() is None:
        return {
            "code": "missing_input",
            "message": (
                "Fitting a budget response curve needs the same Campaign "
                "observed at several budget levels, which a single reporting "
                "window does not carry. Configure MTA_SIM_DATA_DIR with a "
                "research snapshot to fit against."
            ),
        }
    return None


def start_job(
    stage: str, options: dict, on_finish: Callable[[Job], None] | None = None
) -> Job:
    """Start `stage` and return its run immediately.

    The caller has already checked `start_refusal`. The child is detached from
    the request: the HTTP response returns as soon as the process is spawned,
    and the client polls for the rest.
    """
    global _next_id
    with _lock:
        identifier = _next_id
        _next_id += 1
    job = Job(identifier, stage, STAGES[stage]["script"] or stage)
    _running[stage] = job

    try:
        needs_marketplace = (
            stage == "attribution" and _simulator_attribution_inputs() is not None
        ) or (
            stage in {"optimization", "evaluation"}
            and research_snapshot_path() is not None
        )
        marketplace = _selected_marketplace() if needs_marketplace else None
        execution_options = {
            **options,
            **({"_marketplace": marketplace} if marketplace else {}),
        }
        args = arguments_for(stage, execution_options)
        job.command = " ".join(args)
        job.append("meta", f"$ {job.command}")
        if options.get("startDate") or options.get("endDate"):
            job.append(
                "meta",
                "Reporting window: "
                f"{options.get('startDate') or 'earliest'} to "
                f"{options.get('endDate') or 'latest'}",
            )
        if stage == "attribution" and _simulator_attribution_inputs() is not None:
            job.append(
                "meta",
                "Preparing every uploaded daily path window as one model scope.",
            )
        prepare_runtime_inputs(stage, marketplace=marketplace)
        if stage == "attribution" and _simulator_attribution_inputs() is not None:
            job.append(
                "meta",
                "Prepared marketplace-scoped attribution inputs: "
                f"{_prepared_attribution_path()} and {_prepared_performance_path()}",
            )
    except (OSError, ValueError, SQLAlchemyError) as error:
        _finish(
            job,
            error=(
                "Could not prepare the pipeline runtime inputs: "
                f"{type(error).__name__}: {error}"
            ),
            on_finish=on_finish,
        )
        return job

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
                "The `uv` command was not found on this server. The dashboard "
                "runs pipeline stages through uv, exactly as the documented "
                "commands do; install uv, or run the stage in a terminal instead."
            ),
            on_finish=on_finish,
        )
        return job
    except OSError as error:
        _finish(job, error=f"{type(error).__name__}: {error}", on_finish=on_finish)
        return job

    job.process = process
    thread = threading.Thread(
        target=_drain, args=(job, process, on_finish), daemon=True, name=f"job-{stage}"
    )
    thread.start()
    return job


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
        if job.state == "running":
            _finish(job, exit_code=code, on_finish=on_finish)


def _finish(
    job: Job,
    exit_code: int | None = None,
    error: str | None = None,
    on_finish: Callable[[Job], None] | None = None,
) -> None:
    """Record a run's outcome and retire it into the history."""
    job.state = "failed" if error or exit_code != 0 else "succeeded"
    job.exit_code = exit_code
    job.error = error
    job.finished_at = _now()
    job.process = None
    if job.state == "succeeded":
        job.percent = 100
        job.phase = "Complete"
        job.append("meta", "Stage completed. Reloading the dashboard's data.")
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
    if job is None or job.process is None:
        return False
    job.append("meta", "Stop requested by the operator.")
    job.process.terminate()
    return True


def reset_state() -> None:
    """Forget every run. Used by tests to isolate one case from the next."""
    global _next_id
    with _lock:
        _running.clear()
        _history.clear()
        _next_id = 1
