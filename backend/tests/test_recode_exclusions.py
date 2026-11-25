"""C-07-T03 — exclusion engine: locked / closed / filed periods, voided documents, superseded
revisions, reversals and system journals → excluded with a reason code."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.periods import ClosedPeriod, register_period_check, unregister_period_check
from numo9.ledger.recode_exclusions import reasons, split
from numo9.ledger.recode_query import find_lines
from numo9.ledger.services import post_journal, reverse
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from tests.recode_helpers import recode_books

pytestmark = pytest.mark.django_db
EVERYTHING = {
    "match": "any",
    "conditions": [{"field": "date", "op": "after", "value": "2025-12-31"}],
}


@pytest.fixture
def books() -> dict[str, Any]:
    return recode_books()


def excluded(
    books: dict[str, Any], changes: dict[str, Any] | None = None, criteria: Any = EVERYTHING
) -> dict[tuple[int, int], str]:
    index = {e.pk: n for n, e in enumerate(books["entries"], start=1)}
    with org_context(books["org"]):
        lines = find_lines(books["org"], criteria)
        _, out = split(books["org"], lines, changes or {"account": "x"}, books["adviser"])
    return {
        (index.get(x.line.entry_id, x.line.entry_id), x.line.line_no): x.reason.code for x in out
    }


def lock(books: dict[str, Any], module: str, day: dt.date) -> None:
    with org_context(books["org"]):
        LockDate(
            organisation=books["org"],
            module=module,
            level="everyone",
            date=day,
            reason="Closing the books",
        ).save()


def test_nothing_excluded_on_open_books(books: dict[str, Any]) -> None:
    assert excluded(books) == {}


def test_locked_gl_and_module_locks(books: dict[str, Any]) -> None:
    lock(books, "ar", dt.date(2026, 1, 31))  # the sales entry (type sales → AR) only
    assert excluded(books) == {(1, 1): "locked", (1, 2): "locked"}
    lock(books, "gl", dt.date(2026, 2, 28))
    found = excluded(books)
    assert found == {(1, 1): "locked", (1, 2): "locked", (2, 1): "locked", (2, 2): "locked"}
    with org_context(books["org"]):
        lines = list(find_lines(books["org"], EVERYTHING))
        reason = reasons(books["org"], lines, {}, books["adviser"])[
            (lines[2].entry_id, lines[2].line_no)
        ]
    assert (
        reason.detail == {"module": "gl", "level": "everyone", "date": "2026-02-28"}
        and "lock date" in reason.message
    )


def test_closed_period(books: dict[str, Any]) -> None:
    def march(organisation: Any, day: dt.date) -> ClosedPeriod | None:
        if organisation == books["org"] and dt.date(2026, 3, 1) <= day <= dt.date(2026, 3, 31):
            return ClosedPeriod(dt.date(2026, 3, 1), dt.date(2026, 3, 31), "March 2026")
        return None

    register_period_check(march)
    try:
        assert excluded(books) == {(3, 1): "closed_period", (3, 2): "closed_period"}
    finally:
        unregister_period_check(march)


def test_filed_period_only_for_tax_lines_or_tax_recodes(books: dict[str, Any]) -> None:
    from numo9.orgsettings.models import TaxRegistration
    from numo9.tax.filing_service import switch_frequency
    from numo9.tax.models import FilingPeriod

    org = books["org"]
    with org_context(org):
        reg = TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2026, 1, 1),
        )
        reg.save()
        switch_frequency(reg, "quarterly", dt.date(2026, 1, 1), today=dt.date(2026, 7, 15))
        FilingPeriod.objects.filter(registration=reg, end=dt.date(2026, 3, 31)).update(
            status="filed"
        )
    # an account recode: only the Q1 lines with a tax code (the sale's revenue, the supplies)
    assert excluded(books, {"account": "x"}) == {(1, 2): "filed_period", (2, 1): "filed_period"}
    # a tax recode: every Q1 line
    assert set(excluded(books, {"tax_code": "sales.ON.exempt"})) == {
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
        (3, 1),
        (3, 2),
    }


def test_reversed_superseded_and_system(books: dict[str, Any]) -> None:
    org, b = books["org"], books
    with org_context(org):
        reversal = reverse(b["entries"][3], user=b["adviser"])

        def doc(amount: str) -> Any:
            return post_journal(
                JournalSpec(
                    date=dt.date(2026, 5, 2),
                    lines=[
                        LineSpec(b["expense"], debit=Decimal(amount)),
                        LineSpec(b["bank"], credit=Decimal(amount)),
                    ],
                    source_type="purchases.bill",
                    source_id="00000000-0000-0000-0000-00000000b111",
                ),
                user=b["adviser"],
            )

        first = doc("40.00")
        undone = reverse(first, user=b["adviser"])
        current = doc("45.00")
        closing = post_journal(
            JournalSpec(
                date=dt.date(2026, 5, 3),
                journal_type="closing",
                lines=[
                    LineSpec(b["revenue"], debit=Decimal("10.00")),
                    LineSpec(b["re"], credit=Decimal("10.00")),
                ],
            ),
            user=b["adviser"],
            caller="year_end",
        )
    found = excluded(books)
    assert found[(reversal.pk, 1)] == found[(reversal.pk, 2)] == "reversed"
    assert found[(undone.pk, 1)] == "superseded_revision"
    assert found[(closing.pk, 1)] == "system_journal"
    assert (current.pk, 1) not in found and (
        4,
        1,
    ) not in found  # current revision kept; reversed original not searched
    with_reversed = {
        "match": "any",
        "conditions": [{"field": "status", "op": "in", "value": ["posted", "reversed"]}],
    }
    found = excluded(books, criteria=with_reversed)
    assert found[(4, 1)] == "reversed" and found[(first.pk, 1)] == "superseded_revision"


def test_voided_invoice() -> None:
    from numo9.sales.posting import approve, void
    from tests.journal_helpers import people
    from tests.sales_helpers import draft, sales_books

    sales = sales_books("Void Co")
    owner = people(sales["org"])["owner"]
    invoice = approve(draft(sales, [("1", "100.00", "sales.ON.standard")]), owner)
    invoice = void(invoice, owner, reason="Raised in error")
    criteria = {
        "conditions": [
            {"field": "type", "op": "in", "value": ["sales", "reversal"]},
            {"field": "status", "op": "in", "value": ["posted", "reversed"]},
        ]
    }
    with org_context(sales["org"]):
        lines = list(find_lines(sales["org"], criteria))
        included, out = split(sales["org"], lines, {"account": "x"}, owner)
    assert included == [] and len(out) == 6  # the posting and its reversal: AR, revenue, tax
    assert {x.reason.code for x in out} == {"voided_document"}
    assert invoice.number in out[0].reason.message
