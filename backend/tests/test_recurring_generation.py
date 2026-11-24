"""C-04-T06 — the recurring-journal tick: one journal per occurrence, idempotent.

Acceptance: two workers (threads, each its own connection) and a restart create exactly one
journal per period (the unique (template, occurrence date) run row); a locked date is skipped with
the reason recorded (a run row and an audit event) — never posted on another date; drafts or
posted journals per the template's mode; above the approval threshold a "post" occurrence waits
for approval; paused templates generate nothing; next_run moves past today; the hourly job runs
each organisation on its own date.
"""

from __future__ import annotations

import datetime as dt
import threading
from decimal import Decimal
from typing import Any

import pytest
from django.conf import settings as django_settings
from django.db import connection
from freezegun import freeze_time

from numo9.audit.models import AuditEvent
from numo9.ledger.models import (
    JournalEntry,
    JournalStatus,
    RecurringJournalRun,
    RecurringJournalTemplate,
)
from numo9.ledger.recurring import JOB, SOURCE_TYPE, generate_all, generate_due
from numo9.orgsettings.models import LockDate
from numo9.orgsettings.service import get_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, people

D = dt.date


@pytest.fixture
def org(db: Any) -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")


def rent(org: Organisation, mode: str = "post", **fields: Any) -> RecurringJournalTemplate:
    with org_context(org):
        accounts = chart(org)
        item = RecurringJournalTemplate(
            organisation=org,
            name="Warehouse rent",
            narration="Kingsway warehouse rent",
            rrule="FREQ=MONTHLY",
            start_date=D(2026, 1, 31),
            mode=mode,
            lines=[
                {"account": str(accounts["rent"].public_id), "debit": "2400.00"},
                {"account": str(accounts["ar"].public_id), "credit": "2400.00"},
            ],
            **fields,
        )
        item.full_clean()
        item.save()
        return item


def journals(org: Organisation) -> list[JournalEntry]:
    with org_context(org):
        return list(JournalEntry.objects.filter(source_type=SOURCE_TYPE).order_by("date"))


@pytest.mark.django_db
def test_one_journal_per_occurrence_and_a_restart_adds_nothing(org: Organisation) -> None:
    template = rent(org)
    assert template.next_run == D(2026, 1, 31)
    runs = generate_due(org, D(2026, 3, 31))
    assert [r.occurrence_date for r in runs] == [D(2026, 1, 31), D(2026, 2, 28), D(2026, 3, 31)]
    posted = journals(org)
    assert [(j.date, j.status) for j in posted] == [
        (D(2026, 1, 31), JournalStatus.POSTED),
        (D(2026, 2, 28), JournalStatus.POSTED),
        (D(2026, 3, 31), JournalStatus.POSTED),
    ]
    assert {j.narration for j in posted} == {"Kingsway warehouse rent"}
    assert {j.source_id for j in posted} == {str(template.public_id)}
    assert generate_due(org, D(2026, 3, 31)) == []  # the job again: nothing more
    with org_context(org):
        template.refresh_from_db()
        assert template.next_run == D(2026, 4, 30)
        assert {r.template_version for r in RecurringJournalRun.objects.all()} == {1}
    assert len(journals(org)) == 3


@pytest.mark.django_db
def test_draft_mode_paused_and_end_date(org: Organisation) -> None:
    template = rent(org, mode="draft", end_date=D(2026, 2, 28))
    with org_context(org):
        RecurringJournalTemplate.objects.filter(pk=template.pk).update(paused=True)
    assert generate_due(org, D(2026, 6, 30)) == []
    with org_context(org):
        RecurringJournalTemplate.objects.filter(pk=template.pk).update(paused=False)
    runs = generate_due(org, D(2026, 6, 30))
    assert [r.occurrence_date for r in runs] == [D(2026, 1, 31), D(2026, 2, 28)]
    assert {j.status for j in journals(org)} == {JournalStatus.DRAFT}
    with org_context(org):
        template.refresh_from_db()
        assert template.next_run is None  # the schedule is over


@pytest.mark.django_db
def test_locked_period_is_skipped_with_the_reason(org: Organisation) -> None:
    template = rent(org)
    with org_context(org):
        LockDate(organisation=org, module="gl", level="everyone", date=D(2026, 2, 28)).save()
    runs = generate_due(org, D(2026, 3, 31))
    assert [(r.occurrence_date, r.status) for r in runs] == [
        (D(2026, 1, 31), "skipped"),
        (D(2026, 2, 28), "skipped"),
        (D(2026, 3, 31), "created"),
    ]
    assert runs[0].code == "lock.violation" and "2026-02-28" in runs[0].message
    assert [j.date for j in journals(org)] == [D(2026, 3, 31)]  # never moved to another date
    with org_context(org):
        skipped = AuditEvent.objects.filter(
            action="ledger.recurringjournaltemplate.skipped", object_id=str(template.public_id)
        )
        assert skipped.count() == 2
        assert skipped.first().meta["job"] == JOB  # type: ignore[union-attr]
    assert generate_due(org, D(2026, 3, 31)) == []  # a skipped date isn't retried either


@pytest.mark.django_db
def test_above_the_threshold_the_occurrence_waits_for_approval(org: Organisation) -> None:
    owner = people(org)["owner"]
    with org_context(org):
        settings = get_settings(org)
        settings.journal_approval_threshold = Decimal("1000.00")
        settings.save()
    template = rent(org)
    with org_context(org):
        RecurringJournalTemplate.objects.filter(pk=template.pk).update(created_by=owner)
    (run,) = generate_due(org, D(2026, 1, 31))
    assert run.code == "ledger.recurring.awaiting_approval"
    (entry,) = journals(org)
    assert entry.status == JournalStatus.AWAITING_APPROVAL


@pytest.mark.django_db
def test_the_hourly_job_uses_each_organisations_date(org: Organisation) -> None:
    rent(org)
    assert django_settings.CELERY_BEAT_SCHEDULE[JOB]["task"] == JOB
    with freeze_time("2026-02-01 03:00:00"):  # 22:00 on 31 January in Toronto
        assert generate_all() == 1
    with freeze_time("2026-02-28 04:00:00"):  # 23:00 on 27 February in Toronto: not yet
        assert generate_all() == 0
    with freeze_time("2026-02-28 06:00:00"):
        assert generate_all() == 1


@pytest.mark.django_db(transaction=True)
def test_two_workers_create_exactly_one_journal_per_period() -> None:
    org = Organisation.objects.create(name="Race Ltd.", time_zone="America/Toronto")
    rent(org)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            generate_due(org, D(2026, 6, 30))
        except BaseException as error:  # noqa: BLE001 — reported below
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    dates = [j.date for j in journals(org)]
    assert dates == [
        D(2026, 1, 31),
        D(2026, 2, 28),
        D(2026, 3, 31),
        D(2026, 4, 30),
        D(2026, 5, 31),
        D(2026, 6, 30),
    ]
    with org_context(org):
        assert RecurringJournalRun.objects.count() == 6
