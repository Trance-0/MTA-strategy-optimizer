"""Initialize dashboard schemas and parse simulator schemas with live logs.

The root commands remain the only implementations of import and derivation.
This service validates a browser request against a fresh schema census, starts
the appropriate command as a fixed argument vector, and retains bounded output
for polling by the settings dialog.

Data flow:
    settings dialog -> /api/schema-operations -> root command -> PostgreSQL
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from backend.config import REPO_ROOT, valid_schema_name
from backend.services.schemas import _read_schemas

MAX_LINES = 600

_current: "SchemaOperation | None" = None
_lock = threading.Lock()
_next_id = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationError(ValueError):
    """A schema-operation request that must be refused before spawning."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SchemaOperation:
    """One initializer or parser process and its bounded public record."""

    def __init__(
        self, identifier: int, action: str, schema: str, args: list[str]
    ) -> None:
        self.id = identifier
        self.action = action
        self.schema = schema
        self.state = "running"
        self.command = subprocess.list2cmdline(args)
        self.started_at = _now()
        self.finished_at: str | None = None
        self.exit_code: int | None = None
        self.error: str | None = None
        self.lines: list[dict[str, str]] = []
        self.dropped_lines = 0
        self.process: subprocess.Popen | None = None

    def append(self, stream: str, text: str) -> None:
        """Append timestamped nonblank lines, retaining only the newest 600."""
        for raw in str(text).splitlines():
            line = raw.rstrip()
            if not line:
                continue
            self.lines.append({"at": _now(), "stream": stream, "text": line[:500]})
            if len(self.lines) > MAX_LINES:
                overflow = len(self.lines) - MAX_LINES
                self.dropped_lines += overflow
                del self.lines[:overflow]

    def public_view(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "schema": self.schema,
            "state": self.state,
            "command": self.command,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "exitCode": self.exit_code,
            "error": self.error,
            "lines": list(self.lines),
            "droppedLines": self.dropped_lines,
        }


def operation_state() -> dict[str, Any]:
    """The active or most recently completed operation."""
    return {"current": _current.public_view() if _current else None}


def arguments_for(action: str, schema: str, replace: bool = False) -> list[str]:
    """Build the fixed command argument vector for one validated request."""
    if action == "initialize":
        args = [
            sys.executable,
            "-X",
            "utf8",
            "-B",
            "script/import_to_database.py",
            "--schema",
            schema,
        ]
    elif action == "derive":
        args = [
            sys.executable,
            "-X",
            "utf8",
            "-B",
            "script/derive_scenario_schemas.py",
            "--source",
            schema,
            "--all",
        ]
    else:
        raise OperationError("unknown_action", f"Unknown schema action: {action}.")
    if replace:
        args.append("--replace")
    return args


def validate_request(
    action: str,
    schema: str,
    replace: bool,
    census: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Recheck capability and return the argument vector, or a precise refusal."""
    if not valid_schema_name(schema):
        raise OperationError(
            "invalid_schema",
            "Use a schema name beginning with a letter or underscore and containing "
            "only letters, digits, underscores, or dollar signs.",
        )
    if census is None:
        try:
            rows = _read_schemas(schema)
        except Exception as error:  # noqa: BLE001 - becomes a bounded API refusal
            raise OperationError(
                "schema_census_failed",
                "The saved database connection could not inspect schemas: "
                f"{type(error).__name__}: {str(error)[:240]}",
            ) from error
    else:
        rows = census
    found = next((item for item in rows if item["name"] == schema), None)

    if action == "initialize":
        if found is not None and not found["canInitialize"]:
            raise OperationError(
                "unsafe_schema",
                f"Schema {schema!r} is populated and is not a dashboard schema; "
                "the sample initializer would mix unrelated data into it.",
            )
        if found is not None and found["kind"] == "dashboard" and not replace:
            raise OperationError(
                "replace_required",
                f"Schema {schema!r} already serves the dashboard. Enable replacement "
                "to rebuild it.",
            )
    elif action == "derive":
        if found is None or not found["canDerive"]:
            raise OperationError(
                "not_simulator_source",
                f"Schema {schema!r} does not hold the complete simulator source contract.",
            )
    else:
        raise OperationError("unknown_action", f"Unknown schema action: {action}.")
    return arguments_for(action, schema, replace)


def start_operation(
    action: str,
    schema: str,
    replace: bool = False,
    *,
    census: list[dict[str, Any]] | None = None,
    on_finish: Callable[[SchemaOperation], None] | None = None,
) -> SchemaOperation:
    """Validate and spawn one operation, returning as soon as it starts."""
    global _current, _next_id
    with _lock:
        if _current is not None and _current.state == "running":
            raise OperationError(
                "already_running", "Another schema operation is already running."
            )
        args = validate_request(action, schema, replace, census)
        operation = SchemaOperation(_next_id, action, schema, args)
        _next_id += 1
        _current = operation

    operation.append("meta", f"$ {operation.command}")
    operation.append(
        "meta",
        f"Validated {action} request for schema {schema!r}; replace={replace}.",
    )
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed vector, never a shell
            args,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env={
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
            },
        )
    except OSError as error:
        _finish(
            operation, error=f"{type(error).__name__}: {error}", on_finish=on_finish
        )
        return operation

    operation.process = process
    threading.Thread(
        target=_drain,
        args=(operation, process, on_finish),
        daemon=True,
        name=f"schema-{action}",
    ).start()
    return operation


def _drain(
    operation: SchemaOperation,
    process: subprocess.Popen,
    on_finish: Callable[[SchemaOperation], None] | None,
) -> None:
    try:
        if process.stdout is not None:
            for line in process.stdout:
                operation.append("stdout", line)
    finally:
        code = process.wait()
        if operation.state in {"running", "stopping"}:
            _finish(operation, exit_code=code, on_finish=on_finish)


def _finish(
    operation: SchemaOperation,
    exit_code: int | None = None,
    error: str | None = None,
    on_finish: Callable[[SchemaOperation], None] | None = None,
) -> None:
    operation.exit_code = exit_code
    operation.error = error
    operation.finished_at = _now()
    operation.process = None
    if operation.state == "stopping":
        operation.state = "stopped"
    elif operation.state != "stopped":
        operation.state = "failed" if error or exit_code != 0 else "succeeded"
    operation.append(
        "meta",
        "Schema operation completed."
        if operation.state == "succeeded"
        else error or f"Schema operation ended with exit code {exit_code}.",
    )
    if operation.state == "succeeded" and on_finish is not None:
        on_finish(operation)


def stop_operation() -> bool:
    """Request termination of the running operation."""
    operation = _current
    if operation is None or operation.state != "running" or operation.process is None:
        return False
    operation.append("meta", "Stop requested by the operator.")
    operation.state = "stopping"
    operation.process.terminate()
    return True
