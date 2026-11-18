"""Celery tasks of the demo app (discovered by Celery): the daily inactivity purge (U-07-T09)."""

from __future__ import annotations

from typing import Any

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .purge import purge_inactive

JOB = "numo9.demo.purge_inactive"


@platform_job(name=JOB, queue=DEFAULT)
def purge_inactive_job() -> dict[str, Any]:
    return {"purged": len(purge_inactive())}
