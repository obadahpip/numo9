"""D-03a-T08 — duplicate-invoice soft warning: same customer, same total, date within 7 days
(drafts count, void ones don't); a warning only — approval still goes through.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.sales.duplicates import possible_duplicates
from numo9.sales.posting import approve, void
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books["owner"] = people(books["org"])["owner"]
    return books


def test_same_customer_total_and_week(books: dict[str, Any]) -> None:
    first = approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["owner"])
    twin = draft(books, [("1", "100.00", "sales.ON.standard")], date=DAY + dt.timedelta(days=7))
    with org_context(books["org"]):
        (hit,) = possible_duplicates(twin)
    assert (hit["number"], hit["total"]) == (first.number, "113.00")
    assert "INV-0001" in hit["message"] and "113.00" in hit["message"]
    # A warning only: the twin is still approved.
    assert approve(twin, books["owner"]).status == "approved"


def test_what_isnt_a_duplicate(books: dict[str, Any]) -> None:
    approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["owner"])
    cases = [
        draft(books, [("1", "100.00", "sales.ON.standard")], date=DAY + dt.timedelta(days=8)),
        draft(books, [("1", "100.01", "sales.ON.standard")]),
        draft(books, [("1", "100.00", "sales.BC.standard")], province="BC"),
    ]
    with org_context(books["org"]):
        for case in cases:
            others = [d for d in possible_duplicates(case) if d["status"] != "draft"]
            assert others == [], case


def test_drafts_count_void_ones_dont(books: dict[str, Any]) -> None:
    typed = draft(books, [("1", "50.00", "sales.ON.standard")])
    again = draft(books, [("1", "50.00", "sales.ON.standard")])
    with org_context(books["org"]):
        (hit,) = possible_duplicates(again)
        assert hit["id"] == str(typed.public_id)
    assert hit["status"] == "draft" and "A draft invoice" in hit["message"]
    gone = void(
        approve(draft(books, [("1", "70.00", "sales.ON.standard")]), books["owner"]), books["owner"]
    )
    later = draft(books, [("1", "70.00", "sales.ON.standard")])
    with org_context(books["org"]):
        assert [d for d in possible_duplicates(later) if d["id"] == str(gone.public_id)] == []
