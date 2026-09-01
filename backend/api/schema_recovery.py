"""What the error card offers when the loaded schema cannot serve the dashboard.

One read-only route. The actions it names are carried out by the two routes
that already exist -- `POST /api/settings/schema-selection` and
`POST /api/schema-operations` -- each of which revalidates against its own live
census, so this route decides nothing and grants nothing.

Data flow:
    the error card -> here -> backend/services/schema_recovery.py
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from backend.services.schema_recovery import recovery_state

blueprint = Blueprint("schema_recovery", __name__)


@blueprint.get("/api/schema-recovery")
def get_schema_recovery():
    """List the schemas this reader could load, build, or populate."""
    return jsonify(recovery_state())
