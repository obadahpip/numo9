"""Helpers for background-job tests (A-08)."""

from __future__ import annotations

from typing import Any


def deliver(task: Any, message: dict[str, Any]) -> Any:
    """Run a captured message the way a worker does (raises what the task raised)."""
    return task.apply(kwargs=message["kwargs"], task_id=message["task_id"]).get(propagate=True)
