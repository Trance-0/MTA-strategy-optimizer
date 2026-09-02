"""Unified backend task queue, event log, and route tests."""

from __future__ import annotations

import threading
import time
import unittest

from backend.app import create_app
from backend.services.tasks import TaskManager


class FakeOperation:
    """Minimal managed operation used without spawning a child process."""

    def __init__(self) -> None:
        self.state = "queued"
        self.percent = 0
        self.phase = ""
        self.started_at = None
        self.finished_at = None
        self.exit_code = None
        self.error = None
        self.process = None
        self.lines = []

    def append(self, stream: str, text: str) -> None:
        self.lines.append(
            {
                "at": "2026-09-02T00:00:00+00:00",
                "stream": stream,
                "level": "INFO",
                "text": text,
            }
        )

    def public_view(self) -> dict:
        return {
            "state": self.state,
            "percent": self.percent,
            "phase": self.phase,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "exitCode": self.exit_code,
            "error": self.error,
            "command": "python fixed.py",
            "lines": list(self.lines),
            "droppedLines": 0,
        }


class QueueTests(unittest.TestCase):
    """Prove one worker preserves first-in/first-out execution."""

    def test_second_task_waits_and_a_queued_task_can_be_stopped(self) -> None:
        manager = TaskManager()
        release = threading.Event()
        started = threading.Event()
        first = FakeOperation()
        second = FakeOperation()

        def run_first() -> None:
            started.set()
            release.wait(2)
            first.state = "succeeded"
            first.percent = 100

        first_id = manager.submit(
            first,
            kind="model",
            action="attribution",
            label="Attribution",
            summary={"dataset": "safe server scope"},
            runner=run_first,
        )
        self.assertTrue(started.wait(1))
        second_id = manager.submit(
            second,
            kind="schema",
            action="derive",
            label="Parse scenarios",
            summary={"schema": "mta", "replace": False},
            runner=lambda: None,
        )

        self.assertEqual(manager.get(first_id)["state"], "running")
        self.assertEqual(manager.get(second_id)["state"], "queued")
        self.assertEqual(manager.get(second_id)["queuePosition"], 1)
        self.assertEqual(manager.stop(second_id), "stopped")
        self.assertEqual(manager.get(second_id)["state"], "stopped")
        self.assertIsNone(manager.get(second_id)["startedAt"])
        release.set()

    def test_public_record_has_safe_summary_and_lifecycle_events(self) -> None:
        manager = TaskManager()
        release = threading.Event()
        operation = FakeOperation()
        task_id = manager.submit(
            operation,
            kind="schema",
            action="initialize",
            label="Initialize database schema",
            summary={"schema": "demo", "replace": False},
            runner=lambda: release.wait(1),
        )
        for _ in range(100):
            if manager.get(task_id)["state"] == "running":
                break
            time.sleep(0.005)
        task = manager.get(task_id)
        self.assertEqual(task["summary"], {"schema": "demo", "replace": False})
        self.assertTrue(task["createdAt"])
        self.assertTrue(task["startedAt"])
        self.assertGreaterEqual(len(task["lines"]), 2)
        release.set()


class TaskRouteTests(unittest.TestCase):
    """Check list/detail/stop routes use precise errors."""

    def setUp(self) -> None:
        self.client = create_app().test_client()

    def test_list_route_is_registered(self) -> None:
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["concurrency"], 1)

    def test_unknown_task_is_404(self) -> None:
        response = self.client.delete("/api/tasks/task-does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "task_not_found")


if __name__ == "__main__":
    unittest.main()
