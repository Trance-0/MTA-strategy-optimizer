"""Start, watch, and stop a pipeline stage.

Three routes over `backend/services/jobs.py`. Starting a stage writes isolated
runtime outputs when `PIPELINE_OUTPUT_DIR` is configured. Configuration
protection and pipeline execution are separate permissions: AppStack
credentials stay protected while its authenticated operator may run the model
stages.

Data flow:
    the Campaign Optimizer -> here -> backend/services/jobs.py -> uv run
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy.exc import SQLAlchemyError

from backend.config import (
    is_hosted,
    pipeline_output_directory,
    pipeline_runs_enabled,
    use_database,
)
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
from backend.services.model_outputs import (
    MAX_FILE_BYTES,
    MAX_STAGE_BYTES,
    ArtifactError,
    artifact_names,
    artifact_manifest,
    artifact_path,
    import_artifacts,
    publish_artifacts,
)

blueprint = Blueprint("jobs", __name__)


@blueprint.get("/api/jobs")
def list_jobs():
    """Every stage's current run, its log, and what it is allowed to do.

    Polled by the Campaign Optimizer while a stage runs. All three stages come
    back in one response because the view shows three tabs at once.
    """
    return jsonify(
        jobs_state(
            execution_enabled=pipeline_runs_enabled(),
            database_enabled=use_database(),
        )
    )


@blueprint.post("/api/jobs/<stage>")
def start(stage: str):
    """Start one pipeline stage.

    Returns as soon as the child process is spawned; the client polls
    `GET /api/jobs` for progress.
    """
    if is_hosted() or not pipeline_runs_enabled():
        return (
            jsonify(
                {
                    "error": "pipeline_disabled",
                    "message": (
                        "Pipeline execution is disabled on this server. Set "
                        "PIPELINE_RUNS_ENABLED=true in its deployment configuration."
                    ),
                }
            ),
            403,
        )

    try:
        options = normalize_options(request.get_json(silent=True) or {})
    except OptionError as error:
        return jsonify({"error": "invalid_options", "message": str(error)}), 400

    database_enabled = use_database()
    refusal = start_refusal(
        stage,
        writable=pipeline_output_directory() is not None,
        options=options,
        database_enabled=database_enabled,
    )
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

    job = start_job(
        stage,
        options,
        on_finish=on_finish,
        database_enabled=database_enabled,
    )
    log("INFO", "jobs", f"{stage} started: {job.command}")
    return jsonify(
        jobs_state(execution_enabled=True, database_enabled=database_enabled)
    ), 202


@blueprint.get("/api/jobs/<stage>/artifacts/<filename>")
def download_artifact(stage: str, filename: str):
    """Download one exact validated stage artifact from runtime storage."""
    try:
        path = artifact_path(stage, filename)
    except ArtifactError as error:
        return jsonify({"error": "invalid_artifact", "message": str(error)}), 400
    except FileNotFoundError:
        return jsonify(
            {"error": "artifact_not_found", "message": "Artifact not found."}
        ), 404
    except (OSError, RuntimeError, SQLAlchemyError) as error:
        return (
            jsonify(
                {
                    "error": "artifact_unavailable",
                    "message": f"{type(error).__name__}: {str(error)[:300]}",
                }
            ),
            503,
        )
    return send_file(path, as_attachment=True, download_name=filename)


@blueprint.post("/api/jobs/<stage>/artifacts")
def upload_artifacts(stage: str):
    """Validate and publish one complete multipart stage-output set."""
    submitted = []
    try:
        uploads = request.files.getlist("files")
        if len(uploads) > len(artifact_names(stage)):
            raise ArtifactError("Too many files were submitted for this stage.")
        total = 0
        for upload in uploads:
            content = upload.stream.read(MAX_FILE_BYTES + 1)
            total += len(content)
            if total > MAX_STAGE_BYTES:
                raise ArtifactError(
                    "The artifact set exceeds the 25 MiB request limit."
                )
            submitted.append((upload.filename or "", content))
        result = publish_artifacts(stage, submitted)
    except (ArtifactError, OSError) as error:
        return jsonify({"error": "invalid_artifacts", "message": str(error)}), 400
    clear_caches()
    log("INFO", "artifacts", f"{stage} outputs uploaded and parsed")
    return jsonify({"ok": True, "artifacts": result})


@blueprint.post("/api/jobs/<stage>/artifacts/import")
def import_stage_artifacts(stage: str):
    """Persist one complete validated runtime set in the active database."""
    if not use_database():
        return (
            jsonify(
                {
                    "error": "database_required",
                    "message": "Configure database mode before importing model outputs.",
                }
            ),
            409,
        )
    try:
        count = import_artifacts(stage)
        artifacts = artifact_manifest(stage, database_enabled=True)
    except (ArtifactError, FileNotFoundError, OSError, SQLAlchemyError) as error:
        return jsonify({"error": "invalid_artifacts", "message": str(error)}), 400
    clear_caches()
    log("INFO", "artifacts", f"{stage} outputs imported to database ({count} files)")
    return jsonify({"ok": True, "imported": count, "artifacts": artifacts})


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
    return (
        jsonify(
            jobs_state(
                execution_enabled=pipeline_runs_enabled(),
                database_enabled=use_database(),
            )
        ),
        200 if stopped else 409,
    )
