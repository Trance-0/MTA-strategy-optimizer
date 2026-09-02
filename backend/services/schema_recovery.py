"""What a reader can do when the loaded schema cannot serve the dashboard.

Dashboard resource routes answer a schema they cannot read with a 503 naming the
problem. The reader this dashboard is deployed for may have a browser and no
terminal, so diagnosis alone is not enough.

So the same failure is described a second time here, as a list of things that
can be clicked. Each option is one of the three actions the API already
implements -- select another schema, build dashboard schemas from a source,
load the sample into an empty one -- attached to a specific schema on the
connected server, ranked so the first is the one most likely wanted.

Nothing here decides anything: the routes that carry out these actions revalidate
against their own live census, so an option that became stale between this call
and the click is refused there rather than trusted here.

Data flow:
    the error card -> GET /api/schema-recovery -> here -> backend/services/schemas.py
"""

from __future__ import annotations

from typing import Any

from backend.config import (
    DEFAULT_SCHEMA,
    is_hosted,
    schema_setup_enabled,
    use_database,
)
from backend.services.schemas import available_schemas

#: Ranked best first. A schema that can simply be selected beats one that has
#: to be built, which beats one that has to be populated from the sample: the
#: reader wants their own data, and the ordering offers real data before it
#: offers a demonstration account.
_ORDER = {"select": 0, "derive": 1, "initialize": 2}


def recovery_state() -> dict[str, Any]:
    """Every schema on the connected server the reader could act on.

    Returns a state rather than raising, on the same grounds as
    `available_schemas()`: this is called precisely when something is already
    wrong, and a recovery route that fails to load leaves the reader with the
    error card and nothing under it.
    """
    if is_hosted():
        return _unavailable(
            "The published build reads the repository's committed sample files "
            "and has no database to repair."
        )
    if not use_database():
        return _unavailable(
            "This dashboard is reading the committed files, so no schema is in "
            "use. Turn on 'Read from the database' in Settings to choose one."
        )

    census = available_schemas()
    if census.get("error"):
        return {
            "available": False,
            "reason": (
                "The database could not be reached to list its schemas — "
                f"{census['error']}"
            ),
            "active": census.get("selected") or DEFAULT_SCHEMA,
            "setupEnabled": schema_setup_enabled(),
            "options": [],
        }

    active = census.get("selected") or DEFAULT_SCHEMA
    setup_enabled = schema_setup_enabled()
    options = [
        option
        for option in (
            _option(item, active, setup_enabled) for item in census.get("schemas", [])
        )
        if option is not None
    ]
    options.sort(key=lambda item: (_ORDER[item["action"]], item["schema"]))
    return {
        "available": True,
        "reason": None,
        "active": active,
        "setupEnabled": setup_enabled,
        "options": options,
    }


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "active": None,
        "setupEnabled": False,
        "options": [],
    }


def _option(
    item: dict[str, Any], active: str, setup_enabled: bool
) -> dict[str, Any] | None:
    """Turn one census entry into an offer, or None when there is nothing to offer.

    The schema already loaded is excluded: it is the one that failed, so
    offering to load it again would be the one option guaranteed not to help.
    A schema this deployment cannot act on is excluded too, rather than listed
    and disabled -- unlike the settings dropdown, this list exists only to be
    acted on, and an entry that cannot be is noise on an error page.
    """
    remedy = item.get("remedy") or {}
    action = remedy.get("action", "none")
    if action == "none":
        return None
    if action == "select" and item["name"] == active:
        return None
    if action in {"derive", "initialize"} and not setup_enabled:
        return None
    return {
        "schema": item["name"],
        "action": action,
        "label": remedy.get("label", ""),
        "summary": remedy.get("summary", ""),
        "kind": item.get("kind"),
        "tableCount": item.get("tableCount"),
        # Replacement is never proposed here. Every option this list offers is
        # additive: selecting reads, building writes new schemas beside the
        # source, and initializing only ever targets an empty one. A reader who
        # needs to overwrite an existing schema does that in Settings, where
        # the checkbox states what it destroys.
        "replace": False,
    }
