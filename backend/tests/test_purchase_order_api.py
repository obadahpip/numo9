"""E-01-T10 — purchase orders, receipts, match and commitments API: create a draft with the
delivery block, list with status counts (the tabs) and search, the limit indicator, approval
within the limit (5,000 cannot approve 5,001), edit an approved PO (lines kept by id, a higher
total → Awaiting approval, a received line can't go), receive 6 of 10 (4 outstanding,
Partially received), the over-receipt confirmation, reversal, the 3-way match (bill 12 vs PO 10
flagged), cancel / close, PDF, the commitment report and its export = screen; permissions,
OpenAPI, tenant sweep and permission check."""

from __future__ import annotations

import csv
import io
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.orgsettings.service import get_settings
from numo9.purchases.models import BillLine, PurchaseOrder
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill_books, member

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    with org_context(books["org"]):
        settings = get_settings(books["org"])
        settings.bill_requires_supplier_invoice_no = False
        settings.save()
    owner = Client()
    owner.force_login(books["owner"])
    buyer = Client()
    buyer.force_login(books["buyer"])
    org = books["org"].public_id
    return {
        **books,
        "client": owner,
        "buyer_client": buyer,
        "api": f"/api/v1/o/{org}",
        "base": f"/api/v1/o/{org}/purchase-orders",
    }


def payload(books: dict[str, Any], lines: list[tuple[str, str]], **over: Any) -> dict[str, Any]:
    return {
        "supplier": str(books["supplier"].public_id),
        "date": "2026-06-15",
        "tax_mode": "no_tax",
        "delivery_attention": "Site office",
        "delivery_address": "12 King St W, Toronto ON",
        "delivery_date": "2026-06-30",
        "delivery_instructions": "Loading dock at the back",
        "lines": [
            {
                "description": f"Line {n + 1}",
                "quantity": qty,
                "unit_price": price,
                "account": str(books["expense"].public_id),
            }
            for n, (qty, price) in enumerate(lines)
        ],
        **over,
    }


def post(client: Client, url: str, body: Any = None) -> Any:
    return client.post(url, body or {}, content_type="application/json")


def made(books: dict[str, Any], lines: list[tuple[str, str]], client: Any = None) -> Any:
    response = post(client or books["client"], books["base"], payload(books, lines))
    assert response.status_code == 201, response.json()
    return response.json()


def test_create_list_tabs_and_limit_indicator(books: dict[str, Any]) -> None:
    order = made(books, [("10", "25.00"), ("2", "100.00")], books["buyer_client"])
    assert (order["status"], order["number"], order["total"]) == ("draft", "", "450.00")
    assert (order["delivery_attention"], order["delivery_date"]) == ("Site office", "2026-06-30")
    assert order["approval"] == {"limit": "5000.00", "within": True}
    big = made(books, [("1", "5001.00")], books["buyer_client"])
    assert big["approval"] == {"limit": "5000.00", "within": False}
    mine = books["buyer_client"].get(f"{books['base']}/approval-limit").json()
    assert mine == {"limit": "5000.00"}
    clerk = Client()
    clerk.force_login(books["clerk"])
    assert clerk.get(f"{books['base']}/{big['id']}").json()["approval"] == {
        "limit": None,
        "within": False,
    }
    approved = post(books["buyer_client"], f"{books['base']}/{order['id']}/approve")
    assert (approved.json()["status"], approved.json()["number"]) == ("approved", "PO-0001")
    listed = books["client"].get(books["base"]).json()
    assert listed["count"] == 2
    assert (listed["counts"]["draft"], listed["counts"]["approved"]) == (1, 1)
    tab = books["client"].get(books["base"], {"status": "approved"}).json()
    assert [r["number"] for r in tab["results"]] == ["PO-0001"]
    found = books["client"].get(books["base"], {"q": "PO-00"}).json()
    assert [r["id"] for r in found["results"]] == [order["id"]]
    assert books["client"].get(books["base"], {"q": "Cedar"}).json()["count"] == 2


def test_limit_5000_cannot_approve_5001_and_submit(books: dict[str, Any]) -> None:
    big = made(books, [("1", "5001.00")], books["buyer_client"])
    refused = post(books["buyer_client"], f"{books['base']}/{big['id']}/approve")
    assert refused.status_code == 403
    with org_context(books["org"]):
        assert PurchaseOrder.objects.get(public_id=big["id"]).status == "draft"
    sent = post(books["buyer_client"], f"{books['base']}/{big['id']}/submit")
    assert sent.json()["status"] == "awaiting_approval"
    again = post(books["buyer_client"], f"{books['base']}/{big['id']}/submit")
    assert (again.status_code, again.json()["code"]) == (400, "purchases.po.not_draft")
    assert post(books["client"], f"{books['base']}/{big['id']}/approve").json()["status"] == (
        "approved"
    )


def test_edit_draft_and_approved_po(books: dict[str, Any]) -> None:
    base = books["base"]
    order = made(books, [("10", "25.00")])
    line = order["lines"][0]["id"]
    edit = payload(books, [("10", "25.00"), ("1", "50.00")], version=order["version"])
    edit["lines"][0]["id"] = line
    edited = books["client"].patch(f"{base}/{order['id']}", edit, content_type="application/json")
    assert edited.status_code == 200, edited.json()
    assert (edited.json()["total"], edited.json()["lines"][0]["id"]) == ("300.00", line)
    stale = books["client"].patch(
        f"{base}/{order['id']}", {**edit, "version": 1}, content_type="application/json"
    )
    assert (stale.status_code, stale.json()["code"]) == (409, "purchases.po.stale")
    approved = post(books["client"], f"{base}/{order['id']}/approve").json()
    lines = approved["lines"]
    post(
        books["client"],
        f"{books['api']}/receipts",
        {"purchase_order": order["id"], "lines": [{"po_line": lines[0]["id"], "quantity": "6"}]},
    )
    shown = books["client"].get(f"{base}/{order['id']}").json()
    drop = payload(books, [("1", "50.00")], version=shown["version"])
    drop["lines"][0]["id"] = lines[1]["id"]
    refused = books["client"].patch(f"{base}/{order['id']}", drop, content_type="application/json")
    assert refused.status_code == 400 and "removed" in refused.json()["lines"]
    below = payload(books, [("5", "25.00"), ("1", "50.00")], version=shown["version"])
    below["lines"][0]["id"], below["lines"][1]["id"] = lines[0]["id"], lines[1]["id"]
    refused = books["client"].patch(f"{base}/{order['id']}", below, content_type="application/json")
    assert refused.status_code == 400 and "0" in refused.json()["lines"]
    more = payload(books, [("10", "25.00"), ("3", "50.00")], version=shown["version"])
    more["lines"][0]["id"], more["lines"][1]["id"] = lines[0]["id"], lines[1]["id"]
    revised = books["client"].patch(f"{base}/{order['id']}", more, content_type="application/json")
    assert revised.status_code == 200, revised.json()
    assert (revised.json()["status"], revised.json()["number"], revised.json()["total"]) == (
        "awaiting_approval",
        "PO-0001",
        "400.00",
    )
    assert revised.json()["lines"][0]["quantity_received"] == "6.0000"
    assert books["client"].delete(f"{base}/{order['id']}").json()["code"] == (
        "purchases.po.not_deletable"
    )
    draft = made(books, [("1", "1.00")])
    assert books["client"].delete(f"{base}/{draft['id']}").status_code == 204
    assert books["client"].get(f"{base}/{draft['id']}").status_code == 404


def test_receive_partially_over_tolerance_and_reverse(books: dict[str, Any]) -> None:
    order = made(books, [("10", "25.00")])
    post(books["client"], f"{books['base']}/{order['id']}/approve")
    line = order["lines"][0]["id"]
    receipts = f"{books['api']}/receipts"
    six = post(
        books["client"],
        receipts,
        {
            "purchase_order": order["id"],
            "date": "2026-06-20",
            "notes": "Pallet 1",
            "lines": [{"po_line": line, "quantity": "6"}],
        },
    )
    assert six.status_code == 201, six.json()
    assert (six.json()["purchase_order_status"], six.json()["lines"][0]["quantity"]) == (
        "partially_received",
        "6.0000",
    )
    shown = books["client"].get(f"{books['base']}/{order['id']}").json()
    assert (shown["lines"][0]["outstanding"], shown["status"]) == ("4.0000", "partially_received")
    assert [r["id"] for r in shown["receipts"]] == [six.json()["id"]]
    over = post(
        books["client"],
        receipts,
        {"purchase_order": order["id"], "lines": [{"po_line": line, "quantity": "5"}]},
    )
    assert (over.status_code, over.json()["code"]) == (
        400,
        "purchases.receipt.over_tolerance_confirm",
    )
    assert over.json()["over"][0]["received"] == "11.0000"
    confirmed = post(
        books["client"],
        receipts,
        {
            "purchase_order": order["id"],
            "lines": [{"po_line": line, "quantity": "5"}],
            "confirm_over": True,
        },
    )
    assert confirmed.status_code == 201 and confirmed.json()["warnings"]
    assert confirmed.json()["purchase_order_status"] == "received"
    listed = books["client"].get(receipts, {"purchase_order": order["id"]}).json()
    assert len(listed["results"]) == 2
    no_reason = post(books["client"], f"{receipts}/{confirmed.json()['id']}/reverse")
    assert no_reason.json()["code"] == "purchases.receipt.reason"
    reversed_ = post(
        books["client"], f"{receipts}/{confirmed.json()['id']}/reverse", {"reason": "Wrong PO"}
    )
    assert reversed_.status_code == 200 and reversed_.json()["reversed_at"]
    shown = books["client"].get(f"{books['base']}/{order['id']}").json()
    assert (shown["status"], shown["lines"][0]["outstanding"]) == ("partially_received", "4.0000")
    foreign = post(
        books["client"],
        receipts,
        {"purchase_order": order["id"], "lines": [{"po_line": order["id"], "quantity": "1"}]},
    )
    assert foreign.status_code == 400


def test_match_bill_12_against_po_10(books: dict[str, Any]) -> None:
    order = made(books, [("10", "25.00")])
    post(books["client"], f"{books['base']}/{order['id']}/approve")
    line = order["lines"][0]["id"]
    post(
        books["client"],
        f"{books['api']}/receipts",
        {"purchase_order": order["id"], "lines": [{"po_line": line, "quantity": "10"}]},
    )
    bill = post(books["client"], f"{books['api']}/bills/from-po", {"purchase_order": order["id"]})
    with org_context(books["org"]):
        BillLine.objects.filter(document__public_id=bill.json()["id"]).update(
            quantity=Decimal("12")
        )
    match = books["client"].get(f"{books['base']}/{order['id']}/match").json()
    assert match["status"] == "red"
    (row,) = match["lines"]
    assert (row["ordered"], row["received"], row["flags"]) == (
        "10.0000",
        "10.0000",
        ["over_ordered", "over_received"],
    )
    assert row["bills"][0]["quantity"] == "12.0000" and row["bills"][0]["match"] == "red"


def test_cancel_close_and_pdf(books: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    base = books["base"]
    draft = made(books, [("1", "10.00")])
    cancelled = post(books["client"], f"{base}/{draft['id']}/cancel")
    assert cancelled.json()["status"] == "cancelled"
    order = made(books, [("10", "25.00")])
    post(books["client"], f"{base}/{order['id']}/approve")
    post(
        books["client"],
        f"{books['api']}/receipts",
        {
            "purchase_order": order["id"],
            "lines": [{"po_line": order["lines"][0]["id"], "quantity": "6"}],
        },
    )
    closed = post(books["client"], f"{base}/{order['id']}/cancel")
    assert closed.json()["status"] == "closed"  # partially received: closed, not cancelled
    again = post(books["client"], f"{base}/{order['id']}/close")
    assert (again.status_code, again.json()["code"]) == (400, "purchases.po.not_closable")
    edit = books["client"].patch(
        f"{base}/{order['id']}", payload(books, [("1", "1")]), content_type="application/json"
    )
    assert edit.json()["code"] == "purchases.po.not_editable"
    monkeypatch.setattr(
        "numo9.purchases.pdf.render_purchase_order_pdf", lambda order: b"%PDF-1.7 stub"
    )
    pdf = books["client"].get(f"{base}/{order['id']}/pdf")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    defaults = books["client"].get(f"{base}/{order['id']}/send").json()
    assert defaults["file_name"] == "purchase-order-PO-0001.pdf"


def test_commitment_report_and_export_equal_the_screen(books: dict[str, Any]) -> None:
    first = made(books, [("10", "25.00"), ("4", "80.00")])
    post(books["client"], f"{books['base']}/{first['id']}/approve")
    other = payload(books, [("2", "100.00")], supplier=str(books["other"].public_id))
    second = post(books["client"], books["base"], other).json()
    post(books["client"], f"{books['base']}/{second['id']}/approve")
    made(books, [("1", "999.00")])  # a draft commits nothing
    url = f"{books['api']}/reports/commitments"
    screen = books["client"].get(url, {"by": "supplier"}).json()
    assert screen["total"] == "770.00"
    assert [(r["label"], r["amount"], r["orders"]) for r in screen["rows"]] == [
        ("Cedar Supply Co.", "570.00", 1),
        ("Maple Hardware Ltd", "200.00", 1),
    ]
    exported = books["client"].get(url, {"by": "supplier", "export": "csv"})
    assert exported.status_code == 200 and exported["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0][0] == "Supplier" and rows[-1][0] == "Total"
    assert [(r[0], r[3]) for r in rows[1:-1]] == [(r["label"], r["amount"]) for r in screen["rows"]]
    assert rows[-1][3] == screen["total"]
    xlsx = books["client"].get(url, {"by": "month", "export": "xlsx"})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    by_month = books["client"].get(url, {"by": "month", "from": "2026-07-01"}).json()
    assert (by_month["rows"], by_month["total"], by_month["from"]) == ([], "0.00", "2026-07-01")
    assert books["client"].get(url, {"by": "colour"}).status_code == 400


def test_permissions_schema_sweep(books: dict[str, Any]) -> None:
    order = made(books, [("1", "10.00")])
    hr = Client()
    hr.force_login(member(books["org"], "hr@refined.ca", "hr"))
    assert hr.get(books["base"]).status_code == 403
    assert hr.get(f"{books['api']}/reports/commitments").status_code == 403
    clerk = Client()
    clerk.force_login(books["clerk"])  # admin without a purchase-order approval limit
    assert post(clerk, f"{books['base']}/{order['id']}/approve").status_code == 403
    schema = StringIO()
    call_command("spectacular", "--format", "openapi-json", stdout=schema)
    for path in (
        "/api/v1/o/{org}/purchase-orders",
        "/api/v1/o/{org}/purchase-orders/{public_id}/match",
        "/api/v1/o/{org}/receipts",
        "/api/v1/o/{org}/receipts/{public_id}/reverse",
        "/api/v1/o/{org}/reports/commitments",
    ):
        assert f'"{path}"' in schema.getvalue(), path
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
