"""C-02-T08 — ``post_journal()`` atomic service. Acceptance: a failure leaves no partial rows.

Covers: a valid journal is posted (number, Posted, posted by/at, lines with contact, tracking,
description, tax code, book scope, source); numbers follow each other; one audit event
``ledger.journalentry.posted`` listing the lines (no draft "created" event); failures at every
step — invalid spec, locked date, closed period, a database error after the lines were written —
leave no entry, no line, no number used and no audit event; the module's lock applies; the
active organisation only; a system posting (no person).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.db import DatabaseError

from numo9.accounts.models import User
from numo9.audit import service as audit_service
from numo9.audit.context import audit_context
from numo9.audit.models import AuditEvent
from numo9.ledger import services
from numo9.ledger.models import Account, JournalEntry, JournalLine, JournalSequence, JournalStatus
from numo9.ledger.periods import (
    ClosedPeriod,
    PeriodClosed,
    register_period_check,
    unregister_period_check,
)
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalInvalid, JournalSpec, LineSpec
from numo9.orgsettings.locks import LockedPeriod
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

DATE = dt.date(2026, 4, 15)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def acc(org: Organisation) -> dict[str, Account]:
    return {
        "ar": account(org, "1100", "Accounts receivable", subtype="current_asset"),
        "sales": account(org, "4000", "Sales", subtype="revenue"),
        "gst": account(org, "2200", "GST/HST payable", subtype="current_liability"),
    }


@pytest.fixture
def olivia(org: Organisation) -> User:
    return User.objects.create_user(email="olivia@maple.ca", password="x" * 12, name="Olivia")


def invoice(acc: dict[str, Account], day: dt.date = DATE, **extra: Any) -> JournalSpec:
    return JournalSpec(
        date=day,
        type="sales",
        narration="Invoice INV-0042",
        source_type="sales.Invoice",
        source_id="inv-42",
        lines=(
            LineSpec(acc["ar"], debit=Decimal("1130.00"), **extra),
            LineSpec(acc["sales"], credit=Decimal("1000.00"), description="  Catering   order "),
            LineSpec(acc["gst"], credit=Decimal("130.00"), tax_code="HST-ON"),
        ),
    )


def nothing_written() -> None:
    assert not JournalEntry.objects.exists()
    assert not JournalLine.objects.exists()
    assert not AuditEvent.objects.filter(object_type="ledger.JournalEntry").exists()


def test_posts_a_journal(org: Organisation, acc: dict[str, Account], olivia: User) -> None:
    customer = contact(org, "Érable Distribution inc.")
    entry = post_journal(invoice(acc, contact=customer, tracking={"region": "east"}), user=olivia)
    stored = JournalEntry.objects.get()
    assert stored.pk == entry.pk and stored.status == JournalStatus.POSTED
    assert stored.number == 1 and stored.posted_by == olivia and stored.posted_at is not None
    assert stored.created_by == olivia and stored.type == "sales"
    assert (stored.source_type, stored.source_id, stored.book_scope) == (
        "sales.Invoice",
        "inv-42",
        "both",
    )
    lines = list(stored.lines.order_by("line_no"))
    assert [(line.debit, line.credit) for line in lines] == [
        (Decimal("1130.00"), Decimal("0.00")),
        (Decimal("0.00"), Decimal("1000.00")),
        (Decimal("0.00"), Decimal("130.00")),
    ]
    assert lines[0].contact == customer and lines[0].tracking == {"region": "east"}
    assert lines[1].description == "Catering order" and lines[2].tax_code == "HST-ON"
    assert post_journal(invoice(acc), user=olivia).number == 2


def test_one_posting_event_with_the_lines(acc: dict[str, Account], olivia: User) -> None:
    with audit_context(kind="user", user=olivia, label="Olivia"):
        entry = post_journal(invoice(acc))
    events = list(AuditEvent.objects.filter(object_type="ledger.JournalEntry"))
    assert [e.action for e in events] == ["ledger.journalentry.posted"]
    event = events[0]
    assert event.object_id == str(entry.public_id) and event.actor_user == olivia
    assert event.changes == {"status": ["draft", "posted"], "number": [None, 1]}
    assert event.meta["number"] == "JE-000001" and event.meta["date"] == "2026-04-15"
    assert event.meta["source"] == {"type": "sales.Invoice", "id": "inv-42"}
    assert [(row["line"], row["debit"], row["credit"]) for row in event.meta["lines"]] == [
        (1, "1130.00", "0.00"),
        (2, "0.00", "1000.00"),
        (3, "0.00", "130.00"),
    ]


def test_invalid_journal_writes_nothing(acc: dict[str, Account]) -> None:
    bad = JournalSpec(
        date=DATE,
        lines=(LineSpec(acc["ar"], debit=Decimal("10.00")), LineSpec(acc["sales"], credit="9.99")),
    )
    with pytest.raises(JournalInvalid):
        post_journal(bad)
    nothing_written()
    assert not JournalSequence.objects.exists()


def test_locked_date_writes_nothing(org: Organisation, acc: dict[str, Account]) -> None:
    LockDate(organisation=org, module="gl", level="everyone", date=DATE).save()
    with pytest.raises(LockedPeriod):
        post_journal(invoice(acc))
    nothing_written()
    post_journal(invoice(acc, DATE + dt.timedelta(days=1)))


def test_module_lock_applies(org: Organisation, acc: dict[str, Account]) -> None:
    LockDate(organisation=org, module="ar", level="everyone", date=DATE).save()
    post_journal(invoice(acc))  # a manual (GL) posting isn't stopped by the AR lock
    with pytest.raises(LockedPeriod) as refused:
        post_journal(invoice(acc), module="ar")
    assert refused.value.violation.module == "ar"


def test_closed_period_writes_nothing(acc: dict[str, Account]) -> None:
    period = ClosedPeriod(dt.date(2026, 1, 1), dt.date(2026, 12, 31), "Fiscal year 2026")

    def check(organisation: Organisation, date: dt.date) -> ClosedPeriod | None:
        return period

    register_period_check(check)
    try:
        with pytest.raises(PeriodClosed):
            post_journal(invoice(acc))
    finally:
        unregister_period_check(check)
    nothing_written()


def test_failure_after_the_lines_rolls_everything_back(
    acc: dict[str, Account], monkeypatch: pytest.MonkeyPatch
) -> None:
    post_journal(invoice(acc))  # number 1
    seen: dict[str, int] = {}

    def broken(organisation: Organisation) -> int:
        seen["lines"] = JournalLine.objects.count()
        raise DatabaseError("connection lost")

    monkeypatch.setattr(services, "allocate_journal_number", broken)
    with pytest.raises(DatabaseError):
        post_journal(invoice(acc))
    assert seen["lines"] == 6  # the second entry's lines were written…
    assert JournalEntry.objects.count() == 1 and JournalLine.objects.count() == 3  # …and undone
    assert AuditEvent.objects.filter(action="ledger.journalentry.posted").count() == 1
    monkeypatch.undo()
    assert post_journal(invoice(acc)).number == 2  # no number was used


def test_failure_in_the_audit_write_rolls_back(
    acc: dict[str, Account], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise DatabaseError("audit table unavailable")

    monkeypatch.setattr(audit_service, "record", broken)
    with pytest.raises(DatabaseError):
        post_journal(invoice(acc))
    nothing_written()


def test_system_posting_has_no_person(acc: dict[str, Account]) -> None:
    entry = post_journal(invoice(acc), user=None)
    assert entry.posted_by is None and JournalEntry.objects.get().created_by is None


def test_active_organisation_only(acc: dict[str, Account]) -> None:
    other = Organisation.objects.create(name="Other Inc.")
    with pytest.raises(ValueError, match="active organisation"):
        post_journal(invoice(acc), organisation=other)
