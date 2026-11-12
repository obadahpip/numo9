"""Retry policy of background jobs (A-08-T04).

A job whose body raises is **retried automatically** with exponential backoff and jitter, up to
the task's ``max_retries`` (default 5, so 6 tries in all). Between tries the run is ``retrying``:
the error is already on the run (the job tray shows it with "Waiting to try again"), and
``next_retry_at`` says when the next try is due.

Not retried — the run is ``failed`` at once:

- ``JobError(..., retry=False)`` (the default): retrying cannot fix bad input or a missing record;
- a result that is not JSON (``JobResultNotJSON``): a programming error;
- message errors (``JobRunRequired``, ``JobRunMismatch``) and ``OrgTask`` errors (``throws``).

**Dead letters.** When the retries are used up the run becomes ``dead``: it keeps the task, its
arguments (``payload``) and the last error, and nothing retries it again by itself. Dead runs are
the dead-letter queue: listed in the platform console (A-08-T08), where they are retried or
purged, and the person who started one can retry it from the job tray (A-08-T07).

**Poison messages.** A message that kills its worker (out of memory, the hard time limit) is
redelivered by Celery (``acks_late`` + ``reject_on_worker_lost``) and finds its run still
``running``. Each redelivery counts as a try; once the tries are used up the run is ``dead``
(``job.worker_lost``) instead of taking another worker down.

**Delay.** Try *n* (n = 1 for the first retry) waits ``d = min(backoff_max, backoff_base ×
2^(n-1))`` seconds with equal jitter: a random delay between ``d/2`` and ``d``, so jobs that failed
together (a provider outage) do not all come back at the same second. Defaults: 30 s base,
1 h cap — 15–30 s, 30–60 s, 1–2 min, 2–4 min, 4–8 min. Set ``backoff_base`` / ``backoff_max`` /
``max_retries`` on the task to change them.

**Retrying by hand** (``retry_run``): a ``failed`` or ``dead`` run is queued again — same run,
same idempotency key, fresh retry budget, its error cleared — and its message sent again.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from numo9.i18n import errors
from numo9.i18n.errors import api_error

from .models import RETRYABLE, JobRun, JobStatus

logger = logging.getLogger("numo9.jobs")

DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_BASE = 30.0
DEFAULT_BACKOFF_MAX = 60.0 * 60

_random = secrets.SystemRandom()


class JobResultNotJSON(TypeError):
    """A job returned something that cannot be stored as JSON (never retried)."""


def backoff_delay(
    retry_number: int,
    *,
    base: float = DEFAULT_BACKOFF_BASE,
    cap: float = DEFAULT_BACKOFF_MAX,
    uniform: Any = None,
) -> float:
    """Seconds to wait before retry ``retry_number`` (1-based): exponential, equal jitter."""
    if retry_number < 1:
        raise ValueError("retry_number starts at 1.")
    ceiling = min(cap, base * (2 ** (retry_number - 1)))
    draw = uniform or _random.uniform
    return float(ceiling / 2 + draw(0, ceiling / 2))


def retry_run(run: JobRun, *, by: Any = None) -> JobRun:
    """Queue a ``failed`` or ``dead`` run again and send it (job tray, console).

    Refused with ``job.not_retryable`` (409) unless the run has failed — a run that is waiting,
    running or done is left alone, and two people clicking Retry at once send it once.
    """
    from .runtime import send, task_for  # runtime imports this module

    task = task_for(run)
    new_task_id = str(uuid.uuid4())
    with transaction.atomic():
        changed = JobRun.platform_runs.filter(pk=run.pk, status__in=RETRYABLE).update(
            status=JobStatus.QUEUED,
            error_code="",
            error_message="",
            error_detail="",
            finished_at=None,
            next_retry_at=None,
            progress_done=0,
            progress_message="",
            result=None,
            result_url="",
            celery_task_id=new_task_id,
            updated_at=timezone.now(),
        )
        if not changed:
            raise api_error(errors.JOB_NOT_RETRYABLE)
        run.refresh_from_db()
        logger.info(
            "job.retried_by_hand %s %s",
            run.task_name,
            run.public_id,
            extra={
                "job": {
                    "id": str(run.public_id),
                    "task": run.task_name,
                    "by": str(getattr(by, "public_id", "")) or None,
                }
            },
        )
        transaction.on_commit(lambda: send(task, run), robust=False)
    return run
