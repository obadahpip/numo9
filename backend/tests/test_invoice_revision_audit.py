"""D-03b-T15 — audit event of a revision: the field diffs (old and new values), the reason and
the journal ids. Acceptance: the audit viewer (API) shows the old and new values."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.test import Client

from numo9.audit.models import AuditEvent
from numo9.sales.models import Invoice, InvoiceLine, InvoiceRevision
from numo9.sales.posting import approve
from numo9.sales.revisions import field_diffs, pdf_snapshot, record_revision_event
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db


def test_revision_event_has_diffs_reason_and_journals() -> None:
    books = sales_books()
    org = books["org"]
    owner = people(org)["owner"]
    invoice = approve(
        draft(books, [("1", "1000.00", "sales.ON.standard")], reference="PO 7781"), owner
    )
    with org_context(org):
        before = pdf_snapshot(invoice, dt.date(2026, 10, 26))
        InvoiceLine._base_manager.filter(document=invoice).update(unit_price=Decimal("900.00"))
        Invoice._base_manager.filter(pk=invoice.pk).update(reference="PO 7781-B")
        invoice = Invoice.objects.get(pk=invoice.pk)
        after = pdf_snapshot(invoice, dt.date(2026, 11, 3))
        revision = InvoiceRevision(organisation=org, invoice=invoice, revision=1, snapshot=after)
        revision.save()
        posted = invoice.journal_entry
        event = record_revision_event(
            revision,
            before=before,
            after=after,
            reason="  Price   correction ",
            journal_reversal=posted,
            journal_post=posted,
            user=owner,
        )
    changes = field_diffs(before, after)
    assert changes["total"] == ["1130.00", "1017.00"]
    assert changes["subtotal"] == ["1000.00", "900.00"]
    (tax_field,) = [name for name in changes if name.startswith("tax[")]
    assert changes[tax_field] == ["130.00", "117.00"]
    assert changes["reference"] == ["PO 7781", "PO 7781-B"]
    old_line, new_line = changes["lines[1]"]
    assert (old_line["unit"], new_line["unit"]) == ("1000.00", "900.00")
    assert set(changes) == {"total", tax_field, "subtotal", "reference", "lines[1]"}
    assert field_diffs(before, before) == {}
    with org_context(org):
        stored = AuditEvent.objects.get(pk=event.pk)
    assert (stored.action, stored.object_type) == ("sales.invoice.revised", "sales.Invoice")
    assert stored.actor_user == owner and stored.changes["total"] == ["1130.00", "1017.00"]
    assert stored.meta["reason"] == "Price correction"
    assert (stored.meta["revision"], stored.meta["number"]) == (1, "INV-0001-1")
    assert stored.meta["journal_reversal"] == {"id": str(posted.public_id), "number": posted.number}
    assert stored.meta["journal_post"]["number"] == posted.number

    # The audit viewer shows the old and new values.
    client = Client()
    client.force_login(owner)
    shown = client.get(f"/api/v1/o/{org.public_id}/audit/events/{stored.public_id}").json()
    by_field = {change["field"]: change for change in shown["changes"]}
    assert (by_field["total"]["old"], by_field["total"]["new"]) == ("1130.00", "1017.00")
    assert by_field["reference"]["new"] == "PO 7781-B"
    assert shown["meta"]["reason"] == "Price correction"
    history = client.get(
        f"/api/v1/o/{org.public_id}/audit/records/sales.Invoice/{invoice.public_id}"
    ).json()
    assert "sales.invoice.revised" in [row["action"] for row in history["results"]]


def test_lines_added_and_removed_are_named() -> None:
    line = {
        "description": "Design",
        "quantity": {"__decimal": "1"},
        "amount": {"__decimal": "100.00"},
    }
    extra = {
        "description": "Install",
        "quantity": {"__decimal": "2"},
        "amount": {"__decimal": "50.00"},
    }
    one, two = {"pdf": {"lines": [line]}}, {"pdf": {"lines": [line, extra]}}
    assert field_diffs(one, two) == {
        "lines[2]": [
            None,
            {"description": "Install", "quantity": "2.00", "amount": "50.00"},
        ]
    }
    assert field_diffs(two, one)["lines[2]"][1] is None
