"""Celery tasks of billing (discovered by ``app.autodiscover_tasks()``)."""

from __future__ import annotations

from typing import Any

from celery import shared_task

from numo9.jobs.queues import HIGH
from numo9.jobs.retry import backoff_delay

from .dunning import run_dunning_job
from .processing import EventFailed, process_event

__all__ = ["process_stripe_event", "run_dunning_job"]

TASK_NAME = "numo9.billing.process_stripe_event"
MAX_RETRIES = 8


@shared_task(bind=True, name=TASK_NAME, queue=HIGH, max_retries=MAX_RETRIES, acks_late=True)  # type: ignore[untyped-decorator]
def process_stripe_event(self: Any, event_pk: int) -> str:
    """Process one stored Stripe event; retried with backoff while its handler fails."""
    try:
        return process_event(event_pk)
    except EventFailed as error:
        raise self.retry(countdown=backoff_delay(self.request.retries + 1), exc=error) from error
