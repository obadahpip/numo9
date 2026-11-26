"""K-09-T10, T11 — timing rules: BACKDATED (journals, invoices, bills) and WEEKEND_POSTING.

Acceptance: journal dated 3 Jun posted 15 Jun flagged (12 days > 7), journal 2 (same day) not;
``days`` changes the outcome; a bill posted 20 days after its date is flagged as the bill (its
document), a recode re-post keeping its original date is not.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.assurance.rules.base import evaluate, registry
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, at, refined

pytestmark = pytest.mark.django_db


def test_journal_dated_3_june_posted_15_june_is_backdated() -> None:
    books = refined()
    (hit,) = evaluate(books["org"], "BACKDATED", now=NOW)
    assert (hit.subject_type, hit.subject_id) == (
        "ledger.JournalEntry",
        str(books["journal1"].public_id),
    )
    assert hit.details["gap"] == 12
    text = registry.get("BACKDATED").explain(hit.details)
    assert text.endswith(
        "is dated 3 Jun 2026 but was posted on 15 Jun 2026 (12 days later; the limit is 7)."
    )
    assert evaluate(books["org"], "BACKDATED", now=NOW, params={"days": 12}) == []


def test_bill_posted_late_is_flagged_as_the_bill() -> None:
    from numo9.purchases.bill_posting import approve
    from tests.bill_helpers import bill, bill_books

    books = bill_books()
    draft = bill(
        books,
        [("1", "250.00")],
        date=dt.date(2026, 6, 1),
        user=books["owner"],
        supplier_invoice_no="CS-1001",
    )
    with at(dt.datetime(2026, 6, 21, 15, tzinfo=dt.UTC)):
        posted = approve(draft, books["owner"])
    (hit,) = evaluate(books["org"], "BACKDATED", now=NOW)
    assert (hit.subject_type, hit.subject_id) == ("purchases.Bill", str(posted.public_id))
    assert hit.label == posted.number and hit.details["gap"] == 20


def test_recode_repost_keeps_its_date_and_is_not_backdated() -> None:
    from numo9.ledger.recode_execute import create_batch, execute

    books = refined()
    org = books["org"]
    criteria = {
        "match": "all",
        "conditions": [
            {"field": "number", "op": "is", "value": books["journal2"].number},
            {"field": "account", "op": "is", "value": str(books["accounts"]["5920"].public_id)},
        ],
    }
    with org_context(org), at(dt.datetime(2026, 9, 1, 15, tzinfo=dt.UTC)):
        batch = create_batch(
            org, criteria, {"tax_code": "purchase.ON.standard"}, None, confirm_tax=True
        )
        execute(batch, None)
    hits = evaluate(org, "BACKDATED", now=NOW)
    assert [h.subject_id for h in hits] == [str(books["journal1"].public_id)]


# ---- WEEKEND_POSTING (K-09-T11) --------------------------------------------------------------


def _post_by_person(books: dict[str, Any], when: dt.datetime) -> object:
    from tests.assurance_helpers import post
    from tests.journal_helpers import people

    staff = books.get("people") or people(books["org"])
    books["people"] = staff
    with org_context(books["org"]):
        return post(
            books["accounts"],
            when.date(),
            "Posted by a person",
            (("5920", "10.00", "0"), ("2900", "0", "10.00")),
            when=when,
            user=staff["owner"],
        )


def test_saturday_in_toronto_is_detected_not_utc() -> None:
    books = refined()
    # Saturday 20 Jun 2026 01:30 UTC = Friday 19 Jun 21:30 in Toronto: not a weekend there.
    friday = _post_by_person(books, dt.datetime(2026, 6, 20, 1, 30, tzinfo=dt.UTC))
    # Sunday 21 Jun 2026 02:30 UTC = Saturday 20 Jun 22:30 in Toronto: a weekend there.
    saturday = _post_by_person(books, dt.datetime(2026, 6, 21, 2, 30, tzinfo=dt.UTC))
    # Monday 22 Jun 2026 03:00 UTC = Sunday 21 Jun 23:00 in Toronto: a weekend there.
    sunday = _post_by_person(books, dt.datetime(2026, 6, 22, 3, 0, tzinfo=dt.UTC))
    hits = {h.subject_id: h for h in evaluate(books["org"], "WEEKEND_POSTING", now=NOW)}
    assert set(hits) == {str(saturday.public_id), str(sunday.public_id)}  # type: ignore[attr-defined]
    assert str(friday.public_id) not in hits  # type: ignore[attr-defined]
    detail = hits[str(saturday.public_id)].details  # type: ignore[attr-defined]
    assert (detail["posted_on"], detail["weekday"], detail["time"]) == (
        "2026-06-20",
        "Saturday",
        "22:30",
    )
    # the teardown journals were posted by an import (no person) on a Monday: not counted
    assert str(books["journal1"].public_id) not in hits


def test_holidays_count_when_asked() -> None:
    books = refined()
    canada_day = _post_by_person(books, dt.datetime(2026, 7, 1, 15, tzinfo=dt.UTC))  # Wednesday
    assert evaluate(books["org"], "WEEKEND_POSTING", now=NOW) == []
    (hit,) = evaluate(books["org"], "WEEKEND_POSTING", now=NOW, params={"include_holidays": True})
    assert hit.subject_id == str(canada_day.public_id)  # type: ignore[attr-defined]
    assert hit.details["holiday"]
