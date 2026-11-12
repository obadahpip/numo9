"""Retry policy (A-08-T04): exponential backoff + jitter, max retries, dead letters, visible error.

Acceptance: a failed job is retried and visible — between tries the run is ``retrying`` with the
error and the time of the next try; when the tries are used up it is ``dead`` (the dead-letter
state) with its arguments kept, and a person can send it again.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from celery.contrib.testing.worker import start_worker
from celery.exceptions import Retry
from django.utils import timezone

from numo9 import celery_app
from numo9.i18n import errors
from numo9.i18n.errors import CatalogueError
from numo9.jobs.models import JobRun, JobStatus
from numo9.jobs.queues import QUEUE_NAMES
from numo9.jobs.retry import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_BACKOFF_MAX,
    backoff_delay,
    retry_run,
)
from numo9.jobs.runtime import JobError, org_job, platform_job, start_job
from numo9.tenancy.models import Organisation
from tests.job_helpers import deliver

TRIES: dict[str, int] = {}


@platform_job(name="tests.retry.flaky", max_retries=3)
def flaky(*, name: str, fail_times: int) -> dict[str, int]:
    """Fails ``fail_times`` times, then succeeds."""
    TRIES[name] = TRIES.get(name, 0) + 1
    if TRIES[name] <= fail_times:
        raise ConnectionError("the provider did not answer")
    return {"tries": TRIES[name]}


@platform_job(name="tests.retry.always_down", max_retries=2)
def always_down(*, name: str) -> None:
    TRIES[name] = TRIES.get(name, 0) + 1
    raise JobError(errors.JOB_NOT_QUEUED, retry=True)


@platform_job(name="tests.retry.bad_input", max_retries=4)
def bad_input(*, name: str) -> None:
    TRIES[name] = TRIES.get(name, 0) + 1
    raise JobError(errors.JOB_NOT_QUEUED)  # retry=False: retrying cannot help


@platform_job(name="tests.retry.not_json", max_retries=4)
def not_json(*, name: str) -> Any:
    TRIES[name] = TRIES.get(name, 0) + 1
    return {"x": {1, 2}}


@org_job(name="tests.retry.org_flaky", max_retries=1, backoff_base=0.2, backoff_max=0.5)
def org_flaky(*, org_id: str, name: str) -> dict[str, int]:
    TRIES[name] = TRIES.get(name, 0) + 1
    if TRIES[name] == 1:
        raise ConnectionError("first try fails")
    return {"tries": TRIES[name]}


@pytest.fixture(autouse=True)
def _tries() -> Iterator[None]:
    TRIES.clear()
    yield
    TRIES.clear()


# ---- the delay ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("retry", "ceiling"), [(1, 30), (2, 60), (3, 120), (4, 240), (5, 480), (8, 3600), (30, 3600)]
)
def test_backoff_is_exponential_and_capped(retry: int, ceiling: float) -> None:
    low = backoff_delay(retry, uniform=lambda a, b: a)
    high = backoff_delay(retry, uniform=lambda a, b: b)
    assert (low, high) == (ceiling / 2, ceiling)


def test_backoff_has_jitter_within_half_to_full() -> None:
    delays = {backoff_delay(3) for _ in range(50)}
    assert len(delays) > 1  # not every job comes back at the same second
    assert all(60 <= d <= 120 for d in delays)


def test_backoff_defaults_and_bounds() -> None:
    assert (DEFAULT_BACKOFF_BASE, DEFAULT_BACKOFF_MAX) == (30.0, 3600.0)
    assert backoff_delay(2, base=1, cap=100, uniform=lambda a, b: b) == 2
    with pytest.raises(ValueError):
        backoff_delay(0)


# ---- retried and visible -----------------------------------------------------------------------


@pytest.mark.django_db
def test_failed_try_is_visible_while_waiting_for_the_next(sent: list[dict[str, Any]]) -> None:
    run = start_job(flaky, key="visible", name="visible", fail_times=1)
    captured: dict[str, Any] = {}

    def no_resend(self: Any, *args: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        raise Retry("retry later", None)

    before = timezone.now()
    task_class = celery_app.tasks[flaky.name].__class__
    with mock.patch.object(task_class, "retry", no_resend):
        result = flaky.apply(kwargs=sent[0]["kwargs"], task_id=sent[0]["task_id"])
    assert result.state == "RETRY"  # handed back to Celery to send again later
    run.refresh_from_db()
    assert run.status == JobStatus.RETRYING
    assert run.error_code == "job.failed" and run.error_message  # visible in the job tray
    assert run.error_detail.endswith("ConnectionError: the provider did not answer")
    assert run.finished_at is None
    assert 15 <= captured["countdown"] <= 30  # first retry: 15–30 s
    assert run.next_retry_at is not None
    expected = before + timedelta(seconds=captured["countdown"])
    assert abs((run.next_retry_at - expected).total_seconds()) < 5
    assert captured["max_retries"] == 3


@pytest.mark.django_db
def test_failed_job_is_retried_until_it_succeeds(
    sent: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    run = start_job(flaky, key="recovers", name="recovers", fail_times=2)
    with caplog.at_level(logging.INFO, logger="numo9.jobs"):
        assert deliver(flaky, sent[0]) == {"tries": 3}  # eager: retries run in place
    run.refresh_from_db()
    assert (run.status, run.attempts) == (JobStatus.SUCCEEDED, 3)
    assert run.error_code == run.error_message == run.error_detail == ""
    assert run.next_retry_at is None
    events = [r.getMessage().split()[0] for r in caplog.records if r.name == "numo9.jobs"]
    assert events.count("job.retrying") == 2
    retrying = [r for r in caplog.records if r.getMessage().startswith("job.retrying")]
    assert [r.job["retry"] for r in retrying] == [1, 2]  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_retries_used_up_dead_letter_the_run(
    sent: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    run = start_job(always_down, key="down", name="down")
    with caplog.at_level(logging.ERROR, logger="numo9.jobs"), pytest.raises(JobError):
        deliver(always_down, sent[0])
    run.refresh_from_db()
    assert TRIES["down"] == 3  # 1 try + max_retries 2
    assert (run.status, run.attempts) == (JobStatus.DEAD, 3)
    assert run.error_code == "job.not_queued"  # the job's own message stays visible
    assert run.finished_at is not None
    assert run.payload == {"name": "down"}  # kept, so the dead letter can be sent again
    assert any(r.getMessage().startswith("job.dead") for r in caplog.records)


@pytest.mark.django_db
@pytest.mark.parametrize(("task", "error"), [(bad_input, JobError), (not_json, TypeError)])
def test_errors_retrying_cannot_fix_fail_at_once(
    sent: list[dict[str, Any]], task: Any, error: type[Exception]
) -> None:
    run = start_job(task, key="once", name="once")
    with pytest.raises(error):
        deliver(task, sent[0])
    run.refresh_from_db()
    assert TRIES["once"] == 1
    assert (run.status, run.attempts) == (JobStatus.FAILED, 1)


@pytest.mark.django_db
def test_worker_lost_too_often_is_dead_lettered(sent: list[dict[str, Any]]) -> None:
    run = start_job(flaky, key="poison", name="poison", fail_times=0)
    # Its workers died mid-run on every try (status left running): 1 + max_retries 3 tries.
    JobRun.platform_runs.filter(pk=run.pk).update(status=JobStatus.RUNNING, attempts=4)
    assert deliver(flaky, sent[0]) is None
    assert "poison" not in TRIES  # the body never ran again
    run.refresh_from_db()
    assert (run.status, run.error_code) == (JobStatus.DEAD, "job.worker_lost")
    assert "4 times" in run.error_message


@pytest.mark.django_db
def test_worker_lost_with_tries_left_runs_again(sent: list[dict[str, Any]]) -> None:
    run = start_job(flaky, key="lost-once", name="lost-once", fail_times=0)
    JobRun.platform_runs.filter(pk=run.pk).update(status=JobStatus.RUNNING, attempts=1)
    assert deliver(flaky, sent[0]) == {"tries": 1}
    run.refresh_from_db()
    assert (run.status, run.attempts) == (JobStatus.SUCCEEDED, 2)


# ---- retry by hand -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_dead_run_can_be_sent_again(sent: list[dict[str, Any]]) -> None:
    run = start_job(always_down, key="again", name="again")
    with pytest.raises(JobError):
        deliver(always_down, sent[0])
    first_task_id = JobRun.platform_runs.get(pk=run.pk).celery_task_id
    retried = retry_run(run)
    assert retried.pk == run.pk  # same run, same idempotency key
    assert retried.status == JobStatus.QUEUED
    assert retried.error_code == "" and retried.finished_at is None
    assert retried.celery_task_id != first_task_id
    assert len(sent) == 2 and sent[1]["task_id"] == retried.celery_task_id
    with pytest.raises(JobError):
        deliver(always_down, sent[1])  # a fresh retry budget: 3 more tries
    assert TRIES["again"] == 6


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING, JobStatus.SUCCEEDED]
)
def test_only_failed_runs_can_be_retried(sent: list[dict[str, Any]], status: str) -> None:
    run = start_job(flaky, key="not-failed", name="not-failed", fail_times=0)
    JobRun.platform_runs.filter(pk=run.pk).update(status=status)
    with pytest.raises(CatalogueError) as refused:
        retry_run(run)
    assert refused.value.get_codes() == "job.not_retryable"
    assert refused.value.status_code == 409
    assert len(sent) == 1


@pytest.mark.django_db
def test_two_retries_at_once_send_one(sent: list[dict[str, Any]]) -> None:
    run = start_job(bad_input, key="double", name="double")
    with pytest.raises(JobError):
        deliver(bad_input, sent[0])
    stale = JobRun.platform_runs.get(pk=run.pk)
    retry_run(run)
    with pytest.raises(CatalogueError):
        retry_run(stale)  # the second click sees it queued already
    assert len(sent) == 2


# ---- a real worker -----------------------------------------------------------------------------


@pytest.fixture
def worker() -> Iterator[Any]:
    with start_worker(
        celery_app,
        queues=list(QUEUE_NAMES),
        perform_ping_check=False,
        shutdown_timeout=10,
        loglevel="WARNING",
    ) as running:
        yield running


@pytest.mark.django_db(transaction=True)
def test_worker_retries_with_backoff(worker: Any) -> None:
    org = Organisation.objects.create(name="Retry Ltd.")
    run = start_job(org_flaky, organisation=org, key="worker", name="worker")
    assert celery_app.AsyncResult(run.celery_task_id).get(timeout=20) == {"tries": 2}
    run.refresh_from_db()
    assert (run.status, run.attempts) == (JobStatus.SUCCEEDED, 2)
