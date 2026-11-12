"""Job base class (A-08-T03): idempotency key check, org context, JobRun lifecycle, logs.

Acceptance: the same key runs once — a second start with the key gets the existing run and sends
nothing, and a second delivery of a finished run does not run the body again.

Most tests run a delivery in-process with ``task.apply()`` (the path a worker takes, on the test
transaction); ``test_worker_runs_a_started_job`` runs one through a real worker thread.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Any
from unittest import mock

import psycopg
import pytest
from celery.contrib.testing.worker import start_worker
from django.db import connection, transaction

from numo9 import celery_app
from numo9.accounts.models import User
from numo9.i18n import errors
from numo9.jobs.models import JobRun, JobStatus
from numo9.jobs.queues import QUEUE_NAMES, REPORTS
from numo9.jobs.runtime import (
    _LOCK_NAMESPACE,
    JOB_RUN_ID,
    JobError,
    JobRunMismatch,
    JobRunRequired,
    JobTask,
    PlatformJobTask,
    current_job,
    idempotency_key,
    org_job,
    platform_job,
    report_progress,
    set_result_url,
    start_job,
)
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation
from tests.job_helpers import deliver
from tests.testapp.models import Widget

CALLS: list[dict[str, Any]] = []


@org_job(name="tests.jobs.make_widgets", queue=REPORTS, max_retries=0)  # retries: T04 tests
def make_widgets(*, org_id: str, labels: list[str], fail: str | None = None) -> dict[str, Any]:
    """Creates one Widget per label, reporting progress; optionally fails after the writes."""
    CALLS.append({"org": current_org(), "job": current_job()})
    for done, label in enumerate(labels, 1):
        Widget.objects.create(label=label)
        report_progress(done, len(labels), f"{label} made")
    set_result_url(f"/o/{org_id}/widgets")
    if fail == "job_error":
        raise JobError(errors.JOB_NOT_QUEUED)
    if fail == "crash":
        raise RuntimeError("disk full while writing 046 454 286")  # a SIN-shaped number
    if fail == "not_json":
        return {"widgets": {object()}}
    return {"made": len(labels)}


@org_job(name="tests.jobs.make_widgets_in_steps", atomic=False, max_retries=0)
def make_widgets_in_steps(*, org_id: str, labels: list[str]) -> None:
    for label in labels:
        Widget.objects.create(label=label)
    raise RuntimeError("stopped half-way")


@platform_job(name="tests.jobs.platform_tick")
def platform_tick(*, note: str = "") -> dict[str, Any]:
    CALLS.append({"org": current_org(), "job": current_job()})
    return {"note": note}


@pytest.fixture(autouse=True)
def _calls() -> Iterator[None]:
    CALLS.clear()
    yield
    CALLS.clear()


def _org(name: str = "Maple Leaf Supply Ltd.", locale: str = "en-ca") -> Organisation:
    return Organisation.objects.create(name=name, locale=locale)


def _user(locale: str = "en-ca") -> User:
    email = f"{uuid.uuid4().hex[:8]}@maple.ca"
    return User.objects.create_user(email=email, password="x" * 12, name="Dana", locale=locale)


# ---- starting a job ----------------------------------------------------------------------------


def test_job_decorators_use_the_job_bases() -> None:
    assert isinstance(make_widgets, JobTask)
    assert isinstance(platform_tick, PlatformJobTask)
    with pytest.raises(TypeError):
        org_job(base=PlatformJobTask)
    with pytest.raises(TypeError):
        platform_job(base=JobTask)


def test_idempotency_key_is_namespaced_by_task_and_organisation() -> None:
    org = Organisation(name="A Ltd.")
    assert idempotency_key("t.x", org, "k1") == f"t.x:{org.public_id}:k1"
    assert idempotency_key("t.x", None, "k1") == "t.x:platform:k1"
    random_1, random_2 = idempotency_key("t.x", None, None), idempotency_key("t.x", None, None)
    assert random_1 != random_2
    long = idempotency_key("t.x", org, "k" * 400)
    assert len(long) <= 255 and ":sha256:" in long
    assert long == idempotency_key("t.x", org, "k" * 400)


@pytest.mark.django_db
def test_start_job_creates_a_queued_run_and_sends_it(sent: list[dict[str, Any]]) -> None:
    org, user = _org(), _user()
    run = start_job(make_widgets, organisation=org, key="batch-1", created_by=user, labels=["a"])
    assert run.started_now  # type: ignore[attr-defined]
    run.refresh_from_db()
    assert (run.status, run.organisation, run.created_by, run.queue) == (
        JobStatus.QUEUED,
        org,
        user,
        "reports",
    )
    assert run.task_name == "tests.jobs.make_widgets"
    assert run.payload == {"labels": ["a"], "org_id": str(org.public_id)}
    assert run.idempotency_key == f"tests.jobs.make_widgets:{org.public_id}:batch-1"
    assert run.max_retries == 0  # the task's setting
    assert len(sent) == 1
    assert sent[0]["kwargs"] == {**run.payload, JOB_RUN_ID: str(run.public_id)}
    assert (sent[0]["queue"], sent[0]["task_id"]) == ("reports", run.celery_task_id)


@pytest.mark.django_db
def test_same_key_runs_once(sent: list[dict[str, Any]]) -> None:
    org = _org()
    first = start_job(make_widgets, organisation=org, key="import-7", labels=["a", "b"])
    again = start_job(make_widgets, organisation=org, key="import-7", labels=["a", "b"])
    assert again.pk == first.pk and not again.started_now  # type: ignore[attr-defined]
    assert len(sent) == 1  # nothing sent for the duplicate
    assert deliver(make_widgets, sent[0]) == {"made": 2}
    # The message is delivered a second time (redelivery after a lost acknowledgement):
    assert deliver(make_widgets, sent[0]) == {"made": 2}  # the stored result
    assert len(CALLS) == 1  # the body ran once
    with org_context_of(org):
        assert Widget.objects.count() == 2
    assert JobRun.platform_runs.get(pk=first.pk).attempts == 1


@pytest.mark.django_db
def test_other_keys_and_organisations_run_separately(sent: list[dict[str, Any]]) -> None:
    org_a, org_b = _org("A Ltd."), _org("B Ltd.")
    start_job(make_widgets, organisation=org_a, key="k", labels=[])
    start_job(make_widgets, organisation=org_b, key="k", labels=[])  # same key, other org
    start_job(make_widgets, organisation=org_a, key="k2", labels=[])
    start_job(make_widgets, organisation=org_a, labels=[])  # no key: always a new run
    start_job(make_widgets, organisation=org_a, labels=[])
    assert len(sent) == 5
    assert JobRun.platform_runs.count() == 5


@pytest.mark.django_db
def test_a_run_created_by_another_process_is_returned(sent: list[dict[str, Any]]) -> None:
    org = _org()
    key = idempotency_key(make_widgets.name, org, "race")
    other = JobRun.platform_runs.create(
        organisation=org, task_name=make_widgets.name, idempotency_key=key
    )
    run = start_job(make_widgets, organisation=org, key="race", labels=[])
    assert run.pk == other.pk and not run.started_now  # type: ignore[attr-defined]
    assert sent == []


@pytest.mark.django_db
def test_message_is_sent_once_the_transaction_commits(
    sent_on_commit: list[dict[str, Any]], django_capture_on_commit_callbacks: Any
) -> None:
    sent = sent_on_commit
    org = _org()
    with django_capture_on_commit_callbacks(execute=True) as callbacks, transaction.atomic():
        start_job(make_widgets, organisation=org, labels=[])
        assert sent == []
    assert len(callbacks) == 1 and len(sent) == 1


@pytest.mark.django_db
def test_broker_failure_marks_the_run_failed() -> None:
    org = _org()
    refuse = mock.patch("celery.app.task.Task.apply_async", side_effect=ConnectionError("down"))
    now = mock.patch.object(transaction, "on_commit", lambda func, using=None, robust=False: func())
    with refuse, now, pytest.raises(ConnectionError):
        start_job(make_widgets, organisation=org, key="k", labels=[])
    run = JobRun.platform_runs.get()
    assert (run.status, run.error_code) == (JobStatus.FAILED, "job.not_queued")
    assert "couldn't be queued" in run.error_message


@pytest.mark.django_db
def test_start_job_refuses_wrong_calls(sent: list[dict[str, Any]]) -> None:
    org = _org()
    with pytest.raises(ValueError, match="organisation job"):
        start_job(make_widgets, labels=[])
    with pytest.raises(ValueError, match="platform job"):
        start_job(platform_tick, organisation=org)
    with pytest.raises(ValueError, match="org_id"):
        start_job(make_widgets, organisation=org, org_id=str(org.public_id), labels=[])
    with pytest.raises(ValueError, match=JOB_RUN_ID):
        start_job(platform_tick, job_run_id="x")
    with pytest.raises(TypeError, match="JSON"):
        start_job(make_widgets, organisation=org, labels=[object()])
    from numo9.jobs.tasks import ping

    with pytest.raises(TypeError, match="not a job task"):
        start_job(ping)
    assert sent == [] and JobRun.platform_runs.count() == 0


def test_delay_is_refused() -> None:
    with pytest.raises(JobRunRequired, match="start_job"):
        make_widgets.delay(org_id=str(uuid.uuid4()), labels=[])
    with pytest.raises(JobRunRequired):
        platform_tick.apply_async(kwargs={"note": "x"})


# ---- running a job -----------------------------------------------------------------------------


def org_context_of(org: Organisation) -> Any:
    from numo9.tenancy.context import org_context

    return org_context(org)


@pytest.mark.django_db
def test_lifecycle_of_a_successful_run(
    sent: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    org = _org()
    with caplog.at_level(logging.INFO, logger="numo9.jobs"):
        run = start_job(make_widgets, organisation=org, key="k", labels=["a", "b", "c"])
        assert deliver(make_widgets, sent[0]) == {"made": 3}
    run.refresh_from_db()
    assert run.status == JobStatus.SUCCEEDED
    assert run.attempts == 1
    assert run.started_at is not None and run.finished_at is not None
    assert run.started_at <= run.finished_at
    assert (run.progress_done, run.progress_total, run.progress_message) == (3, 3, "c made")
    assert run.progress_percent == 100
    assert run.result == {"made": 3}
    assert run.result_url == f"/o/{org.public_id}/widgets"
    assert run.worker.endswith(f":{__import__('os').getpid()}")
    assert run.error_code == ""
    # The body ran in the organisation's context, with the run as current_job().
    assert CALLS[0]["org"] == org and CALLS[0]["job"].pk == run.pk
    assert current_job() is None and current_org() is None  # restored afterwards
    events = [r.getMessage().split()[0] for r in caplog.records if r.name == "numo9.jobs"]
    assert events == ["job.queued", "job.started", "job.succeeded"]
    done = next(r for r in caplog.records if r.getMessage().startswith("job.succeeded"))
    assert done.job["id"] == str(run.public_id)  # type: ignore[attr-defined]
    assert done.job["org_id"] == str(org.public_id)  # type: ignore[attr-defined]
    assert done.job["duration_ms"] >= 0  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_body_logs_carry_the_job_context(sent: list[dict[str, Any]]) -> None:
    import structlog

    seen: list[dict[str, Any]] = []

    @platform_job(name="tests.jobs.log_context")
    def log_context() -> None:
        seen.append(structlog.contextvars.get_contextvars())

    start_job(log_context, key="ctx")
    run = JobRun.platform_runs.get(task_name="tests.jobs.log_context")
    deliver(log_context, sent[0])
    assert seen[0] == {"job_id": str(run.public_id), "job_task": run.task_name, "org_id": None}
    assert structlog.contextvars.get_contextvars() == {}


@pytest.mark.django_db
def test_atomic_job_that_fails_leaves_nothing_behind(sent: list[dict[str, Any]]) -> None:
    org, user = _org(), _user(locale="fr-ca")
    run = start_job(
        make_widgets, organisation=org, created_by=user, labels=["a", "b"], fail="crash"
    )
    with pytest.raises(RuntimeError):
        deliver(make_widgets, sent[0])
    run.refresh_from_db()
    with org_context_of(org):
        assert Widget.objects.count() == 0  # rolled back with the job
    # An unexpected error with no retries left: dead (A-08-T04 retries it otherwise).
    assert (run.status, run.error_code) == (JobStatus.DEAD, "job.failed")
    assert run.error_message.startswith("Une erreur")  # in the starter's language
    assert run.error_detail.startswith("builtins.RuntimeError: disk full")
    assert "046 454 286" not in run.error_detail  # scrubbed (S-03-T06)
    assert run.finished_at is not None


@pytest.mark.django_db
def test_job_error_message_is_stored(sent: list[dict[str, Any]]) -> None:
    org = _org()
    run = start_job(make_widgets, organisation=org, labels=[], fail="job_error")
    with pytest.raises(JobError):
        deliver(make_widgets, sent[0])
    run.refresh_from_db()
    assert (run.status, run.error_code) == (JobStatus.FAILED, "job.not_queued")
    assert run.error_message == str(errors.JOB_NOT_QUEUED.message)


@pytest.mark.django_db
def test_result_must_be_json(sent: list[dict[str, Any]]) -> None:
    run = start_job(make_widgets, organisation=_org(), labels=["a"], fail="not_json")
    with pytest.raises(TypeError, match="JSON"):
        deliver(make_widgets, sent[0])
    run.refresh_from_db()
    assert run.status == JobStatus.FAILED and run.result is None


@pytest.mark.django_db
def test_non_atomic_job_keeps_its_steps(sent: list[dict[str, Any]]) -> None:
    org = _org()
    run = start_job(make_widgets_in_steps, organisation=org, labels=["a", "b"])
    with pytest.raises(RuntimeError):
        deliver(make_widgets_in_steps, sent[0])
    with org_context_of(org):
        assert Widget.objects.count() == 2
    run.refresh_from_db()
    assert run.status == JobStatus.DEAD


@pytest.mark.django_db
def test_platform_job_runs_without_tenant_context(sent: list[dict[str, Any]]) -> None:
    run = start_job(platform_tick, key="tick", note="hello")
    assert run.organisation is None
    assert run.idempotency_key == "tests.jobs.platform_tick:platform:tick"
    assert deliver(platform_tick, sent[0]) == {"note": "hello"}
    assert CALLS[0]["org"] is None
    run.refresh_from_db()
    assert run.status == JobStatus.SUCCEEDED


# ---- messages that are refused -----------------------------------------------------------------


@pytest.mark.django_db
def test_message_without_run_id_is_refused() -> None:
    org = _org()
    with pytest.raises(JobRunRequired):
        make_widgets.apply(kwargs={"org_id": str(org.public_id), "labels": []}).get()
    assert CALLS == []


@pytest.mark.django_db
def test_message_for_another_organisation_or_task_is_refused(
    sent: list[dict[str, Any]],
) -> None:
    org, other = _org("Mine Ltd."), _org("Other Ltd.")
    start_job(make_widgets, organisation=org, labels=["a"])
    forged = {**sent[0]["kwargs"], "org_id": str(other.public_id)}
    with pytest.raises(JobRunMismatch):
        make_widgets.apply(kwargs=forged).get()
    with pytest.raises(JobRunMismatch):
        make_widgets_in_steps.apply(kwargs=sent[0]["kwargs"]).get()
    with pytest.raises(JobRunMismatch):
        make_widgets.apply(kwargs={**sent[0]["kwargs"], JOB_RUN_ID: str(uuid.uuid4())}).get()
    with pytest.raises(JobRunMismatch):
        make_widgets.apply(kwargs={**sent[0]["kwargs"], JOB_RUN_ID: "nope"}).get()
    assert CALLS == []
    with pytest.raises(JobRunMismatch):
        platform_tick.apply(kwargs={"org_id": str(org.public_id), JOB_RUN_ID: "x"}).get()


@pytest.mark.django_db
def test_report_progress_and_result_url_need_a_job() -> None:
    with pytest.raises(RuntimeError):
        report_progress(1, 2)
    with pytest.raises(RuntimeError):
        set_result_url("/x")


@pytest.mark.django_db
def test_progress_is_kept_within_its_total(sent: list[dict[str, Any]]) -> None:
    seen: list[tuple[int, int | None]] = []

    @platform_job(name="tests.jobs.progress_bounds", atomic=False)
    def progress_bounds() -> None:
        report_progress(9, 3)
        run = current_job()
        assert run is not None
        stored = JobRun.platform_runs.get(pk=run.pk)
        seen.append((stored.progress_done, stored.progress_total))
        report_progress(-4)
        stored.refresh_from_db()
        seen.append((stored.progress_done, stored.progress_total))

    start_job(progress_bounds)
    deliver(progress_bounds, sent[0])
    assert seen == [(3, 3), (0, None)]


# ---- a second worker holding the run -----------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="advisory locks are PostgreSQL")
def test_delivery_while_another_worker_runs_it_is_skipped(
    sent: list[dict[str, Any]], caplog: pytest.LogCaptureFixture
) -> None:
    org = _org()
    run = start_job(make_widgets, organisation=org, labels=["a"])
    params = connection.get_connection_params()
    params.pop("cursor_factory", None)
    with psycopg.connect(**params, autocommit=True) as other_worker:
        other_worker.execute("SELECT pg_advisory_lock(%s)", [_LOCK_NAMESPACE | run.pk])
        with caplog.at_level(logging.WARNING, logger="numo9.jobs"):
            assert deliver(make_widgets, sent[0]) is None
    assert CALLS == []
    run.refresh_from_db()
    assert run.status == JobStatus.QUEUED and run.attempts == 0
    assert any(r.getMessage().startswith("job.skipped_locked") for r in caplog.records)
    # The other worker is gone (its connection closed, the lock with it): the run can run.
    assert deliver(make_widgets, sent[0]) == {"made": 1}


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
def test_worker_runs_a_started_job(worker: Any) -> None:
    org = _org()
    run = start_job(make_widgets, organisation=org, key="worker", labels=["a", "b"])
    result = celery_app.AsyncResult(run.celery_task_id)
    assert result.get(timeout=15) == {"made": 2}
    run.refresh_from_db()
    assert run.status == JobStatus.SUCCEEDED and run.attempts == 1
    assert run.worker and not run.worker.startswith("local:")
    again = start_job(make_widgets, organisation=org, key="worker", labels=["a", "b"])
    assert again.pk == run.pk
    with org_context_of(org):
        assert Widget.objects.count() == 2
