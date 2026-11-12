"""Job base class: idempotency, organisation context, JobRun lifecycle, logs (A-08-T03).

Every background job that a person waits for or that must not run twice is a *job task*: a
Celery task whose base is ``JobTask`` (organisation jobs) or ``PlatformJobTask`` (platform jobs
with no organisation). Jobs are started with ``start_job`` — never with ``delay()``:

    @org_job(name="numo9.contacts.bulk_archive", queue=queues.REPORTS)
    def bulk_archive(*, org_id: str, contact_ids: list[str]) -> dict[str, int]:
        for done, cid in enumerate(contact_ids, 1):
            ...
            report_progress(done, len(contact_ids))
        return {"archived": len(contact_ids)}

    run = start_job(bulk_archive, organisation=org, key=f"archive:{batch_id}",
                    created_by=user, contact_ids=ids)

``start_job``

1. builds the **idempotency key** ``<task name>:<organisation public id | platform>:<key>`` (a
   random key when the caller gives none; long keys are hashed) — so the same caller key in two
   organisations never collides;
2. creates the ``JobRun`` (status ``queued``, the keyword arguments kept as ``payload``). The key
   is unique in the database: when a run with that key exists — even one another process created
   a moment ago — that run is returned (``run.started_now`` is False) and **nothing is sent**;
3. sends the Celery message once the surrounding transaction commits (the worker always finds the
   row), with ``job_run_id`` added to the keyword arguments. If the broker refuses, the run is
   marked ``failed`` (``job.not_queued``) and the error is raised to the caller.

When a worker runs the message, the base class

1. refuses a message without ``job_run_id`` (``JobRunRequired`` — sent with ``delay()``), naming
   an unknown run, or whose task or organisation differs from the run's (``JobRunMismatch`` — a
   forged or misrouted message); these are never retried;
2. takes a PostgreSQL **advisory lock** on the run for as long as it runs (released when the
   process dies, so a crashed run can be picked up again). A second delivery of the same run while
   the lock is held is skipped — the worker holding it finishes the job;
3. skips a run that has **already finished** (a redelivered message after success): the stored
   result is returned and the body does not run again;
4. marks the run ``running`` (attempt count, worker, start time) and runs the body — organisation
   jobs inside the organisation's tenant context (``OrgTask``, A-01-T07). With ``atomic = True``
   (the default) the body and the ``succeeded`` mark commit in **one transaction**: a job that
   dies half-way leaves nothing behind, and the rerun applies its effect exactly once. Long jobs
   that report progress or commit in steps set ``atomic=False`` and make each step safe to repeat;
5. stores the result (JSON) and the finish time — or the error (A-08-T04 adds retries).

Inside the body, ``current_job()`` is the run, ``report_progress(done, total, note)`` updates the
job tray immediately (in an atomic job it becomes visible at commit), and ``set_result_url(url)``
gives the run a result link.

**Logs.** Every lifecycle step logs one ``numo9.jobs`` record with a ``job`` field (run id, task,
organisation, attempt, status, duration). While the body runs, every log line it writes carries
``job_id``, ``job_task`` and ``org_id`` (structlog context variables).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

import structlog
from celery import Task, shared_task
from django.db import IntegrityError, connection, transaction
from django.utils import timezone, translation

from numo9.i18n import errors
from numo9.i18n.errors import ErrorMessage
from numo9.security.scrubbing import scrub_text
from numo9.tenancy.models import Organisation
from numo9.tenancy.tasks import ORG_ID, OrgTask

from .models import JobRun, JobStatus
from .queues import DEFAULT

logger = logging.getLogger("numo9.jobs")

JOB_RUN_ID = "job_run_id"
PLATFORM_SCOPE = "platform"
KEY_MAX_LENGTH = 255
#: First half of the 64-bit advisory-lock key: "A08" — the second half is the run's id.
_LOCK_NAMESPACE = 0xA08 << 40


class JobRunRequired(RuntimeError):
    """A job task was sent without ``job_run_id`` — start jobs with ``start_job()``."""


class JobRunMismatch(LookupError):
    """The message names no run, or a run of another task or organisation."""


class JobError(Exception):
    """An error a job body raises on purpose, with a message the person who started it reads.

    ``retry=False`` (default): retrying cannot help (bad input, a record that no longer exists) —
    the run is ``failed`` at once. ``retry=True``: a temporary problem (A-08-T04 retries it).
    """

    def __init__(self, error: ErrorMessage | str, *, retry: bool = False, **params: Any) -> None:
        # A code string is accepted so Celery can rebuild the exception from its JSON form.
        if isinstance(error, str):
            error = errors.CATALOGUE.get(error, errors.JOB_FAILED)
        self.error = error
        self.retry = retry
        self.params = params
        super().__init__(error.code)


_current: ContextVar[JobRun | None] = ContextVar("numo9_current_job", default=None)


def current_job() -> JobRun | None:
    """The run of the job executing in this thread, or None outside a job."""
    return _current.get()


def report_progress(done: int, total: int | None = None, message: str = "") -> None:
    """Record progress of the current job: ``done`` of ``total`` steps (total may be unknown).

    Written straight away, so the job tray shows it while the job runs (inside an atomic job it
    becomes visible when the job's transaction commits). ``done`` is kept within ``total``.
    """
    run = current_job()
    if run is None:
        raise RuntimeError("report_progress() called outside a job.")
    done = max(0, int(done))
    if total is not None:
        total = max(0, int(total))
        done = min(done, total)
    run.progress_done, run.progress_total, run.progress_message = done, total, message[:200]
    JobRun.platform_runs.filter(pk=run.pk).update(
        progress_done=done,
        progress_total=total,
        progress_message=run.progress_message,
        updated_at=timezone.now(),
    )


def set_result_url(url: str) -> None:
    """Give the current job a result link (a download, a report): shown in the job tray."""
    run = current_job()
    if run is None:
        raise RuntimeError("set_result_url() called outside a job.")
    run.result_url = url[:500]


# ---- starting a job ----------------------------------------------------------------------------


def idempotency_key(task_name: str, organisation: Organisation | None, key: str | None) -> str:
    """``<task>:<organisation public id | platform>:<key>``; a random key when none is given."""
    scope = str(organisation.public_id) if organisation is not None else PLATFORM_SCOPE
    caller = key if key else uuid.uuid4().hex
    full = f"{task_name}:{scope}:{caller}"
    if len(full) > KEY_MAX_LENGTH:
        digest = hashlib.sha256(caller.encode()).hexdigest()
        full = f"{task_name}:{scope}:sha256:{digest}"[:KEY_MAX_LENGTH]
    return full


def start_job(
    task: Task,
    *,
    organisation: Organisation | None = None,
    key: str | None = None,
    created_by: Any = None,
    countdown: float | None = None,
    **kwargs: Any,
) -> JobRun:
    """Start ``task`` once per ``key`` (see the module docstring) and return its run."""
    if not isinstance(task, JobTask | PlatformJobTask):
        raise TypeError(f"{task.name} is not a job task: use @org_job or @platform_job.")
    if isinstance(task, JobTask):
        if organisation is None:
            raise ValueError(f"{task.name} is an organisation job: pass organisation=.")
        if ORG_ID in kwargs:
            raise ValueError("Pass organisation=, not org_id=: start_job fills it in.")
        kwargs[ORG_ID] = str(organisation.public_id)
    elif organisation is not None:
        raise ValueError(f"{task.name} is a platform job: it has no organisation.")
    if JOB_RUN_ID in kwargs:
        raise ValueError(f"{JOB_RUN_ID} is set by start_job.")
    try:
        json.dumps(kwargs)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{task.name}: job arguments must be JSON ({exc}).") from exc

    full_key = idempotency_key(task.name, organisation, key)
    try:
        with transaction.atomic():
            run: JobRun = JobRun.platform_runs.create(
                organisation=organisation,
                task_name=task.name,
                queue=getattr(task, "queue", None) or DEFAULT,
                payload=kwargs,
                idempotency_key=full_key,
                max_retries=task.max_retries if task.max_retries is not None else 0,
                created_by=created_by,
                celery_task_id=str(uuid.uuid4()),
            )
    except IntegrityError:
        existing: JobRun = JobRun.platform_runs.get(idempotency_key=full_key)
        existing.started_now = False  # type: ignore[attr-defined]
        _log(logging.INFO, "job.duplicate", existing)
        return existing
    run.started_now = True  # type: ignore[attr-defined]
    _log(logging.INFO, "job.queued", run)
    transaction.on_commit(lambda: send(task, run, countdown=countdown), robust=False)
    return run


def send(task: Task, run: JobRun, *, countdown: float | None = None) -> None:
    """Send the run's Celery message; a broker failure marks the run failed and is raised."""
    try:
        task.apply_async(
            kwargs={**run.payload, JOB_RUN_ID: str(run.public_id)},
            queue=run.queue,
            task_id=run.celery_task_id,
            countdown=countdown,
        )
    except Exception as exc:
        _finish_failed(run, errors.JOB_NOT_QUEUED, {}, exc)
        raise


# ---- running a job -----------------------------------------------------------------------------


@contextmanager
def run_lock(run: JobRun) -> Iterator[bool]:
    """Session advisory lock on the run (PostgreSQL); True when this process holds it.

    A process that dies drops its connection and with it the lock, so a run left ``running`` by a
    killed worker can be taken over by the redelivered message. Other databases (local SQLite)
    have no second worker to race with: the lock is always granted.
    """
    if connection.vendor != "postgresql":
        yield True
        return
    lock_key = _LOCK_NAMESPACE | run.pk
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_key])
        acquired = bool(cursor.fetchone()[0])
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_key])


def _load_run(task: Task, run_id: Any, org_id: str | None) -> JobRun:
    if not run_id:
        raise JobRunRequired(f"{task.name} was sent without {JOB_RUN_ID}: use start_job().")
    try:
        public_id = uuid.UUID(str(run_id))
    except ValueError as exc:
        raise JobRunMismatch(f"{task.name}: {JOB_RUN_ID} {run_id!r} is not a UUID.") from exc
    run: JobRun | None = (
        JobRun.platform_runs.select_related("organisation", "created_by")
        .filter(public_id=public_id)
        .first()
    )
    if run is None:
        raise JobRunMismatch(f"{task.name}: no job run {public_id}.")
    run_org = run.organisation.public_id if run.organisation else None
    try:
        message_org = uuid.UUID(org_id) if org_id else None
    except ValueError:
        message_org = None
    if run.task_name != task.name or run_org != message_org:
        raise JobRunMismatch(f"{task.name}: job run {public_id} belongs to another job.")
    return run


def execute(task: Task, run_id: Any, org_id: str | None, body: Callable[[], Any]) -> Any:
    """Run one delivery of a job (steps 1–5 of the module docstring)."""
    run = _load_run(task, run_id, org_id)
    with run_lock(run) as acquired:
        if not acquired:
            _log(logging.WARNING, "job.skipped_locked", run)
            return None
        run.refresh_from_db()
        if run.is_finished:
            _log(logging.INFO, "job.skipped_finished", run)
            return run.result
        _mark_running(task, run)
        started = time.monotonic()
        token = _current.set(run)
        context = structlog.contextvars.bound_contextvars(
            job_id=str(run.public_id), job_task=run.task_name, org_id=org_id
        )
        try:
            with context:
                if getattr(task, "atomic", True):
                    with transaction.atomic():
                        result = body()
                        _finish_succeeded(run, result)
                else:
                    result = body()
                    _finish_succeeded(run, result)
        except Exception as exc:
            return handle_failure(task, run, exc, started)
        finally:
            _current.reset(token)
        _log(logging.INFO, "job.succeeded", run, duration_ms=_ms(started))
        return result


def handle_failure(task: Task, run: JobRun, exc: Exception, started: float) -> Any:
    """The body raised: record the error on the run and re-raise (A-08-T04 adds retries)."""
    if isinstance(exc, JobError):
        _finish_failed(run, exc.error, exc.params, exc)
    else:
        _finish_failed(run, errors.JOB_FAILED, {}, exc)
    _log(logging.ERROR, "job.failed", run, duration_ms=_ms(started), error=type(exc).__name__)
    raise exc


def _mark_running(task: Task, run: JobRun) -> None:
    now = timezone.now()
    request = getattr(task, "request", None)
    hostname = getattr(request, "hostname", None) or "local"
    run.status = JobStatus.RUNNING
    run.attempts += 1
    run.started_at = run.started_at or now
    run.next_retry_at = None
    run.worker = f"{hostname}:{os.getpid()}"[:255]
    run.celery_task_id = (getattr(request, "id", None) or run.celery_task_id or "")[:255]
    run.save(
        update_fields=[
            "status",
            "attempts",
            "started_at",
            "next_retry_at",
            "worker",
            "celery_task_id",
            "updated_at",
        ]
    )
    _log(logging.INFO, "job.started", run)


def _finish_succeeded(run: JobRun, result: Any) -> None:
    try:
        json.dumps(result)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{run.task_name}: a job's result must be JSON ({exc}).") from exc
    run.status = JobStatus.SUCCEEDED
    run.result = result
    run.finished_at = timezone.now()
    if run.progress_total is not None:
        run.progress_done = run.progress_total
    run.error_code = run.error_message = run.error_detail = ""
    run.save(
        update_fields=[
            "status",
            "result",
            "result_url",
            "finished_at",
            "progress_done",
            "error_code",
            "error_message",
            "error_detail",
            "updated_at",
        ]
    )


def _error_text(run: JobRun, error: ErrorMessage, params: dict[str, Any]) -> str:
    """The message in the language of the person who started the job (platform: default)."""
    locale = getattr(run.created_by, "locale", None) or (
        run.organisation.locale if run.organisation is not None else None
    )
    with translation.override(locale or None):
        return error.text(**params)


def _detail(exc: BaseException) -> str:
    return scrub_text(f"{type(exc).__module__}.{type(exc).__qualname__}: {exc}")[:4000]


def _record_error(
    run: JobRun, error: ErrorMessage, params: dict[str, Any], exc: BaseException
) -> None:
    run.error_code = error.code
    run.error_message = _error_text(run, error, params)
    run.error_detail = _detail(exc)


def _finish_failed(
    run: JobRun,
    error: ErrorMessage,
    params: dict[str, Any],
    exc: BaseException,
    status: str = JobStatus.FAILED,
) -> None:
    _record_error(run, error, params, exc)
    run.status = status
    run.finished_at = timezone.now()
    run.next_retry_at = None
    run.save(
        update_fields=[
            "status",
            "error_code",
            "error_message",
            "error_detail",
            "finished_at",
            "next_retry_at",
            "updated_at",
        ]
    )


# ---- logs --------------------------------------------------------------------------------------


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _log(level: int, event: str, run: JobRun, **fields: Any) -> None:
    job = {
        "id": str(run.public_id),
        "task": run.task_name,
        "org_id": str(run.organisation.public_id) if run.organisation is not None else None,
        "queue": run.queue,
        "status": run.status,
        "attempt": run.attempts,
        **fields,
    }
    logger.log(level, "%s %s %s", event, run.task_name, run.public_id, extra={"job": job})


# ---- base classes and decorators ---------------------------------------------------------------

#: Never retried automatically: the message itself is wrong.
_MESSAGE_ERRORS = (JobRunRequired, JobRunMismatch)


class JobTask(OrgTask):
    """Base class of organisation jobs (on top of ``OrgTask``: org_id required, tenant context)."""

    abstract = True
    atomic = True
    max_retries = 5
    typing = False  # job_run_id is not a body argument; start_job validates the call
    throws: tuple[type[Exception], ...] = (*OrgTask.throws, *_MESSAGE_ERRORS)

    def apply_async(
        self, args: Any = None, kwargs: dict[str, Any] | None = None, **options: Any
    ) -> Any:
        if not (kwargs or {}).get(JOB_RUN_ID):
            raise JobRunRequired(f"{self.name} is a job: start it with start_job().")
        return super().apply_async(args, kwargs, **options)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        run_id = kwargs.pop(JOB_RUN_ID, None)
        org_id = kwargs.get(ORG_ID)
        call = super().__call__  # OrgTask: validates org_id, sets the tenant context
        return execute(self, run_id, str(org_id) if org_id else None, lambda: call(*args, **kwargs))


class PlatformJobTask(Task):  # type: ignore[misc]  # celery is untyped
    """Base class of platform jobs: no organisation, no tenant context."""

    abstract = True
    atomic = True
    max_retries = 5
    typing = False
    throws = _MESSAGE_ERRORS

    def apply_async(
        self, args: Any = None, kwargs: dict[str, Any] | None = None, **options: Any
    ) -> Any:
        if not (kwargs or {}).get(JOB_RUN_ID):
            raise JobRunRequired(f"{self.name} is a job: start it with start_job().")
        return super().apply_async(args, kwargs, **options)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        run_id = kwargs.pop(JOB_RUN_ID, None)
        if ORG_ID in kwargs:
            raise JobRunMismatch(f"{self.name} is a platform job: it takes no org_id.")
        call = super().__call__
        return execute(self, run_id, None, lambda: call(*args, **kwargs))


def org_job(*args: Any, **options: Any) -> Callable[..., Any]:
    """``shared_task`` with ``JobTask`` as base: ``@org_job(name=..., queue=...)``."""
    options.setdefault("base", JobTask)
    if not issubclass(options["base"], JobTask):
        raise TypeError("org_job() base must be JobTask or a subclass of it.")
    decorator: Callable[..., Any] = shared_task(*args, **options)
    return decorator


def platform_job(*args: Any, **options: Any) -> Callable[..., Any]:
    """``shared_task`` with ``PlatformJobTask`` as base: ``@platform_job(name=..., queue=...)``."""
    options.setdefault("base", PlatformJobTask)
    if not issubclass(options["base"], PlatformJobTask):
        raise TypeError("platform_job() base must be PlatformJobTask or a subclass of it.")
    decorator: Callable[..., Any] = shared_task(*args, **options)
    return decorator
