"""HTTP routes for configured MTA-SIM generation and export."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from backend.services.data_generator import (
    download_path,
    generator_overview,
    get_run,
    preset_configuration,
    start_generation,
    start_postgresql_export,
)


blueprint = Blueprint("data_generator", __name__)


@blueprint.get("/api/data-generator")
def overview():
    """Return availability, presets, limits, and the default configuration."""

    return jsonify(generator_overview())


@blueprint.get("/api/data-generator/presets/<variant>/<preset>")
def preset(variant: str, preset: str):
    """Return one allow-listed preset resolved to a self-contained object."""

    try:
        return jsonify(
            {
                "variant": variant,
                "preset": preset,
                "configuration": preset_configuration(variant, preset),
            }
        )
    except ValueError as error:
        return jsonify({"error": "unknown_preset", "message": str(error)}), 404


@blueprint.post("/api/data-generator/runs")
def create_run():
    """Start one bounded asynchronous generator run."""

    body = request.get_json(silent=True) or {}
    try:
        state = start_generation(
            str(body.get("variant") or "baseline"),
            body.get("configuration"),
        )
        return jsonify(state), 202
    except ValueError as error:
        return jsonify({"error": "invalid_configuration", "message": str(error)}), 400
    except RuntimeError as error:
        code = 409 if "active" in str(error) else 503
        return jsonify({"error": "generator_unavailable", "message": str(error)}), code


@blueprint.get("/api/data-generator/runs/<run_id>")
def read_run(run_id: str):
    """Return one run's bounded state."""

    try:
        return jsonify(get_run(run_id))
    except KeyError as error:
        return jsonify({"error": "unknown_run", "message": str(error)}), 404


@blueprint.get("/api/data-generator/runs/<run_id>/files/<table>")
def download(run_id: str, table: str):
    """Download one declared generated CSV file."""

    try:
        path, name = download_path(run_id, table)
        return send_file(
            path, as_attachment=True, download_name=name, mimetype="text/csv"
        )
    except KeyError as error:
        return jsonify({"error": "unknown_file", "message": str(error)}), 404
    except RuntimeError as error:
        return jsonify({"error": "file_unavailable", "message": str(error)}), 409


@blueprint.post("/api/data-generator/runs/<run_id>/postgresql")
def export_postgresql(run_id: str):
    """Start backend-only PostgreSQL export over a secure browser boundary."""

    local = request.remote_addr in {"127.0.0.1", "::1"}
    if not (request.is_secure or local):
        return (
            jsonify(
                {
                    "error": "secure_transport_required",
                    "message": "PostgreSQL credentials require HTTPS or localhost.",
                }
            ),
            403,
        )
    body = request.get_json(silent=True) or {}
    try:
        state = start_postgresql_export(
            run_id,
            body.get("connection"),
            replace=body.get("replace") is True,
        )
        return jsonify(state), 202
    except KeyError as error:
        return jsonify({"error": "unknown_run", "message": str(error)}), 404
    except ValueError as error:
        return jsonify({"error": "invalid_connection", "message": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"error": "export_unavailable", "message": str(error)}), 409
