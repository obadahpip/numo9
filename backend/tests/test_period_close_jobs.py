"""C-06-T06 — recurring and automatic jobs respect closed periods: a recurring tick dated in a
closed period records a skipped run (the exception, with the closed lock's reason) and posts no
journal; an automatic reversal due in a closed period isn't posted and is audited once as an
exception; both show on the period's checklist."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.ledger.models import JournalEntry, RecurringJournalRun, RecurringJournalTemplate
from numo9.ledger.period_close import checklist, close, close_year
from numo9.ledger.recurring import generate_due
from numo9.ledger.reversals import post_due_reversals
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from tests.period_close_helpers import close_books

pytestmark = pytest.mark.django_db
day = dt.date


@pytest.fixture
def books() -> dict[str, Any]:
    return close_books()


def test_recurring_tick_into_a_closed_period_is_an_exception(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        template = RecurringJournalTemplate(
            organisation=org,
            name="Rent",
            narration="Rent",
            rrule="FREQ=MONTHLY",
            start_date=day(2026, 6, 30),
            mode="post",
            lines=[
                {"account": str(books["expense"].public_id), "debit": "100.00"},
                {"account": str(books["revenue"].public_id), "credit": "100.00"},
            ],
            created_by=books["owner"],
        )
        template.full_clean()
        template.save()
    close(org, "gl", day(2026, 6, 30), books["owner"])
    with org_context(org):
        before = JournalEntry.objects.count()
        runs = generate_due(org, day(2026, 7, 2))
        run = RecurringJournalRun.objects.get(template=template, occurrence_date=day(2026, 6, 30))
        assert JournalEntry.objects.count() == before
        items = {item["key"]: item for item in checklist(org, day(2026, 6, 30))}
    assert runs and run.status == "skipped" and run.code == "lock.violation"
    assert items["exceptions"]["detail"]["recurring_skipped"] == 1


def test_auto_reversal_into_a_closed_year_is_an_exception(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        entry = post_journal(
            JournalSpec(
                date=day(2026, 12, 30),
                lines=[
                    LineSpec(account=books["bank"], debit=Decimal("75")),
                    LineSpec(account=books["revenue"], credit=Decimal("75")),
                ],
                narration="Accrual",
                journal_type="adjusting",
                auto_reverse_on=day(2026, 12, 31),
            ),
            user=books["adviser"],
        )
    close_year(org, day(2026, 12, 31), books["owner"])
    noon = dt.datetime(2027, 1, 2, 17, tzinfo=dt.UTC)
    assert post_due_reversals(now=noon) == 0
    assert post_due_reversals(now=noon) == 0  # the job again
    with org_context(org):
        entry.refresh_from_db()
        events = AuditEvent.objects.filter(action="ledger.journalentry.auto_reversal_skipped")
        assert entry.status == "posted" and events.count() == 1
        assert events.first().meta["code"] == "lock.violation"  # type: ignore[union-attr]
