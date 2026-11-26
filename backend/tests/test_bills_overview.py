"""E-02-T15 — purchases overview + bills list tabs: one query source (gap-22).

Acceptance (backend half of the UI task): every overview tile equals the count and amount of the
list tab of the same key; Overdue is "due before today in the organisation's time zone with an
open balance"; aging buckets and top suppliers add up to what is owed; unknown tab/section → 400.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from freezegun import freeze_time

from numo9.purchases.bill_posting import approve
from numo9.purchases.models import Bill, BillStatus
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books

pytestmark = pytest.mark.django_db

# 03:30 UTC on 1 Oct = 23:30 on 30 Sep in Toronto: the organisation's "today" is still 30 Sep.
NOW = "2026-10-01T03:30:00Z"
TODAY = dt.date(2026, 9, 30)


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    org = books["org"]
    org.time_zone = "America/Toronto"
    org.save(update_fields=["time_zone"])
    owner = books["owner"]
    numbers = iter(range(1, 100))

    def posted(amount: str, due: dt.date, supplier: str = "supplier", paid: str = "0") -> Bill:
        draft = bill(
            books,
            [("1", amount)],
            supplier=supplier,
            due_date=due,
            date=due - dt.timedelta(days=30),
            user=owner,
            supplier_invoice_no=f"INV-{next(numbers)}",
        )
        with org_context(org):
            done = approve(draft, owner)
            if Decimal(paid):
                Bill.objects.filter(pk=done.pk).update(
                    amount_paid=Decimal(paid), status=BillStatus.PARTIALLY_PAID
                )
        return done

    bill(books, [("1", "100.00")], user=owner)  # draft
    bill(books, [("2", "150.00")], user=owner)  # draft 300.00
    submitted = bill(books, [("1", "700.00")], user=owner)
    with org_context(org):
        Bill.objects.filter(pk=submitted.pk).update(status=BillStatus.AWAITING_APPROVAL)
    posted("1000.00", TODAY)  # due today: not overdue (and "current" in the aging)
    posted("400.00", TODAY - dt.timedelta(days=1), supplier="other")  # overdue 1 day
    posted("2500.00", TODAY - dt.timedelta(days=45), paid="500.00")  # overdue 45 d, 2,000 owed
    posted("300.00", TODAY - dt.timedelta(days=120), supplier="other")  # over 90 days
    paid_off = posted("999.00", TODAY - dt.timedelta(days=200))
    with org_context(org):
        Bill.objects.filter(pk=paid_off.pk).update(
            amount_paid=Decimal("999.00"), status=BillStatus.PAID
        )
    deleted = bill(books, [("1", "5000.00")], user=owner)
    with org_context(org):
        Bill.objects.filter(pk=deleted.pk).update(deleted_at=dt.datetime(2026, 9, 1, tzinfo=dt.UTC))
    return books


def client(books: dict[str, Any]) -> Client:
    c = Client()
    c.force_login(books["owner"])
    return c


def base(books: dict[str, Any]) -> str:
    return f"/api/v1/o/{books['org'].public_id}/bills"


@freeze_time(NOW)
def test_tiles_equal_list_tabs(books: dict[str, Any]) -> None:
    c = client(books)
    body = c.get(f"{base(books)}/overview").json()
    assert body["as_of"] == TODAY.isoformat()
    tiles = {t["key"]: (t["count"], t["amount"]) for t in body["tiles"]}
    assert tiles == {
        "draft": (2, "400.00"),
        "awaiting_approval": (1, "700.00"),
        "awaiting_payment": (4, "3700.00"),  # 1,000 + 400 + 2,000 + 300 still owed
        "overdue": (3, "2700.00"),  # not the bill due today (org time zone)
    }
    assert [t["key"] for t in body["tiles"]] == [
        "draft",
        "awaiting_approval",
        "awaiting_payment",
        "overdue",
    ]
    for tile in body["tiles"]:
        assert tile["href"].endswith(f"/purchases/bills?tab={tile['key']}")
        listed = c.get(base(books), {"tab": tile["key"]}).json()
        assert listed["count"] == tile["count"], tile["key"]
        assert sum(
            Decimal(
                r["amount_due"] if tile["key"] in ("awaiting_payment", "overdue") else r["total"]
            )
            for r in listed["results"]
        ) == Decimal(tile["amount"])
        tab = next(t for t in listed["tabs"] if t["key"] == tile["key"])
        assert (tab["count"], tab["amount"]) == (tile["count"], tile["amount"])


@freeze_time(NOW)
def test_list_tabs_and_status_filter(books: dict[str, Any]) -> None:
    c = client(books)
    listed = c.get(base(books)).json()
    assert listed["tab"] == "all"
    tabs = {t["key"]: t["count"] for t in listed["tabs"]}
    assert tabs == {
        "all": 8,  # deleted bill left out
        "draft": 2,
        "awaiting_approval": 1,
        "awaiting_payment": 4,
        "overdue": 3,
        "paid": 1,
        "void": 0,
    }
    assert [t["label"] for t in listed["tabs"]][:2] == ["All", "Draft"]
    assert listed["count"] == 8
    partly = c.get(base(books), {"tab": "awaiting_payment", "status": "partially_paid"}).json()
    assert partly["count"] == 1
    # The tab counts never depend on the filters of the current tab.
    assert {t["key"]: t["count"] for t in partly["tabs"]} == tabs
    refused = c.get(base(books), {"tab": "later"})
    assert (refused.status_code, refused.json()["code"]) == (400, "purchases.bill.bad_tab")


@freeze_time(NOW)
def test_aging_and_top_suppliers(books: dict[str, Any]) -> None:
    c = client(books)
    aging = c.get(f"{base(books)}/overview", {"section": "aging"}).json()
    assert "tiles" not in aging and "top_suppliers" not in aging
    assert [(b["key"], b["count"], b["amount"]) for b in aging["aging"]] == [
        ("current", 1, "1000.00"),
        ("1_30", 1, "400.00"),
        ("31_60", 1, "2000.00"),
        ("61_90", 0, "0.00"),
        ("over_90", 1, "300.00"),
    ]
    assert aging["aging"][1]["label"] == "1–30 days"
    top = c.get(f"{base(books)}/overview", {"section": "suppliers"}).json()["top_suppliers"]
    assert [(s["name"], s["owed"], s["overdue"], s["bills"]) for s in top] == [
        ("Cedar Supply Co.", "3000.00", "2000.00", 2),
        ("Maple Hardware Ltd", "700.00", "700.00", 2),
    ]
    bad = c.get(f"{base(books)}/overview", {"section": "everything"})
    assert (bad.status_code, bad.json()["code"]) == (400, "purchases.overview.bad_section")


def test_empty_organisation_answers_zeros() -> None:
    books = bill_books("Empty Books Ltd.")
    body = client(books).get(f"{base(books)}/overview").json()
    assert [(t["count"], t["amount"]) for t in body["tiles"]] == [(0, "0.00")] * 4
    assert [b["amount"] for b in body["aging"]] == ["0.00"] * 5
    assert body["top_suppliers"] == []


def test_overview_needs_bill_view_permission(books: dict[str, Any]) -> None:
    from tests.purchase_helpers import member

    employee = member(books["org"], "staff@refined.ca", "employee")
    c = Client()
    c.force_login(employee)
    assert c.get(f"{base(books)}/overview").status_code == 403
