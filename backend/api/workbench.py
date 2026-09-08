"""Expose revisioned plans and durable runs through the Flask API.

Request objects enter the workbench service; only public identities, safe
records and declared complete result files leave this transport boundary.
"""

from __future__ import annotations

import os
from functools import wraps

from flask import Blueprint, jsonify, request, send_file

from backend.config import is_hosted, pipeline_output_directory, pipeline_runs_enabled
from backend.services import datasets, workbench


blueprint = Blueprint("workbench", __name__)


def _errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except workbench.WorkbenchError as error:
            return jsonify(error=error.code, message=str(error)), error.status
        except datasets.DatasetNotFoundError:
            return jsonify(error="dataset_not_found", message="The selected dataset was not found."), 404
        except datasets.DatasetStorageError:
            return jsonify(error="dataset_storage_unavailable", message="The selected dataset could not be read."), 503
        except datasets.DatasetValidationError as error:
            return jsonify(error="invalid_dataset", message=str(error), issues=error.issues), 400
        except OSError:
            return jsonify(error="runtime_unavailable", message="Workbench storage is unavailable. Check runtime storage in Settings."), 503
    return wrapped


def _payload():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise workbench.WorkbenchError("Provide a JSON request object.")
    return value


def _capabilities():
    root = pipeline_output_directory()
    # Probe access without creating files merely to answer a Settings read.
    ancestor = root
    while ancestor is not None and not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    writable = ancestor is not None and ancestor.is_dir() and os.access(ancestor, os.W_OK | os.X_OK)
    recovery_error = workbench.recovery_storage_error()
    writable = writable and recovery_error is None
    executable = writable and not is_hosted() and pipeline_runs_enabled()
    return {"storageAvailable": bool(writable), "executionAvailable": bool(executable),
            "storageReason": None if writable else recovery_error or "Configure a writable PIPELINE_OUTPUT_DIR.",
            "executionReason": None if executable else "Model execution requires writable storage and enabled server execution."}


@blueprint.get("/api/workbench/plans")
@_errors
def plans():
    capabilities = _capabilities()
    rows = workbench.list_plans(request.args.get("datasetId")) if pipeline_output_directory() is not None else []
    return jsonify(plans=rows, **capabilities)


@blueprint.post("/api/workbench/plans")
@_errors
def create_plan():
    return jsonify(workbench.create_plan(_payload())), 201


@blueprint.get("/api/workbench/plans/<identifier>")
@_errors
def plan(identifier):
    value = request.args.get("revision")
    if value is not None and not value.isdigit():
        raise workbench.WorkbenchError("revision must be a positive integer.")
    return jsonify(workbench.get_plan(identifier, int(value) if value is not None else None))


@blueprint.put("/api/workbench/plans/<identifier>")
@_errors
def revise_plan(identifier):
    return jsonify(workbench.update_plan(identifier, _payload()))


@blueprint.get("/api/workbench/runs")
@_errors
def runs():
    rows = workbench.list_runs(request.args.get("datasetId")) if pipeline_output_directory() is not None else []
    return jsonify(runs=rows, **_capabilities())


@blueprint.post("/api/workbench/runs")
@_errors
def start_run():
    return jsonify(workbench.start_run(_payload())), 202


@blueprint.get("/api/workbench/runs/<identifier>")
@_errors
def run(identifier):
    return jsonify(workbench.get_run(identifier))


@blueprint.post("/api/workbench/runs/<identifier>/stop")
@_errors
def stop_run(identifier):
    return jsonify(workbench.stop_run(identifier))


@blueprint.get("/api/workbench/runs/<identifier>/files/<filename>")
@_errors
def download(identifier, filename):
    path = workbench.run_artifact_path(identifier, filename)
    return send_file(path, as_attachment=True, download_name=filename)
