"""D-07-T07 — the ``disputed`` flag on an invoice and the customer's reminder opt-out: either one
stops reminders (``reminder_block``); a disputed invoice is charged no late fee; flagging needs
what is disputed, is audited, and resolving it lets reminders and fees resume."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.contacts.models import Contact
from numo9.sales.disputes import DisputeRefused, reminder_block, set_disputed
from numo9.sales.late_fees import late_fees
from numo9.sales.models import Invoice, LateFeePolicy
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db
D = Decimal
DUE = dt.date(2026, 7, 15)


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    made = draft(books, [("10", "100.00", "sales.ON.standard")])
    with org_context(books["org"]):
        made.due_date = DUE
        made.save(update_fields=["due_date"])
        LateFeePolicy.objects.create(
            organisation=books["org"], is_active=True, rate_pct=D("24"), fee_account=None
        )
    books["invoice"] = approve(made, books["owner"])
    return books


def fresh(books: dict[str, Any]) -> Invoice:
    with org_context(books["org"]):
        found: Invoice = Invoice.objects.select_related("contact").get(pk=books["invoice"].pk)
        return found


@pytest.mark.parametrize(
    ("disputed", "opted_out", "blocked"),
    [
        (False, False, None),
        (True, False, "disputed"),
        (False, True, "opted_out"),
        (True, True, "disputed"),
    ],
)
def test_the_flag_and_the_opt_out_stop_reminders(
    books: dict[str, Any], disputed: bool, opted_out: bool, blocked: str | None
) -> None:
    if disputed:
        set_disputed(books["invoice"], True, books["owner"], reason="Chairs arrived damaged")
    with org_context(books["org"]):
        Contact.objects.filter(pk=books["invoice"].contact_id).update(reminders_opt_out=opted_out)
    assert reminder_block(fresh(books)) == blocked


def test_dispute_is_audited_stops_fees_and_resolves(books: dict[str, Any]) -> None:
    august = dt.date(2026, 8, 15)
    assert len(late_fees(books["org"], august)) == 1
    set_disputed(books["invoice"], True, books["owner"], reason="  Chairs   damaged ")
    invoice = fresh(books)
    assert (invoice.disputed, invoice.dispute_reason) == (True, "Chairs damaged")
    assert invoice.disputed_at is not None
    assert late_fees(books["org"], august) == []  # no late fee while disputed
    with org_context(books["org"]):
        event = AuditEvent.objects.filter(changes__has_key="disputed").latest("pk")
    assert event.changes["disputed"] == [False, True]

    set_disputed(books["invoice"], False, books["owner"])
    invoice = fresh(books)
    assert (invoice.disputed, invoice.disputed_at, invoice.dispute_reason) == (False, None, "")
    assert reminder_block(invoice) is None
    assert len(late_fees(books["org"], august)) == 1


def test_a_dispute_needs_a_reason_and_a_posted_invoice(books: dict[str, Any]) -> None:
    with pytest.raises(DisputeRefused) as refused:
        set_disputed(books["invoice"], True, books["owner"], reason=" ")
    assert refused.value.code == "sales.dispute.reason_required"
    other = draft(books, [("1", "100.00", "sales.ON.standard")])
    with pytest.raises(DisputeRefused) as refused:
        set_disputed(other, True, books["owner"], reason="Wrong price")
    assert refused.value.code == "sales.dispute.not_posted"
    assert fresh(books).disputed is False
