"""Serialize long-running backend work and expose one safe operator record.

The model and schema services still own validation and command construction.
This module owns only scheduling, lifecycle timestamps, bounded public history,
and cancellation. Browser input never reaches this layer directly.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

MAX_TASKS = 100
ACTIVE_STATES = {"queued", "running", "stopping"}


def _now() -> str:
    """Return an ISO-8601 Coordinated Universal Time timestamp."""
    return datetime.now(timezone.utc).isoformat()


class ManagedOperation(Protocol):
    """The lifecycle surface supplied by a model or schema operation."""

    state: str
    percent: int
    phase: str
    started_at: str | None
    finished_at: str | None
    process: Any

    def append(self, stream: str, text: str) -> None:
        """Append one safe public event line."""

    def public_view(self) -> dict[str, Any]:
        """Return the operation-specific public representation."""


@dataclass
class TaskEntry:
    """One operation plus allow-listed metadata and its runner."""

    task_id: str
    kind: str
    action: str
    label: str
    summary: dict[str, Any]
    operation: ManagedOperation
    runner: Callable[[], None]
    created_at: str


class TaskManager:
    """A bounded first-in/first-out queue with one worker."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._queue: deque[TaskEntry] = deque()
        self._entries: deque[TaskEntry] = deque(maxlen=MAX_TASKS)
        self._by_id: dict[str, TaskEntry] = {}
        self._next_id = 1
        self._worker: threading.Thread | None = None

    def submit(
        self,
        operation: ManagedOperation,
        *,
        kind: str,
        action: str,
        label: str,
        summary: dict[str, Any],
        runner: Callable[[], None],
    ) -> str:
        """Queue one validated operation and return its public task identifier."""
        with self._condition:
            task_id = f"task-{self._next_id}"
            self._next_id += 1
            entry = TaskEntry(
                task_id=task_id,
                kind=kind,
                action=action,
                label=label,
                summary=dict(summary),
                operation=operation,
                runner=runner,
                created_at=_now(),
            )
            operation.state = "queued"
            operation.percent = 0
            operation.phase = "Waiting for the operator queue"
            operation.started_at = None
            operation.finished_at = None
            operation.append("queue", "Accepted by the single-worker operator queue.")
            self._queue.append(entry)
            self._entries.appendleft(entry)
            self._by_id[task_id] = entry
            self._trim_index()
            self._ensure_worker()
            self._condition.notify_all()
            return task_id

    def register_terminal(
        self,
        operation: ManagedOperation,
        *,
        kind: str,
        action: str,
        label: str,
        summary: dict[str, Any],
    ) -> str:
        """Expose a preparation failure that occurred before queue admission."""
        with self._condition:
            task_id = f"task-{self._next_id}"
            self._next_id += 1
            entry = TaskEntry(
                task_id,
                kind,
                action,
                label,
                dict(summary),
                operation,
                lambda: None,
                _now(),
            )
            self._entries.appendleft(entry)
            self._by_id[task_id] = entry
            self._trim_index()
            return task_id

    def state(self) -> dict[str, Any]:
        """Return newest-first tasks and queue concurrency."""
        with self._condition:
            return {
                "concurrency": 1,
                "tasks": [self._public(entry) for entry in self._entries],
            }

    def get(self, task_id: str) -> dict[str, Any] | None:
        """Return one task, or ``None`` when history no longer retains it."""
        with self._condition:
            entry = self._by_id.get(task_id)
            return self._public(entry) if entry else None

    def stop(self, task_id: str) -> str:
        """Cancel a queued task or request termination of a running one."""
        with self._condition:
            entry = self._by_id.get(task_id)
            if entry is None:
                return "missing"
            operation = entry.operation
            if operation.state == "queued":
                try:
                    self._queue.remove(entry)
                except ValueError:
                    pass
                operation.state = "stopped"
                operation.phase = "Stopped before start"
                operation.finished_at = _now()
                operation.append("queue", "Cancelled before a worker started the task.")
                return "stopped"
            if operation.state != "running" or operation.process is None:
                return "terminal"
            operation.state = "stopping"
            operation.phase = "Stop requested"
            operation.append("meta", "Stop requested by the operator.")
            operation.process.terminate()
            return "stopping"

    def reset(self) -> None:
        """Clear non-running state between tests without killing real children."""
        with self._condition:
            for entry in list(self._queue):
                entry.operation.state = "stopped"
            self._queue.clear()
            running = [
                entry
                for entry in self._entries
                if entry.operation.state in {"running", "stopping"}
            ]
            self._entries = deque(running, maxlen=MAX_TASKS)
            self._by_id = {entry.task_id: entry for entry in running}

    def _ensure_worker(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._work,
            daemon=True,
            name="backend-task-worker",
        )
        self._worker.start()

    def _work(self) -> None:
        while True:
            with self._condition:
                while not self._queue:
                    self._condition.wait()
                entry = self._queue.popleft()
                operation = entry.operation
                if operation.state != "queued":
                    continue
                operation.state = "running"
                operation.percent = max(1, operation.percent)
                operation.phase = "Starting worker"
                operation.started_at = _now()
                operation.append("queue", "Worker started the task.")
            try:
                entry.runner()
                if operation.state == "running":
                    operation.state = "succeeded"
                    operation.percent = 100
                    operation.phase = "Complete"
                    operation.finished_at = _now()
                    operation.append("queue", "Task completed.")
            except Exception as error:  # noqa: BLE001 - terminal public task state
                operation.state = "failed"
                operation.phase = "Failed"
                operation.finished_at = _now()
                if hasattr(operation, "error"):
                    operation.error = f"{type(error).__name__}: {str(error)[:300]}"
                operation.append(
                    "stderr", f"{type(error).__name__}: {str(error)[:500]}"
                )

    def _public(self, entry: TaskEntry | None) -> dict[str, Any]:
        if entry is None:
            return {}
        view = entry.operation.public_view()
        queue_position = None
        if entry.operation.state == "queued":
            try:
                queue_position = list(self._queue).index(entry) + 1
            except ValueError:
                queue_position = None
        return {
            **view,
            "id": entry.task_id,
            "kind": entry.kind,
            "action": entry.action,
            "label": entry.label,
            "summary": dict(entry.summary),
            "createdAt": entry.created_at,
            "queuePosition": queue_position,
        }

    def _trim_index(self) -> None:
        retained = {entry.task_id for entry in self._entries}
        self._by_id = {
            task_id: entry
            for task_id, entry in self._by_id.items()
            if task_id in retained
        }


manager = TaskManager()


def tasks_state() -> dict[str, Any]:
    """Return the shared manager's public list."""
    return manager.state()


def task_detail(task_id: str) -> dict[str, Any] | None:
    """Return one shared-manager task."""
    return manager.get(task_id)


def stop_task(task_id: str) -> str:
    """Stop one shared-manager task by exact identifier."""
    return manager.stop(task_id)
