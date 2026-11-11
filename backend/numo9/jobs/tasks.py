"""Platform tasks of the jobs app (A-08-T01)."""

from __future__ import annotations

from typing import Any

from celery import shared_task

from .queues import DEFAULT


@shared_task(name="numo9.jobs.ping", queue=DEFAULT, ignore_result=False)  # type: ignore[untyped-decorator]
def ping(payload: Any = None) -> dict[str, Any]:
    """Health check: a worker consuming this proves broker, worker and result backend work.

    Used by ``manage.py celery_ping`` (deploy checks) and the worker tests. Holds no tenant data,
    so it is a platform task (A-01-T07 org-scoped tasks need an explicit ``org_id``).
    """
    return {"pong": True, "payload": payload}
