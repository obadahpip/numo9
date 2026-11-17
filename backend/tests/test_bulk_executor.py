"""V-03-T05 — executor: per-row transaction, permission check per organisation, resumable.

Acceptance: a worker killed mid-job → the resumed job completes the rest, each organisation
changed exactly once; access is re-checked per organisation when the row runs; an error in one
organisation fails that row only; cancelling keeps done rows and cancels the rest.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from numo9.bulk import service
from numo9.bulk.actions import TagsAction
from numo9.bulk.models import BulkJob, RowOutcome
from numo9.tenancy.models import PracticeAssignment
from numo9.workspace.models import OrgTag
from numo9.workspace.tags import create_tag
from tests.bulk_helpers import bulk_world
from tests.job_helpers import deliver

pytestmark = pytest.mark.django_db


class WorkerKilled(BaseException):
    """What a SIGKILL looks like from inside the body: nothing after it runs."""


@pytest.fixture
def world() -> dict[str, Any]:
    world = bulk_world(5)
    world["tag"] = create_tag(world["practice"], "Retail")
    return world


def make_job(world: dict[str, Any]) -> BulkJob:
    job, _preview = service.create_job(
        world["admin"],
        world["practice"],
        "tags",
        {"add": [str(world["tag"].public_id)]},
        {"ids": [str(org.public_id) for org in world["orgs"]]},
    )
    return job


def outcomes(job: BulkJob) -> list[str]:
    return list(job.rows.order_by("position").values_list("outcome", flat=True))


def test_confirm_runs_one_background_job(world: dict[str, Any], sent: list[dict[str, Any]]) -> None:
    job = service.confirm(make_job(world), world["admin"])
    assert job.status == "queued" and job.rows.count() == 5
    assert [m["task"] for m in sent] == [service.RUN_JOB]
    again = service.confirm  # a second confirm is refused, no second job
    with pytest.raises(Exception, match="bulk.not_preview|already"):
        again(job, world["admin"])
    assert len(sent) == 1
    assert deliver(service.run_bulk_job, sent[0])["succeeded"] == 5
    job.refresh_from_db()
    assert job.status == "completed" and job.finished_at is not None
    assert OrgTag.objects.count() == 5


def test_killed_between_rows_resumes_the_rest_once(world: dict[str, Any], sent: Any) -> None:
    job = service.confirm(make_job(world), world["admin"])
    calls = {"n": 0}

    def progress(done: int, total: int | None = None, message: str = "") -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise WorkerKilled

    with mock.patch.object(service, "report_progress", progress), pytest.raises(WorkerKilled):
        service.execute(job)
    assert outcomes(job) == ["succeeded", "succeeded", "pending", "pending", "pending"]
    assert OrgTag.objects.count() == 2
    service.execute(job)  # the redelivery / retry
    assert outcomes(job) == ["succeeded"] * 5
    assert OrgTag.objects.count() == 5  # each organisation tagged once


def test_killed_inside_a_row_leaves_it_untouched(world: dict[str, Any], sent: Any) -> None:
    job = service.confirm(make_job(world), world["admin"])
    real = TagsAction.apply
    calls = {"n": 0}

    def apply(self: TagsAction, ctx: Any) -> Any:
        calls["n"] += 1
        result = real(self, ctx)
        if calls["n"] == 3:
            raise WorkerKilled  # after the change, before the outcome: all rolled back
        return result

    with mock.patch.object(TagsAction, "apply", apply), pytest.raises(WorkerKilled):
        service.execute(job)
    assert outcomes(job)[:3] == ["succeeded", "succeeded", "pending"]
    assert OrgTag.objects.count() == 2
    service.execute(job)
    assert outcomes(job) == ["succeeded"] * 5 and OrgTag.objects.count() == 5


def test_access_is_checked_per_row_when_it_runs(world: dict[str, Any], sent: Any) -> None:
    job = service.confirm(make_job(world), world["admin"])
    PracticeAssignment.objects.filter(organisation=world["orgs"][1]).update(active=False)
    service.execute(job)
    rows = list(job.rows.order_by("position"))
    assert rows[1].outcome == RowOutcome.SKIPPED and rows[1].reason == "no_access"
    assert rows[1].message == "You don't have access to this organisation."
    assert [r.outcome for r in rows if r.position != 1] == ["succeeded"] * 4


def test_an_error_fails_one_row_and_the_job_goes_on(world: dict[str, Any], sent: Any) -> None:
    job = service.confirm(make_job(world), world["admin"])
    real = TagsAction.apply

    def apply(self: TagsAction, ctx: Any) -> Any:
        if ctx.organisation == world["orgs"][2]:
            raise RuntimeError("boom")
        return real(self, ctx)

    with mock.patch.object(TagsAction, "apply", apply):
        counts = service.execute(job)
    assert counts["failed"] == 1 and counts["succeeded"] == 4 and counts["pending"] == 0
    failed = job.rows.get(outcome="failed")
    assert failed.reason == "error" and "Nothing was changed" in failed.message


def test_cancel_keeps_done_rows_and_cancels_the_rest(world: dict[str, Any], sent: Any) -> None:
    job = service.confirm(make_job(world), world["admin"])
    calls = {"n": 0}

    def progress(done: int, total: int | None = None, message: str = "") -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            service.cancel(job)

    with mock.patch.object(service, "report_progress", progress):
        counts = service.execute(job)
    assert outcomes(job) == ["succeeded", "succeeded", "cancelled", "cancelled", "cancelled"]
    assert counts["pending"] == 0
    job.refresh_from_db()
    assert job.status == "cancelled"
    assert job.rows.filter(outcome="cancelled").first().message.startswith("The bulk action")
