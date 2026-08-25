"""Start, watch, and stop a pipeline stage.

Three routes over `backend/services/jobs.py`. Starting a stage writes new
outputs under `modules/`, so it is refused in every read-only deployment --
the published static build has no server at all, and a protected server
deployment must not rewrite the configuration it was given.

Data flow:
    the Campaign Optimizer -> here -> backend/services/jobs.py -> uv run
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.config import config_read_only, is_hosted, use_database
from backend.repository.snapshot import clear_caches
from backend.services.jobs import (
    STAGE_KEYS,
    OptionError,
    jobs_state,
    normalize_options,
    start_job,
    start_refusal,
    stop_job,
)
from backend.services.settings import log

blueprint = Blueprint("jobs", __name__)


@blueprint.get("/api/jobs")
def list_jobs():
    """Every stage's current run, its log, and what it is allowed to do.

    Polled by the Campaign Optimizer while a stage runs. All three stages come
    back in one response because the view shows three tabs at once.
    """
    return jsonify(jobs_state())


@blueprint.post("/api/jobs/<stage>")
def start(stage: str):
    """Start one pipeline stage.

    Returns as soon as the child process is spawned; the client polls
    `GET /api/jobs` for progress.
    """
    if is_hosted() or config_read_only():
        return (
            jsonify(
                {
                    "error": "read_only_deployment",
                    "message": (
                        "This deployment cannot run pipeline stages. Run the "
                        "dashboard locally against a PostgreSQL mirror to run them."
                    ),
                }
            ),
            403,
        )

    try:
        options = normalize_options(request.get_json(silent=True) or {})
    except OptionError as error:
        return jsonify({"error": "invalid_options", "message": str(error)}), 400

    refusal = start_refusal(stage, writable=use_database())
    if refusal is not None:
        return (
            jsonify({"error": refusal["code"], "message": refusal["message"]}),
            409 if refusal["code"] == "already_running" else 400,
        )

    def on_finish(job):
        # A stage that succeeded rewrote what the dashboard reads, so the
        # cached snapshot is stale the moment it finishes.
        clear_caches()
        log("INFO", "jobs", f"{stage} finished; caches cleared")

    job = start_job(stage, options, on_finish=on_finish)
    log("INFO", "jobs", f"{stage} started: {job.command}")
    return jsonify(jobs_state()), 202


@blueprint.delete("/api/jobs/<stage>")
def stop(stage: str):
    """Stop a running stage.

    A name that is not a stage is a 404 rather than a 409: "nothing is running"
    and "no such stage" are different faults, and answering both the same way
    would let a typo read as an idle stage.
    """
    if stage not in STAGE_KEYS:
        return (
            jsonify({"error": "unknown_stage", "message": f"Unknown stage: {stage}."}),
            404,
        )
    stopped = stop_job(stage)
    return jsonify(jobs_state()), 200 if stopped else 409
