"""E-02-T03 — duplicate-bill suspects: same supplier, total within ±1 %, date within ±10 days,
not void or deleted; a soft warning (never a block) and a review list of pairs, each pair once."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.purchases.duplicates import review_list, suspects_for
from numo9.tenancy.context import org_context
from tests.bill_helpers import DAY, bill, bill_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return bill_books()


def test_fixture_duplicates_are_surfaced(books: dict[str, Any]) -> None:
    original = bill(books, [("1", "1000.00")], supplier_invoice_no="A-1")
    near = bill(
        books, [("1", "1009.00")], date=DAY + dt.timedelta(days=9), supplier_invoice_no="A-1b"
    )
    off = bill(books, [("1", "1011.00")], date=DAY + dt.timedelta(days=2))  # 1.1 % off original
    late = bill(books, [("1", "1000.00")], date=DAY + dt.timedelta(days=11))  # 11 days later
    bill(books, [("1", "1000.00")], supplier="other")  # another supplier
    with org_context(books["org"]):
        found = suspects_for(original)
        assert [row["id"] for row in found] == [str(near.public_id)]
        assert found[0]["days_apart"] == 9
        assert "A-1b from Cedar Supply Co." in found[0]["message"]
        # Each bill has its own window: 1011.00 and the 11-days-later bill are close to `near`.
        assert {row["id"] for row in suspects_for(near)} == {
            str(original.public_id),
            str(off.public_id),
            str(late.public_id),
        }


def test_closest_first_and_deleted_bills_left_out(books: dict[str, Any]) -> None:
    target = bill(books, [("1", "500.00")])
    farther = bill(books, [("1", "504.00")])
    closer = bill(books, [("1", "500.00")], date=DAY + dt.timedelta(days=3))
    gone = bill(books, [("1", "500.00")])
    with org_context(books["org"]):
        gone.soft_delete()
        assert [r["id"] for r in suspects_for(target)] == [
            str(closer.public_id),
            str(farther.public_id),
        ]


def test_review_list_has_each_pair_once(books: dict[str, Any]) -> None:
    a = bill(books, [("1", "250.00")])
    b = bill(books, [("1", "250.00")], date=DAY + dt.timedelta(days=1))
    bill(books, [("1", "999.00")])
    with org_context(books["org"]):
        pairs = review_list()
    assert len(pairs) == 1
    assert {pairs[0]["bill"]["id"], pairs[0]["suspect"]["id"]} == {
        str(a.public_id),
        str(b.public_id),
    }
