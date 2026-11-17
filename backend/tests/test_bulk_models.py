"""V-03-T02 — ``BulkJob`` + ``BulkJobRow`` (action, params, status, outcome, message).

Acceptance: the migration applies; one row per organisation of a job; a final outcome always has
its time; counters per outcome.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.bulk.models import BulkJob, BulkJobRow, RowOutcome
from numo9.tenancy.models import Organisation
from tests.workspace_helpers import practice, user

pytestmark = pytest.mark.django_db


@pytest.fixture
def job() -> BulkJob:
    return BulkJob.objects.create(
        practice=practice("Abuodeh CPA"),
        created_by=user("sam@cpa.ca"),
        action="tags",
        params={"add": ["retail"]},
        selection={"ids": []},
    )


def test_rows_and_counts(job: BulkJob) -> None:
    orgs = [Organisation.objects.create(name=f"Org {i}") for i in range(3)]
    for position, org in enumerate(orgs):
        BulkJobRow.objects.create(job=job, organisation=org, position=position)
    BulkJobRow.objects.filter(position=0).update(
        outcome=RowOutcome.SUCCEEDED, processed_at=timezone.now()
    )
    BulkJobRow.objects.filter(position=1).update(
        outcome=RowOutcome.SKIPPED, reason="no_access", processed_at=timezone.now()
    )
    assert job.status == "preview"
    counts = job.counts()
    assert (counts["succeeded"], counts["skipped"], counts["pending"], counts["failed"]) == (
        1,
        1,
        1,
        0,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        BulkJobRow.objects.create(job=job, organisation=orgs[0], position=9)


def test_final_outcome_needs_its_time(job: BulkJob) -> None:
    org = Organisation.objects.create(name="Org")
    with pytest.raises(IntegrityError), transaction.atomic():
        BulkJobRow.objects.create(job=job, organisation=org, position=0, outcome="succeeded")


def test_action_and_status_are_checked(job: BulkJob) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        BulkJob.objects.filter(pk=job.pk).update(action="delete")
    with pytest.raises(IntegrityError), transaction.atomic():
        BulkJob.objects.filter(pk=job.pk).update(status="weird")
