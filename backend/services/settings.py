"""The settings behind the foot of the navigation rail.

Holds the two things a reader may need to change without editing files: the
database credentials this service connects with, and whether data access is
logged while it streams.

Credentials are written to `.env` at the repository root, which is git-ignored.
Nothing here writes a credential to a tracked file, to an API response, or to
the log: `safe_summary()` is the only rendering of a connection, and it omits
the password by construction. The password is never sent back to the page
either -- the dialog receives a flag saying whether one is stored, which is all
it needs to explain a blank field.

Data flow:
    the settings dialog -> POST /api/settings -> here -> .env -> backend/config.py
"""

from __future__ import annotations

import os
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import (
    DEFAULT_SCHEMA,
    REPO_ROOT,
    config_read_only,
    is_hosted,
    use_database,
    valid_schema_name,
)
from backend.database import database_available, dispose_engine
from backend.repository.snapshot import clear_caches
from backend.services.schemas import available_schemas, probe_schemas

#: Written to `.env`. Order is preserved when the file is rewritten, so a
#: hand-edited file keeps its shape.
ENV_KEYS: tuple[str, ...] = (
    "DATABASE",
    "PG_HOST",
    "PG_PORT",
    "PG_DATABASE",
    "PG_USER",
    "PG_PASSWORD",
    "PG_SSLMODE",
    "PG_SCHEMA",
)

ENV_PATH: Path = REPO_ROOT / ".env"

#: How many log records the in-memory stream keeps. A file would be the wrong
#: choice: the reader wants to watch what the service is doing right now, and a
#: capped buffer cannot fill a disk on a demonstration machine.
LOG_CAPACITY = 400

LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}

_records: deque = deque(maxlen=LOG_CAPACITY)
_logging_on = False
_logging_level = "INFO"
_log_lock = threading.Lock()


def log(level: str, source: str, message: Any) -> None:
    """Record one line of activity, if logging is on."""
    if not _logging_on:
        return
    if LEVEL_ORDER.get(level, 20) < LEVEL_ORDER.get(_logging_level, 20):
        return
    with _log_lock:
        _records.append(
            {
                "when": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "level": level,
                "source": source,
                # A long statement or a long error is truncated rather than
                # stored whole, so one record cannot dominate the buffer.
                "message": str(message)[:400],
            }
        )


def logging_enabled() -> bool:
    return _logging_on


def apply_logging(enabled: bool, level: str = "INFO") -> None:
    """Turn capture on or off, and set the level it captures from."""
    global _logging_on, _logging_level
    _logging_on = bool(enabled)
    _logging_level = level if level in LEVEL_ORDER else "INFO"


def log_state() -> dict:
    """The capture state and its most recent records."""
    with _log_lock:
        return {
            "enabled": _logging_on,
            "level": _logging_level,
            "capacity": LOG_CAPACITY,
            "records": list(_records)[-120:],
        }


def clear_log() -> None:
    with _log_lock:
        _records.clear()


def read_env(path: Path = ENV_PATH) -> dict[str, str]:
    """Read the current `.env` values, falling back to the live environment."""
    values: dict[str, str] = {}
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    for key in ENV_KEYS:
        values.setdefault(key, os.environ.get(key, ""))
    return values


def write_env(updates: dict[str, str], path: Path = ENV_PATH) -> None:
    """Merge `updates` into `.env`, preserving comments and unrelated keys.

    The file is rewritten rather than appended to, so a key set twice cannot
    end up with the stale value winning depending on read order.
    """
    lines: list[str] = []
    seen: set[str] = set()

    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                lines.append(raw)
                continue
            key = line.partition("=")[0].strip()
            if key in updates:
                lines.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                lines.append(raw)

    while lines and lines[-1].strip() == "":
        lines.pop()

    missing = [key for key in ENV_KEYS if key in updates and key not in seen]
    if missing:
        if lines:
            lines.append("")
        lines.append("# Written by the dashboard settings module.")
        lines.extend(f"{key}={updates[key]}" for key in missing)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    # The values are exported into this process too, so the change takes effect
    # without a restart, and every cached read is dropped because it may have
    # come from the other source.
    os.environ.update(updates)
    _invalidate_configuration_caches()
    clear_caches()
    dispose_engine()


def _invalidate_configuration_caches() -> None:
    """Drop the memoized reads of `.env` so the new values take effect.

    `dashboard/config.py` memoizes `use_database`, `is_hosted`, and
    `database_settings` because they are read on every request and `.env` does
    not normally change under a running process. Saving new credentials is the
    one moment it does, so those caches are cleared here rather than the
    memoization being removed and every request paying for it.
    """
    from dashboard import config as dashboard_config

    for name in ("is_hosted", "use_database", "database_settings"):
        getattr(dashboard_config, name).cache_clear()


def status() -> dict:
    """The `{label, colour, detail}` triple the rail displays.

    The dot colours match the deployment accents in `src/lib/deployment.js`:
    green wherever the dashboard is reading committed files and cannot write,
    and the brand tint only where a database is actually connected. The rail
    and the theme therefore cannot disagree about which deployment this is.
    """
    if is_hosted():
        return {
            "label": "Sample data",
            "colour": "#7ed6a4",
            "detail": "Published build, reading the repository's committed samples.",
        }
    if use_database():
        usable, message = database_available()
        return {
            "label": "Database",
            "colour": "#7ee0b0" if usable else "#ffb4ad",
            "detail": message if usable else f"Unavailable — {message}",
        }
    return {
        "label": "Local files",
        "colour": "#7ed6a4",
        "detail": "Reading committed CSV and JSON artifacts. Read-only.",
    }


def test_connection(updates: dict[str, str]) -> dict:
    """Open a throwaway connection with the entered values.

    Tests what was typed rather than what is saved, so a reader can validate a
    correction before committing it to `.env`. The probe connection is closed
    whether or not it succeeded, so a failed test cannot leave a socket open on
    the shared instance.

    A successful test also carries the schema census back, because the dialog's
    schema list is only knowable from a live connection: the reader tests, and
    the dropdown fills with what that server actually offers.
    """
    missing = [
        key
        for key in ("PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD")
        if not updates.get(key)
    ]
    if missing:
        return {"ok": False, "message": f"Missing {', '.join(missing)}."}

    schema = (updates.get("PG_SCHEMA") or "").strip() or DEFAULT_SCHEMA
    if not valid_schema_name(schema):
        return {
            "ok": False,
            "message": (
                f"{schema!r} is not a valid PostgreSQL schema name. Use letters, "
                "digits, and underscores, beginning with a letter or underscore."
            ),
        }

    from urllib.parse import quote_plus

    from sqlalchemy import create_engine, text

    user = quote_plus(updates["PG_USER"])
    password = quote_plus(updates["PG_PASSWORD"])
    host = updates["PG_HOST"]
    port = updates.get("PG_PORT") or "5432"
    database = updates["PG_DATABASE"]
    sslmode = updates.get("PG_SSLMODE") or "prefer"
    url = (
        f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
        f"?sslmode={sslmode}"
    )

    probe = None
    try:
        probe = create_engine(url, connect_args={"connect_timeout": 10})
        with probe.connect() as connection:
            version = connection.execute(text("select version()")).scalar_one()
            # Counted in the schema the reader chose rather than always in
            # `public`, so the number describes what selecting it would read.
            tables = connection.execute(
                text(
                    "select count(*)::int from information_schema.tables "
                    "where table_schema = :schema"
                ),
                {"schema": schema},
            ).scalar_one()
        census = probe_schemas(updates)
        return {
            "ok": True,
            "message": (
                f"Connected to {updates['PG_USER']}@{host}:{port}/{database} — "
                f"schema {schema}, {tables} table(s). {str(version).split(',')[0]}"
            ),
            "schemas": census,
        }
    except Exception as error:  # noqa: BLE001 - reported to the dialog, not raised
        return {"ok": False, "message": f"{type(error).__name__}: {str(error)[:300]}"}
    finally:
        if probe is not None:
            probe.dispose()


def settings_state() -> dict:
    """The state the settings dialog renders.

    Carries no credential beyond the host, port, database, and user the reader
    typed themselves.
    """
    values = read_env()
    return {
        "hosted": is_hosted(),
        "readOnly": config_read_only(),
        "useDatabase": use_database(),
        "connection": {
            "PG_HOST": values.get("PG_HOST", ""),
            "PG_PORT": values.get("PG_PORT") or "5432",
            "PG_DATABASE": values.get("PG_DATABASE", ""),
            "PG_USER": values.get("PG_USER", ""),
            "PG_SSLMODE": values.get("PG_SSLMODE") or "prefer",
            "PG_SCHEMA": values.get("PG_SCHEMA") or DEFAULT_SCHEMA,
            "passwordStored": bool(values.get("PG_PASSWORD")),
        },
        # Enumerated only in database mode: in file mode there is no connection
        # to ask, and opening one to populate a dropdown the reader has not
        # asked for would make every settings request pay for a round trip.
        "schemas": (
            available_schemas()
            if use_database()
            else {"schemas": [], "selected": values.get("PG_SCHEMA") or DEFAULT_SCHEMA,
                  "error": None}
        ),
        "status": status(),
        "logging": log_state(),
    }
