"""Start, poll, and stop PostgreSQL schema setup operations.

Data flow:
    settings dialog -> here -> schema_operations service -> root import command
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.config import config_read_only, is_hosted, use_database
from backend.database import dispose_engine
from backend.repository.snapshot import clear_caches
from backend.services.schema_operations import (
    OperationError,
    operation_state,
    start_operation,
    stop_operation,
)
from backend.services.settings import log

blueprint = Blueprint("schema_operations", __name__)


@blueprint.get("/api/schema-operations")
def get_schema_operation():
    """Return the active or most recent setup operation."""
    return jsonify(operation_state())


@blueprint.post("/api/schema-operations")
def post_schema_operation():
    """Validate and start one initializer or simulator parser."""
    if is_hosted() or config_read_only() or not use_database():
        return (
            jsonify(
                {
                    "error": "schema_operations_unavailable",
                    "message": (
                        "Schema setup needs a writable local deployment with "
                        "DATABASE=true and saved PostgreSQL settings."
                    ),
                }
            ),
            403,
        )
    body = request.get_json(silent=True) or {}
    action = str(body.get("action") or "").strip()
    schema = str(body.get("schema") or "").strip()
    if "replace" in body and not isinstance(body["replace"], bool):
        return (
            jsonify(
                {
                    "error": "invalid_replace",
                    "message": "replace must be a Boolean value.",
                }
            ),
            400,
        )
    replace = body.get("replace") is True

    def on_finish(operation):
        dispose_engine()
        clear_caches()
        log("INFO", "schema", f"{operation.action} completed; caches cleared")

    try:
        start_operation(action, schema, replace, on_finish=on_finish)
    except OperationError as error:
        status = (
            409
            if error.code
            in {
                "already_running",
                "unsafe_schema",
                "replace_required",
                "not_simulator_source",
                "schema_census_failed",
            }
            else 400
        )
        return jsonify({"error": error.code, "message": str(error)}), status
    log("INFO", "schema", f"{action} started for {schema}")
    return jsonify(operation_state()), 202


@blueprint.delete("/api/schema-operations")
def delete_schema_operation():
    """Request termination of the active setup operation."""
    stopped = stop_operation()
    return jsonify(operation_state()), 200 if stopped else 409
