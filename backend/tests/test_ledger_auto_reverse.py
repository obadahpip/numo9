"""C-03-T09 — automatic reversal: ``auto_reverse_on`` on a journal; the hourly beat job posts the
reversal on that date, idempotently.

Acceptance: an accrual of 30 June reversing on 1 July is reversed on 1 July (organisation's date),
not before; running the job again (a worker restart) posts nothing more — exactly one reversal;
the reversal is dated 1 July, mirrors the lines and is a system posting; a reversal date on or
before the journal, or in a locked period, is refused when the journal is saved or posted.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.conf import settings
from freezegun import freeze_time

from numo9.ledger.models import JournalEntry, JournalStatus
from numo9.ledger.policy import JournalRuleError
from numo9.ledger.reversals import JOB, post_due_reversals
from numo9.ledger.services import post_journal, save_draft
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db
JUNE_30, JULY_1 = dt.date(2026, 6, 30), dt.date(2026, 7, 1)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")


def accrual(org: Organisation) -> JournalEntry:
    with org_context(org):
        accounts = chart(org)
        return post_journal(
            pay(accounts["rent"], accounts["ar"], "1130.00", date=JUNE_30, auto_reverse_on=JULY_1)
        )


def test_reversed_on_its_date_exactly_once(org: Organisation) -> None:
    entry = accrual(org)
    assert entry.auto_reverse_on == JULY_1
    with freeze_time("2026-07-01 03:00:00"):  # 23:00 on 30 June in Toronto: not yet
        assert post_due_reversals() == 0
    with freeze_time("2026-07-01 05:00:00"):  # 01:00 on 1 July in Toronto
        assert post_due_reversals() == 1
        assert post_due_reversals() == 0  # the job runs again (worker restart)
    with org_context(org):
        entry.refresh_from_db()
        assert entry.status == JournalStatus.REVERSED
        (reversal,) = JournalEntry.objects.filter(reversal_of=entry)
        assert (reversal.date, reversal.posted_by) == (JULY_1, None)
        assert reversal.narration.startswith("Automatic reversal of")
        assert reversal.auto_reverse_on is None
        lines = [(line.debit, line.credit) for line in reversal.lines.order_by("line_no")]
        original = [(line.credit, line.debit) for line in entry.lines.order_by("line_no")]
        assert lines == original


def test_job_is_scheduled_hourly() -> None:
    assert settings.CELERY_BEAT_SCHEDULE[JOB]["task"] == JOB


def test_reversal_date_must_follow_the_journal(org: Organisation) -> None:
    with org_context(org):
        accounts = chart(org)
        for when in (JUNE_30, dt.date(2026, 6, 1)):
            for write in (save_draft, post_journal):
                with pytest.raises(JournalRuleError) as raised:
                    write(
                        pay(
                            accounts["rent"],
                            accounts["ar"],
                            "10.00",
                            date=JUNE_30,
                            auto_reverse_on=when,
                        )
                    )
                assert raised.value.error_list[0].code == "ledger.journal.auto_reverse_before"


def test_locked_reversal_date_is_refused_at_save(org: Organisation) -> None:
    with org_context(org):
        accounts = chart(org)
        LockDate(organisation=org, module="gl", level="everyone", date=JULY_1).save()
        spec = pay(
            accounts["rent"],
            accounts["ar"],
            "10.00",
            date=dt.date(2026, 7, 15),
            auto_reverse_on=dt.date(2026, 7, 16),
        )
        assert save_draft(spec).auto_reverse_on == dt.date(2026, 7, 16)
        locked = pay(
            accounts["rent"],
            accounts["ar"],
            "10.00",
            date=dt.date(2026, 6, 15),
            auto_reverse_on=JULY_1,
        )
        with pytest.raises(JournalRuleError) as raised:
            save_draft(locked)
    assert raised.value.error_list[0].code == "ledger.journal.auto_reverse_locked"
    assert "2026-07-01" in raised.value.messages[0]
