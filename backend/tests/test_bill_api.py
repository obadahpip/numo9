"""E-02-T10 — bills API: create a draft (lines, totals, holdback, attached document), list with
status counts and search, edit with optimistic versioning, delete drafts, preview (journal, ITC,
routing, suspects), submit / approve / void / release holdback, bill from PO, duplicates; the
duplicate supplier invoice number is refused at save; permissions and tenant sweep."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.orgsettings.models import TaxRegistration
from numo9.purchases.models import Bill
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.bill_helpers import DAY, bill_books, member

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    client = Client()
    client.force_login(books["owner"])
    with org_context(books["org"]):
        tax = code_for("purchase.ON.standard", "purchase", DAY, books["org"])
        TaxRegistration(
            organisation=books["org"],
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
    return {
        **books,
        "client": client,
        "base": f"/api/v1/o/{books['org'].public_id}/bills",
        "tax": tax,
    }


def payload(books: dict[str, Any], **over: Any) -> dict[str, Any]:
    return {
        "supplier": str(books["supplier"].public_id),
        "date": DAY.isoformat(),
        "supplier_invoice_no": "CS-1001",
        "lines": [
            {
                "description": "Tiles",
                "quantity": "10",
                "unit_price": "45.00",
                "account": str(books["expense"].public_id),
                "tax_code": str(books["tax"].public_id),
            }
        ],
        **over,
    }


def post(books: dict[str, Any], url: str, body: Any = None) -> Any:
    return books["client"].post(url, body or {}, content_type="application/json")


def test_create_list_edit_delete(books: dict[str, Any]) -> None:
    base = books["base"]
    made = post(books, base, payload(books, holdback_type="percent", holdback_value="10"))
    assert made.status_code == 201, made.json()
    bill = made.json()
    assert (bill["status"], bill["number"], bill["total"], bill["holdback_amount"]) == (
        "draft",
        "",
        "508.50",
        "50.85",
    )
    assert bill["due_date"] is not None and bill["lines"][0]["tax_amount"] == "58.50"
    listed = books["client"].get(base, {"q": "CS-10"}).json()
    assert [r["id"] for r in listed["results"]] == [bill["id"]] and listed["counts"]["draft"] == 1
    assert books["client"].get(base, {"status": "paid"}).json()["results"] == []
    edited = books["client"].patch(
        f"{base}/{bill['id']}",
        payload(books, supplier_invoice_no="CS-1002", version=bill["version"]),
        content_type="application/json",
    )
    assert edited.status_code == 200, edited.json()
    assert (edited.json()["supplier_invoice_no"], edited.json()["version"]) == ("CS-1002", 2)
    stale = books["client"].patch(
        f"{base}/{bill['id']}", payload(books, version=1), content_type="application/json"
    )
    assert (stale.status_code, stale.json()["code"]) == (409, "purchases.bill.stale")
    assert books["client"].delete(f"{base}/{bill['id']}").status_code == 204
    assert books["client"].get(f"{base}/{bill['id']}").status_code == 404


def test_duplicate_supplier_invoice_number_is_refused_at_save(books: dict[str, Any]) -> None:
    assert post(books, books["base"], payload(books)).status_code == 201
    again = post(books, books["base"], payload(books, supplier_invoice_no=" cs-1001"))
    assert again.status_code == 400
    assert again.json()["supplier_invoice_no"][0].startswith("Already used on a draft bill")
    other = payload(books, supplier=str(books["other"].public_id))
    assert post(books, books["base"], other).status_code == 201


def test_preview_and_the_life_of_a_bill(books: dict[str, Any]) -> None:
    base = books["base"]
    bill = post(books, base, payload(books, holdback_type="amount", holdback_value="100")).json()
    shown = books["client"].get(f"{base}/{bill['id']}/preview").json()
    assert shown["journal"]["complete"] is True
    assert [line["credit"] for line in shown["journal"]["lines"] if line["credit"] != "0.00"] == [
        "408.50",
        "100.00",
    ]
    assert shown["itc"] == [{"tax": "58.50", "claimable": "58.50", "cost": "0.00"}]
    assert (
        shown["routing"]["explanation"] == "" and shown["duplicates"] == [] and shown["match"] == []
    )
    approved = post(books, f"{base}/{bill['id']}/approve")
    assert approved.status_code == 200, approved.json()
    assert (approved.json()["status"], approved.json()["number"]) == (
        "awaiting_payment",
        "BILL-0001",
    )
    again = post(books, f"{base}/{bill['id']}/approve")
    assert (again.status_code, again.json()["code"]) == (400, "purchases.bill.not_draft")
    released = post(
        books, f"{base}/{bill['id']}/release-holdback", {"amount": "40", "date": "2026-07-01"}
    )
    assert released.json()["holdback_released"] == "40.00"
    refused = post(books, f"{base}/{bill['id']}/void")
    assert (refused.status_code, refused.json()["code"]) == (400, "purchases.bill.not_voidable")
    patched = books["client"].patch(
        f"{base}/{bill['id']}", payload(books), content_type="application/json"
    )
    assert patched.json()["code"] == "purchases.bill.not_editable"
    second = post(books, base, payload(books, supplier_invoice_no="CS-2")).json()
    post(books, f"{base}/{second['id']}/approve")
    voided = post(books, f"{base}/{second['id']}/void", {"reason": "Typo", "date": "2026-06-20"})
    assert voided.json()["status"] == "void"


def test_submit_from_po_and_duplicates(books: dict[str, Any]) -> None:
    from numo9.purchases.approvals import approve as approve_po
    from numo9.purchases.receipts import receive
    from tests.purchase_helpers import po

    base = books["base"]
    bill = post(books, base, payload(books)).json()
    sent = post(books, f"{base}/{bill['id']}/submit")
    assert sent.json()["status"] == "awaiting_approval"
    post(books, base, payload(books, supplier_invoice_no="CS-9"))
    assert len(books["client"].get(f"{base}/duplicates").json()["results"]) == 1
    order = approve_po(po(books, [("3", "20.00")]), books["owner"])
    with org_context(books["org"]):
        line = order.lines.get()
    receive(order, books["owner"], [(line, Decimal("2"))])
    made = post(books, f"{base}/from-po", {"purchase_order": str(order.public_id)})
    assert made.status_code == 201, made.json()
    assert (made.json()["purchase_order"]["number"], made.json()["lines"][0]["quantity"]) == (
        order.number,
        "2.0000",
    )
    nothing = post(books, f"{base}/from-po", {"purchase_order": str(order.public_id)})
    assert nothing.status_code == 201  # the first is a draft: billed quantities move at approval


def test_permissions_and_features(books: dict[str, Any]) -> None:
    base = books["base"]
    bill = post(books, base, payload(books)).json()
    hr = Client()
    hr.force_login(member(books["org"], "hr@refined.ca", "hr"))
    assert hr.get(base).status_code == 403
    clerk = Client()
    clerk.force_login(books["clerk"])  # admin without a bill approval limit
    refused = clerk.post(f"{base}/{bill['id']}/approve", {}, content_type="application/json")
    assert refused.status_code == 403
    with org_context(books["org"]):
        assert Bill.objects.get(public_id=bill["id"]).status == "draft"
