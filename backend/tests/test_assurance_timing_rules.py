"""K-09-T10, T11 — timing rules: BACKDATED (journals, invoices, bills) and WEEKEND_POSTING.

Acceptance: journal dated 3 Jun posted 15 Jun flagged (12 days > 7), journal 2 (same day) not;
``days`` changes the outcome; a bill posted 20 days after its date is flagged as the bill (its
document), a recode re-post keeping its original date is not.
"""

from __future__ import annotations

import datetime as dt

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
