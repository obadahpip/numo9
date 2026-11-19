"""Celery tasks of the metering app (discovered by Celery): the aggregator (S-06-T07)."""

from __future__ import annotations

from typing import Any

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .service import aggregate

JOB = "numo9.metering.aggregate"


# Commits batch by batch (each batch saves its offset with its sums, so a repeat is harmless).
@platform_job(name=JOB, queue=DEFAULT, atomic=False)
def aggregate_job() -> dict[str, Any]:
    result = aggregate()
    return {"events": result.events, "rows": result.rows, "batches": result.batches}
