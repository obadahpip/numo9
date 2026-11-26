"""D-04-T11 — ``manage.py replay_ticks``: replaying a day creates nothing new.

A day the hourly job already ran replays as "already ran" (no invoice, no run row added); a day
it missed (the workers were down) is generated once, and replaying it again adds nothing; a dry
run creates nothing; dates before the template existed are never replayed; bad arguments are
refused.
"""

from __future__ import annotations

import datetime as dt
from io import StringIO
from typing import Any

import pytest
from django.core.management import CommandError, call_command
from freezegun import freeze_time

from numo9.sales.models import RecurringInvoiceRun, RecurringInvoiceTemplate
from numo9.sales.recurring_invoices import generate_due
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import sales_books
from tests.test_recurring_invoice_generation import invoices, make_template

pytestmark = pytest.mark.django_db
D = dt.date


def replay(*args: str) -> str:
    out = StringIO()
    call_command("replay_ticks", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def books(db: Any) -> dict[str, Any]:
    with freeze_time("2026-01-02 12:00:00"):
        books = sales_books()
        books["owner"] = people(books["org"])["owner"]
        books["template"] = make_template(books)
    return books


def test_replaying_a_day_that_ran_creates_nothing_new(books: dict[str, Any]) -> None:
    org = books["org"]
    generate_due(org, D(2026, 2, 28))
    before = len(invoices(org))
    out = replay("--date", "2026-01-31", "--to", "2026-02-28", "--org", str(org.public_id))
    assert out.count(": already ran") == 2
    assert out.strip().endswith("2 occurrences: 0 created, 0 skipped, 2 already ran.")
    assert len(invoices(org)) == before == 2
    with org_context(org):
        assert RecurringInvoiceRun.objects.count() == 2


def test_a_missed_day_is_generated_once(books: dict[str, Any]) -> None:
    org = books["org"]
    dry = replay("--date", "2026-01-31", "--dry-run", "--kind", "invoices")
    assert "Monthly retainer · 2026-01-31: would run" in dry
    assert invoices(org) == []  # a dry run creates nothing
    out = replay("--date", "2026-01-31", "--kind", "invoices")
    assert "Monthly retainer · 2026-01-31: created" in out
    again = replay("--date", "2026-01-31")
    assert "2026-01-31: already ran" in again
    assert [i.date for i in invoices(org)] == [D(2026, 1, 31)]
    with org_context(org):
        template = RecurringInvoiceTemplate.objects.get(pk=books["template"].pk)
        assert template.next_run == D(2026, 1, 31)  # the job moves it, not the replay
    assert generate_due(org, D(2026, 1, 31)) == []  # nor does the tick create it again


def test_days_before_the_template_existed_are_not_replayed(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        RecurringInvoiceTemplate.objects.filter(pk=books["template"].pk).update(
            start_date=D(2025, 11, 30)
        )
    out = replay("--date", "2025-11-01", "--to", "2025-12-31")
    assert out.strip() == "0 occurrences: 0 created, 0 skipped, 0 already ran."


def test_bad_arguments_are_refused(books: dict[str, Any]) -> None:
    with pytest.raises(CommandError, match="isn't a date"):
        replay("--date", "31/01/2026")
    with pytest.raises(CommandError, match="before"):
        replay("--date", "2026-02-01", "--to", "2026-01-01")
    with pytest.raises(CommandError, match="Unknown kind"):
        replay("--date", "2026-02-01", "--kind", "quotes")
