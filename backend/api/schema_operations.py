"""Start, poll, and stop PostgreSQL schema setup operations.

Data flow:
    settings dialog -> here -> schema_operations service -> root import command
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.config import is_hosted, schema_setup_enabled, use_database
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


def _refusal() -> tuple[str, str] | None:
    """Why this deployment cannot run schema setup, or None if it can.

    Configuration protection is deliberately not one of the reasons. Setup
    writes tables to the database the platform already pointed this service
    at; it never rewrites a credential, so `DASHBOARD_CONFIG_READ_ONLY` is not
    the flag that governs it. `SCHEMA_SETUP_ENABLED` is, and an operator who
    wants the browser kept away from the data sets that instead.
    """
    if is_hosted():
        return (
            "schema_operations_unavailable",
            "The published build reads the repository's committed sample files "
            "and has no database to set up.",
        )
    if not use_database():
        return (
            "schema_operations_unavailable",
            "Schema setup needs database mode. Turn on 'Read from the database' "
            "in Settings and save a PostgreSQL connection first.",
        )
    if not schema_setup_enabled():
        return (
            "schema_setup_disabled",
            "This server was deployed with SCHEMA_SETUP_ENABLED=false, so the "
            "dashboard may read schemas but not write them.",
        )
    return None


def _state_payload() -> dict:
    """The operation record, carrying whether a new one may be started.

    The capability travels with every response rather than being inferred by
    the dialog from `readOnly`, so what the buttons offer and what the route
    would accept cannot drift apart.
    """
    refusal = _refusal()
    return {
        **operation_state(),
        "available": refusal is None,
        "reason": None if refusal is None else refusal[1],
    }


@blueprint.get("/api/schema-operations")
def get_schema_operation():
    """Return the active or most recent setup operation, and its availability."""
    return jsonify(_state_payload())


@blueprint.post("/api/schema-operations")
def post_schema_operation():
    """Validate and start one initializer or simulator parser."""
    refusal = _refusal()
    if refusal is not None:
        code, message = refusal
        return jsonify({"error": code, "message": message}), 403
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
    return jsonify(_state_payload()), 202


@blueprint.delete("/api/schema-operations")
def delete_schema_operation():
    """Request termination of the active setup operation."""
    stopped = stop_operation()
    return jsonify(_state_payload()), 200 if stopped else 409
