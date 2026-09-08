"""Transport canonical dataset files and pushed reports to shared validation."""

from __future__ import annotations

import csv
import io
import json
from functools import wraps

from flask import Blueprint, jsonify, request

from backend.services import datasets

blueprint = Blueprint("datasets", __name__)


def dataset_errors(function):
    """Map known ingestion errors without exposing a server path."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except datasets.DatasetValidationError as error:
            return jsonify(error="invalid_dataset", message=str(error), issues=error.issues), 400
        except datasets.DatasetNotFoundError:
            return jsonify(error="dataset_not_found", message="The selected dataset was not found."), 404
        except datasets.DatasetStorageError as error:
            return jsonify(error="dataset_storage_unavailable", message=str(error)), 503
    return wrapped


def _payload():
    if request.is_json:
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise datasets.DatasetValidationError([{"path": "/", "message": "Provide a JSON object."}])
        return value, "api"
    if not request.mimetype or not request.mimetype.startswith("multipart/"):
        raise datasets.DatasetValidationError([{"path": "/", "message": "Provide JSON or multipart report files."}])
    # The supplied filename only selects a parser; it is never a storage path.
    allowed = {"performance", "paths", "research"}
    if set(request.files) - allowed or set(request.form) - {"name"}:
        raise datasets.DatasetValidationError([{"path": "/", "message": "Unknown file or form role."}])
    payload = {"name": request.form.get("name")}
    for role in request.files:
        if len(request.files.getlist(role)) != 1:
            raise datasets.DatasetValidationError([{"path": role, "message": "Provide exactly one file per role."}])
        upload = request.files[role]
        try:
            text = upload.read().decode("utf-8-sig")
            if (upload.filename or "").lower().endswith(".csv") and role != "research":
                reader = csv.DictReader(io.StringIO(text))
                fields = datasets.MTA_SIM_ADS_FIELDS if role == "performance" else datasets.MTA_SIM_PATH_REPORT_FIELDS
                if tuple(reader.fieldnames or ()) != tuple(fields):
                    raise ValueError("CSV header does not match the template's ordered fields.")
                payload[role] = list(reader)
            else:
                payload[role] = json.loads(text)
        except (UnicodeError, ValueError, csv.Error):
            raise datasets.DatasetValidationError([{"path": role, "message": "File must be valid UTF-8 JSON or match the ordered CSV template."}]) from None
    return payload, "file"


@blueprint.get("/api/datasets")
@dataset_errors
def list_registered():
    """Report published descriptors and the registry's current availability."""
    try:
        return jsonify(datasets=datasets.list_datasets(), available=True, reason="")
    except datasets.DatasetStorageError:
        return jsonify(datasets=[], available=False, reason="Dataset runtime storage is unavailable.")


@blueprint.get("/api/datasets/templates")
def templates():
    return jsonify(datasets.templates())


@blueprint.get("/api/datasets/<dataset_id>")
@dataset_errors
def detail(dataset_id):
    return jsonify(datasets.get_dataset(dataset_id))


@blueprint.post("/api/datasets/validate")
@dataset_errors
def validate():
    payload, _ = _payload()
    return jsonify(datasets.validate_dataset(payload))


@blueprint.post("/api/datasets")
@dataset_errors
def register():
    payload, source = _payload()
    return jsonify(datasets.register_dataset(payload, source=source)), 201
