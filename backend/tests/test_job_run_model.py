"""JobRun model (A-08-T02).

Acceptance: a duplicate idempotency key is rejected — by the database, so two processes racing to
start the same job cannot both succeed.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.jobs.models import ACTIVE, FINISHED, RETENTION, RETRYABLE, JobRun, JobStatus
from numo9.tenancy.context import TenantContextMissing, org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def _org(name: str = "Maple Leaf Supply Ltd.") -> Organisation:
    return Organisation.objects.create(name=name)


def _run(org: Organisation | None, key: str, **fields: object) -> JobRun:
    run: JobRun = JobRun.platform_runs.create(
        organisation=org, task_name="tests.job", idempotency_key=key, **fields
    )
    return run


# ---- idempotency key ---------------------------------------------------------------------------


def test_duplicate_idempotency_key_is_rejected() -> None:
    org = _org()
    _run(org, "tests.job:org:import-42")
    with pytest.raises(IntegrityError), transaction.atomic():
        _run(org, "tests.job:org:import-42")
    assert JobRun.platform_runs.filter(idempotency_key="tests.job:org:import-42").count() == 1


def test_key_is_unique_across_organisations_and_platform_jobs() -> None:
    _run(_org("A Ltd."), "same-key")
    with pytest.raises(IntegrityError), transaction.atomic():
        _run(_org("B Ltd."), "same-key")
    with pytest.raises(IntegrityError), transaction.atomic():
        _run(None, "same-key")


def test_empty_idempotency_key_is_rejected() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _run(None, "")


# ---- integrity ---------------------------------------------------------------------------------


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _run(None, "k-status", status="exploded")


def test_progress_cannot_exceed_its_total() -> None:
    _run(None, "k-ok", progress_done=5, progress_total=5)
    _run(None, "k-unknown-total", progress_done=7)  # total not known yet
    with pytest.raises(IntegrityError), transaction.atomic():
        _run(None, "k-over", progress_done=6, progress_total=5)


def test_defaults() -> None:
    run = _run(None, "k-defaults")
    assert run.status == JobStatus.QUEUED
    assert (run.attempts, run.max_retries, run.progress_done, run.progress_total) == (0, 5, 0, None)
    assert run.payload == {}
    assert run.result is None
    assert run.public_id is not None
    assert run.started_at is None and run.finished_at is None


# ---- tenancy -----------------------------------------------------------------------------------


def test_platform_jobs_have_no_organisation() -> None:
    run = _run(None, "k-platform")
    assert run.is_platform
    assert not _run(_org(), "k-org").is_platform


def test_objects_is_organisation_scoped() -> None:
    mine, theirs = _org("Mine Ltd."), _org("Theirs Ltd.")
    own = _run(mine, "k-mine")
    _run(theirs, "k-theirs")
    _run(None, "k-platform")
    with pytest.raises(TenantContextMissing):
        list(JobRun.objects.all())
    with org_context(mine):
        assert list(JobRun.objects.all()) == [own]  # never another's, never platform jobs
    assert JobRun.platform_runs.count() == 3


# ---- states and progress -----------------------------------------------------------------------


def test_state_groups_cover_every_status_once() -> None:
    assert set(JobStatus.values) == ACTIVE | FINISHED
    assert not ACTIVE & FINISHED
    assert RETRYABLE <= FINISHED
    assert JobStatus.SUCCEEDED not in RETRYABLE


@pytest.mark.parametrize(
    ("status", "done", "total", "percent"),
    [
        (JobStatus.RUNNING, 0, None, None),
        (JobStatus.RUNNING, 3, 0, None),
        (JobStatus.RUNNING, 1, 3, 33),
        (JobStatus.RUNNING, 3, 3, 100),
        (JobStatus.SUCCEEDED, 0, None, 100),
    ],
)
def test_progress_percent(status: str, done: int, total: int | None, percent: int | None) -> None:
    run = JobRun(status=status, progress_done=done, progress_total=total)
    assert run.progress_percent == percent


def test_retention_is_30_days() -> None:
    assert RETENTION.days == 30
