"""The snapshot, the reload control, and the master-object routes.

These four routes are what the six views read and write. `GET /api/dashboard`
is the one the client fetches on load; the others exist because a reader can
change something from the interface.

Data flow:
    backend/repository/&#42; -> here -> dashboard/src/api/client.js
"""

from __future__ import annotations

import time

from flask import Blueprint, jsonify, request

from backend.config import source_label, use_database
from backend.database import database_available
from backend.repository.research import (
    MasterObjectError,
    archive_master_object,
    save_master_object,
)
from backend.repository.snapshot import (
    clear_caches,
    load_research_history,
    load_snapshot,
)
from backend.services.settings import log

blueprint = Blueprint("dashboard", __name__)


@blueprint.get("/api/health")
def health():
    """Liveness only: the process is up and routing requests.

    Deliberately independent of `DATABASE`, of the `PG_*` variables, and of
    `attribution_result` having rows, unlike `/api/dashboard`. A release with
    no data loaded yet is still a successfully deployed release; conflating the
    two means a deployment can never go healthy until the database is seeded,
    and a rollback to a perfectly good prior release fails the same way.
    """
    return jsonify({"ok": True})


@blueprint.get("/api/dashboard")
def dashboard():
    """The whole snapshot in one response.

    A database that is configured but unreachable is reported as a page-level
    state rather than as a failed fetch inside whichever chart read it first,
    which is what lets the client name both remedies.
    """
    started = time.perf_counter()
    try:
        if use_database():
            usable, message = database_available()
            if not usable:
                log("ERROR", "data_source", f"database unusable: {message}")
                return (
                    jsonify(
                        {
                            "error": "database_unavailable",
                            "message": message,
                            "source": source_label(),
                        }
                    ),
                    503,
                )
        snapshot = load_snapshot()
        elapsed = (time.perf_counter() - started) * 1000
        log(
            "INFO",
            "data_source",
            f"snapshot from {snapshot['mode']} in {elapsed:.0f} ms",
        )
        return jsonify(snapshot)
    except Exception as error:  # noqa: BLE001 - reported as a page-level state
        log("ERROR", "data_source", f"{type(error).__name__}: {error}")
        return (
            jsonify(
                {
                    "error": "load_failed",
                    "message": f"{type(error).__name__}: {str(error)[:400]}",
                }
            ),
            500,
        )


@blueprint.get("/api/dashboard/research-history")
def research_history():
    """Observation-heavy research arrays, fetched only by views that use them."""
    try:
        return jsonify(load_research_history())
    except Exception as error:  # noqa: BLE001 - same page-level error contract
        log(
            "ERROR", "data_source", f"research history: {type(error).__name__}: {error}"
        )
        return (
            jsonify(
                {
                    "error": "load_failed",
                    "message": f"{type(error).__name__}: {str(error)[:400]}",
                }
            ),
            500,
        )


@blueprint.post("/api/reload")
def reload_data():
    """Drop the cached reads so the next request hits the source again."""
    clear_caches()
    log("INFO", "data_source", "caches cleared by the reload control")
    return jsonify({"ok": True})


@blueprint.put("/api/master/<entity_type>/<entity_id>")
def save_master(entity_type: str, entity_id: str):
    """Save an editable master or configuration draft for a future run.

    Generated delivery, budget, outcome, and path tables have no mutation
    route, which keeps historical experiments reproducible.
    """
    try:
        payload = (request.get_json(silent=True) or {}).get("payload")
        saved = save_master_object(entity_type, entity_id, payload)
        return jsonify({"ok": True, "object": saved})
    except MasterObjectError as error:
        return (
            jsonify({"error": "master_write_rejected", "message": str(error)}),
            400 if use_database() else 403,
        )


@blueprint.delete("/api/master/<entity_type>/<entity_id>")
def archive_master(entity_type: str, entity_id: str):
    """Archive a future-run draft; this never deletes generated history."""
    try:
        archived = archive_master_object(entity_type, entity_id)
        return jsonify({"ok": True, "object": archived})
    except MasterObjectError as error:
        return (
            jsonify({"error": "master_archive_rejected", "message": str(error)}),
            400 if use_database() else 403,
        )
