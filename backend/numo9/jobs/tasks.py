"""Platform tasks of the jobs app: worker check (A-08-T01), job-run retention purge (A-08-T05)."""

from __future__ import annotations

from typing import Any

from celery import shared_task
from django.utils import timezone

from .models import FINISHED, RETENTION, JobRun
from .queues import DEFAULT
from .runtime import platform_job

PURGE_BATCH = 1000


@shared_task(name="numo9.jobs.ping", queue=DEFAULT, ignore_result=False)  # type: ignore[untyped-decorator]
def ping(payload: Any = None) -> dict[str, Any]:
    """Health check: a worker consuming this proves broker, worker and result backend work.

    Used by ``manage.py celery_ping`` (deploy checks) and the worker tests. Holds no tenant data,
    so it is a platform task (A-01-T07 org-scoped tasks need an explicit ``org_id``).
    """
    return {"pong": True, "payload": payload}


@platform_job(name="numo9.jobs.purge_job_runs", queue=DEFAULT)
def purge_job_runs() -> dict[str, int]:
    """Delete job runs that finished more than ``RETENTION`` (30 days) ago — daily, by beat.

    Runs still waiting, running or retrying are kept whatever their age. Deletes in batches so a
    large backlog never holds one long lock.
    """
    cutoff = timezone.now() - RETENTION
    old = JobRun.platform_runs.filter(status__in=FINISHED, finished_at__lt=cutoff)
    deleted = 0
    while batch := list(old.values_list("pk", flat=True)[:PURGE_BATCH]):
        deleted += JobRun.platform_runs.filter(pk__in=batch).delete()[0]
    return {"deleted": deleted}
