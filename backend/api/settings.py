"""Read and change the deployment's data source and its logging.

Two routes over `backend/services/settings.py`. The published build accepts
neither: it has no writable `.env` and no socket, so a change could not take
effect and pretending otherwise would invite a real password into a page that
cannot use it.

Data flow:
    the settings dialog -> here -> backend/services/settings.py -> .env
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.config import DEFAULT_SCHEMA, config_read_only, is_hosted, valid_schema_name
from backend.services.settings import (
    apply_logging,
    clear_log,
    log,
    read_env,
    settings_state,
    test_connection,
    write_env,
)

blueprint = Blueprint("settings", __name__)


@blueprint.get("/api/settings")
def get_settings():
    """The state the settings dialog renders. Carries no stored password."""
    return jsonify(settings_state())


@blueprint.post("/api/settings")
def post_settings():
    """Apply a settings change.

    `test` probes the entered values without saving them, and carries back the
    schemas that connection offers. `save` rewrites `.env`. `logging` toggles
    the capture, and `clearLog` empties it.
    """
    if is_hosted():
        return (
            jsonify(
                {
                    "error": "hosted",
                    "message": (
                        "The published build reads the repository's committed "
                        "sample files and cannot open a database connection."
                    ),
                }
            ),
            403,
        )

    if config_read_only():
        return (
            jsonify(
                {
                    "error": "read_only_configuration",
                    "message": (
                        "This server reads protected deployment configuration. "
                        "Change it through the server deployment environment, "
                        "then restart the service."
                    ),
                }
            ),
            403,
        )

    body = request.get_json(silent=True) or {}
    action = body.get("action")

    if action == "logging":
        logging = body.get("logging") or {}
        apply_logging(bool(logging.get("enabled")), logging.get("level") or "INFO")
        return jsonify(settings_state())

    if action == "clearLog":
        clear_log()
        return jsonify(settings_state())

    connection = body.get("connection") or {}
    updates = {
        "DATABASE": "true" if body.get("useDatabase") else "false",
        "PG_HOST": str(connection.get("PG_HOST") or "").strip(),
        "PG_PORT": str(connection.get("PG_PORT") or "").strip() or "5432",
        "PG_DATABASE": str(connection.get("PG_DATABASE") or "").strip(),
        "PG_USER": str(connection.get("PG_USER") or "").strip(),
        "PG_PASSWORD": str(connection.get("PG_PASSWORD") or ""),
        "PG_SSLMODE": str(connection.get("PG_SSLMODE") or "prefer"),
        "PG_SCHEMA": str(connection.get("PG_SCHEMA") or "").strip() or DEFAULT_SCHEMA,
    }

    # A schema name reaches libpq as an identifier inside a connect option
    # rather than as a bound value, so it is refused here before it is written
    # to `.env`, rather than at the connection that would carry it. The dialog
    # offers a list, so a name failing this arrived from something other than
    # the dropdown.
    if not valid_schema_name(updates["PG_SCHEMA"]):
        return (
            jsonify(
                {
                    "error": "invalid_schema",
                    "message": (
                        f"{updates['PG_SCHEMA']!r} is not a valid PostgreSQL schema "
                        "name. Use letters, digits, and underscores, beginning with "
                        "a letter or underscore."
                    ),
                }
            ),
            400,
        )

    # An empty password field means "keep the stored one" rather than "clear
    # it", because the dialog never receives the stored value to echo back.
    if updates["PG_PASSWORD"] == "":
        updates["PG_PASSWORD"] = read_env().get("PG_PASSWORD", "")

    if action == "test":
        result = test_connection(updates)
        log("INFO", "settings", f"connection test: {'ok' if result['ok'] else 'failed'}")
        return jsonify(result)

    if action == "save":
        write_env(updates)
        log("INFO", "settings", "credentials written to .env, caches cleared")
        return jsonify({"ok": True, **settings_state()})

    return jsonify({"error": "unknown_action"}), 400
