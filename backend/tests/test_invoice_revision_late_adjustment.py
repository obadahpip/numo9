"""D-03b-T11 — a revision saved as a late adjustment into a filed GST/HST period: invoice 101 dated
15 Jun 2026 (June filed, confirmation GH-9) revised 1,130.00 → 1,017.00 with
``late_adjustment=True``. The June return is unchanged — as filed and when recalculated (an
amendment): line 103 stays 130.00; July, the next open period, carries the revision's journals
(the reversal on line 107, the new tax on line 104) and shows the tax difference −13.00 on its
net tax; the adjustment is linked to the revision (its journals, the audit event)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.sales.posting import approve
from numo9.sales.revise import revise
from numo9.sales.revisions import build_revision, late_adjustment_summary, late_adjustments_of
from numo9.tax import returns
from numo9.tax.models import FilingPeriod, TaxLine, TaxReturn
from numo9.tax.return_lines import regular_lines
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books
from tests.test_invoice_revision_lock_rules import file_june

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    books["invoice"] = approve(
        draft(books, [("10", "100.00", "sales.ON.standard")]), books["owner"]
    )  # 15 Jun 2026: 1,000.00 + HST 130.00
    books["june"] = file_june(books)
    with org_context(books["org"]):
        books["july"] = FilingPeriod.objects.get(
            registration=books["june"].registration, start=dt.date(2026, 7, 1)
        )
    return books


def revised(books: dict[str, Any]) -> Any:
    with org_context(books["org"]):
        books["invoice"].refresh_from_db()
        opened = build_revision(books["invoice"])
    opened.lines[0]["quantity"] = D("9")
    opened.reason = "Nine hours, not ten"
    return revise(books["invoice"], opened, books["owner"], late_adjustment=True)


def test_filed_period_unchanged_and_next_period_shows_the_delta(books: dict[str, Any]) -> None:
    june, july = books["june"], books["july"]
    with org_context(books["org"]):
        filed = TaxReturn.objects.get(period=june, status="filed")
        filed_lines = dict(filed.lines)
    assert (filed_lines["103"], filed_lines["109"]) == ("130.00", "130.00")

    revision = revised(books)
    assert (revision.total, revision.tax_total) == (D("1017.00"), D("117.00"))
    with org_context(books["org"]):
        filed.refresh_from_db()
        assert filed.lines == filed_lines  # the filed return never changes
        again = regular_lines(june)  # what an amendment of June would compute
        assert (again["103"], again["104"], again["107"]) == (D("130.00"), D("0"), D("0"))

        rows = late_adjustments_of(revision)
        assert {(r.line, r.amount) for r in rows} == {("107", D("130.00")), ("104", D("117.00"))}
        assert {r.journal_id for r in rows} == {
            revision.journal_reversal_id,
            revision.journal_post_id,
        }
        assert {(r.filed_period, r.target_period) for r in rows} == {(june, july)}
        assert TaxLine.objects.filter(
            entry_id__in=[revision.journal_reversal_id, revision.journal_post_id], late=True
        ).exists()

    (summary,) = late_adjustment_summary(revision)
    assert summary["tax_delta"] == "-13.00" and summary["reported_in_id"] == str(july.public_id)

    made = returns.prepare(july, books["owner"])
    lines = made.lines
    assert (lines["103"], lines["104"], lines["107"]) == ("0.00", "117.00", "130.00")
    assert lines["109"] == "-13.00"  # the revision's tax difference, in the next open period

    with org_context(books["org"]):
        event = AuditEvent.objects.get(action="sales.invoice.revised")
    assert event.meta["late_adjustment"] == [summary]


def test_without_tax_change_the_delta_is_zero(books: dict[str, Any]) -> None:
    """A description-only revision still reverses and re-posts (traceability): net delta 0."""
    with org_context(books["org"]):
        books["invoice"].refresh_from_db()
        opened = build_revision(books["invoice"])
    opened.lines[0]["description"] = "Consulting — June"
    opened.reason = "Clearer description"
    revision = revise(books["invoice"], opened, books["owner"], late_adjustment=True)
    (summary,) = late_adjustment_summary(revision)
    assert summary["tax_delta"] == "0.00"
