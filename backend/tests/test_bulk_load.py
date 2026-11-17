"""V-03-T12 — load test: a 200-organisation job completes and every row has an outcome.

The job runs as the worker runs it (the captured A-08 message delivered to the task), over 200
organisations mixing changes, organisations already as asked (skipped: no change), one the
practice no longer serves (skipped: no access) and one whose change raises (failed) — and is
interrupted once part-way (a killed worker), then redelivered. Acceptance: **0 rows without an
outcome**, the counters add up to 200, every changed organisation is changed exactly once, and
the job stays inside its time budget.
"""

from __future__ import annotations

import time
from typing import Any
from unittest import mock

import pytest

from numo9.bulk import service
from numo9.bulk.actions import TagsAction
from numo9.bulk.models import RowOutcome
from numo9.tenancy.models import PracticeAssignment
from numo9.workspace.models import OrgTag
from numo9.workspace.tags import create_tag, tag_organisation
from tests.bulk_helpers import bulk_world
from tests.job_helpers import deliver

pytestmark = pytest.mark.django_db

COUNT = 200
BUDGET_SECONDS = 60.0


class WorkerKilled(BaseException):
    pass


def test_200_organisation_job_leaves_no_row_without_outcome(sent: list[dict[str, Any]]) -> None:
    world = bulk_world(COUNT)
    orgs = world["orgs"]
    tag = create_tag(world["practice"], "Year-end 2026")
    for org in orgs[:10]:
        tag_organisation(tag, org)  # already as asked
    PracticeAssignment.objects.filter(organisation=orgs[50]).update(active=False)
    job, preview = service.create_job(
        world["admin"],
        world["practice"],
        "tags",
        {"add": [str(tag.public_id)]},
        {"ids": [str(org.public_id) for org in orgs]},
    )
    assert preview["total"] == COUNT
    service.confirm(job, world["admin"])
    real = TagsAction.apply
    state = {"calls": 0, "kill": True}

    def apply(self: TagsAction, ctx: Any) -> Any:
        state["calls"] += 1
        if ctx.organisation == orgs[120]:
            raise RuntimeError("provider timeout")
        if state["kill"] and state["calls"] == 100:
            state["kill"] = False
            raise WorkerKilled
        return real(self, ctx)

    started = time.monotonic()
    with mock.patch.object(TagsAction, "apply", apply):
        with pytest.raises(WorkerKilled):
            deliver(service.run_bulk_job, sent[0])
        assert job.rows.filter(outcome=RowOutcome.PENDING).exists()
        service.execute(job)  # the redelivery
    elapsed = time.monotonic() - started

    job.refresh_from_db()
    counts = job.counts()
    assert job.rows.filter(outcome=RowOutcome.PENDING).count() == 0
    assert job.rows.filter(processed_at__isnull=True).count() == 0
    assert sum(counts.values()) == COUNT
    assert counts == {
        "pending": 0,
        "succeeded": COUNT - 10 - 1 - 1,
        "skipped": 11,
        "failed": 1,
        "cancelled": 0,
    }
    assert job.status == "completed" and job.finished_at is not None
    assert OrgTag.objects.filter(tag=tag).count() == COUNT - 2  # served ones, once each
    assert job.rows.get(organisation=orgs[50]).reason == "no_access"
    assert job.rows.get(organisation=orgs[120]).reason == "error"
    assert elapsed < BUDGET_SECONDS, f"200 organisations took {elapsed:.1f} s"
