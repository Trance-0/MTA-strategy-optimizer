"""List, inspect, and stop unified backend operator tasks."""

from __future__ import annotations

from flask import Blueprint, jsonify

from backend.services.tasks import stop_task, task_detail, tasks_state

blueprint = Blueprint("tasks", __name__)


@blueprint.get("/api/tasks")
def list_tasks():
    """Return bounded task history and queue concurrency."""
    return jsonify(tasks_state())


@blueprint.get("/api/tasks/<task_id>")
def get_task(task_id: str):
    """Return one task with its complete retained event log."""
    task = task_detail(task_id)
    if task is None:
        return jsonify({"error": "task_not_found", "message": "Task not found."}), 404
    return jsonify(task)


@blueprint.delete("/api/tasks/<task_id>")
def delete_task(task_id: str):
    """Cancel a queued task or terminate a running child."""
    outcome = stop_task(task_id)
    if outcome == "missing":
        return jsonify({"error": "task_not_found", "message": "Task not found."}), 404
    task = task_detail(task_id)
    if outcome == "terminal":
        return (
            jsonify(
                {
                    "error": "task_finished",
                    "message": "Task is already finished.",
                    "task": task,
                }
            ),
            409,
        )
    return jsonify({"ok": True, "task": task})
