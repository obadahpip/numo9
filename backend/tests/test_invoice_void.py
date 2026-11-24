"""D-03a-T07 — voiding an invoice: the journal is reversed (the invoice nets to zero in the
ledger), the status becomes Void, the number is kept (never reused), the void is audited with
its reason; drafts, paid and already-void invoices can't be voided; a locked date is refused and
changes nothing.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum

from numo9.audit.models import AuditEvent
from numo9.ledger.models import JournalLine
from numo9.orgsettings.models import LockDate
from numo9.sales.models import Invoice
from numo9.sales.posting import InvoiceRefused, approve, void
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books["owner"] = people(books["org"])["owner"]
    return books


def net_by_account(books: dict[str, Any], invoice: Invoice) -> dict[str, Decimal]:
    with org_context(books["org"]):
        rows = (
            JournalLine.objects.filter(entry__in=[invoice.journal_entry, invoice.void_entry])
            .values("account__code")
            .annotate(net=Sum("debit") - Sum("credit"))
        )
        return {r["account__code"]: r["net"] for r in rows}


def test_void_reverses_keeps_the_number_and_is_audited(books: dict[str, Any]) -> None:
    invoice = approve(draft(books, [("2", "150.00", "sales.ON.standard")]), books["owner"])
    voided = void(invoice, books["owner"], reason="Entered twice")
    assert (voided.status, voided.number) == ("void", "INV-0001")
    assert voided.void_entry is not None and voided.voided_at is not None
    assert set(net_by_account(books, voided).values()) == {Decimal("0.00")}
    with org_context(books["org"]):
        assert voided.void_entry.reversal_of_id == voided.journal_entry_id
        assert voided.void_entry.date == DAY
        event = AuditEvent.objects.get(action="sales.invoice.voided")
        assert event.meta == {"number": "INV-0001", "reason": "Entered twice"}
        assert event.actor_user_id == books["owner"].pk
    # The number is never reused.
    again = approve(draft(books, [("1", "10.00", "sales.ON.standard")]), books["owner"])
    assert again.number == "INV-0002"


def test_what_cannot_be_voided(books: dict[str, Any]) -> None:
    with pytest.raises(InvoiceRefused):
        void(draft(books, [("1", "10.00", "sales.ON.standard")]), books["owner"])
    paid = approve(draft(books, [("1", "10.00", "sales.ON.standard")]), books["owner"])
    with org_context(books["org"]):
        Invoice._base_manager.filter(pk=paid.pk).update(
            amount_paid=Decimal("5.00"), status="partially_paid"
        )
        paid.refresh_from_db()
    with pytest.raises(InvoiceRefused) as caught:
        void(paid, books["owner"])
    assert "payments" in str(caught.value)
    done = void(
        approve(draft(books, [("1", "10.00", "sales.ON.standard")]), books["owner"]), books["owner"]
    )
    with pytest.raises(InvoiceRefused):
        void(done, books["owner"])


def test_locked_void_date_changes_nothing(books: dict[str, Any]) -> None:
    invoice = approve(draft(books, [("1", "10.00", "sales.ON.standard")]), books["owner"])
    with org_context(books["org"]):
        LockDate(organisation=books["org"], module="ar", level="everyone", date=DAY).save()
    with pytest.raises(Exception):  # noqa: B017 — the lock refusal (409)
        void(invoice, books["owner"])
    with org_context(books["org"]):
        invoice.refresh_from_db()
    assert invoice.status == "approved" and invoice.void_entry is None
    later = void(invoice, books["owner"], date=dt.date(2026, 6, 20))
    assert later.void_entry is not None and later.void_entry.date == dt.date(2026, 6, 20)
