"""C-06-T03 — the close checklist counts, for the month: drafts (journals, invoices, bills…),
items awaiting approval, unfiled tax periods ended by then, and exceptions (recurring journals
skipped, automatic reversals not posted); items of other months aren't counted."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.models import RecurringJournalRun, RecurringJournalTemplate
from numo9.ledger.period_close import checklist
from numo9.orgsettings.models import TaxRegistration
from numo9.purchases.models import ExpenseClaimStatus
from numo9.tax.filing_service import switch_frequency
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books
from tests.expense_helpers import add_line, make_claim

pytestmark = pytest.mark.django_db
day = dt.date
JUNE = day(2026, 6, 30)


def items(org: Any, end: dt.date = JUNE) -> dict[str, dict[str, Any]]:
    with org_context(org):
        return {item["key"]: item for item in checklist(org, end)}


def test_counts_match_the_fixture() -> None:
    books = bill_books()
    org = books["org"]
    bill(books, [("1", "100")], date=day(2026, 6, 5), supplier_invoice_no="A")
    bill(books, [("1", "100")], date=day(2026, 6, 6), supplier_invoice_no="B")
    bill(books, [("1", "100")], date=day(2026, 7, 6), supplier_invoice_no="C")  # July
    from numo9.purchases.routing import submit

    submit(
        bill(
            books,
            [("1", "100")],
            date=day(2026, 6, 7),
            supplier_invoice_no="D",
            user=books["clerk"],
        ),
        books["clerk"],
    )
    claim = make_claim(org, books["clerk"], status=ExpenseClaimStatus.DRAFT)
    add_line(
        claim, merchant="Taxi", account=books["expense"], amount=Decimal("20"), date=day(2026, 6, 9)
    )
    with org_context(org):
        reg = TaxRegistration(
            organisation=org, type="rt", number="123456782RT0001", effective_from=day(2026, 1, 1)
        )
        reg.save()
        switch_frequency(reg, "quarterly", day(2026, 1, 1), today=day(2026, 7, 1))
        template = RecurringJournalTemplate.objects.first()
    found = items(org)
    assert found["drafts"]["count"] == 3 and found["drafts"]["detail"]["bills"] == 2
    assert found["drafts"]["detail"]["expense_claims"] == 1
    assert found["awaiting_approval"]["count"] == 1
    assert found["unfiled_tax"]["count"] == 2  # Q1 and Q2 ended, not filed
    assert found["unfiled_tax"]["link"].endswith(
        f"/settings/tax/registrations/{reg.public_id}/filing"
    )
    assert found["exceptions"]["count"] == 0
    assert template is None or isinstance(template, RecurringJournalTemplate)
    assert items(org, day(2026, 7, 31))["drafts"]["detail"]["bills"] == 1


def test_exceptions_are_counted() -> None:
    from tests.period_close_helpers import close_books

    books = close_books()
    org = books["org"]
    from numo9.ledger.services import post_journal
    from numo9.ledger.validation import JournalSpec, LineSpec

    with org_context(org):
        post_journal(
            JournalSpec(
                date=day(2026, 6, 1),
                lines=[
                    LineSpec(account=books["bank"], debit=Decimal("50")),
                    LineSpec(account=books["revenue"], credit=Decimal("50")),
                ],
                narration="Accrual",
                journal_type="adjusting",
                auto_reverse_on=day(2026, 6, 2),
            ),
            user=books["adviser"],
        )
        template = RecurringJournalTemplate(
            organisation=org,
            name="Rent",
            rrule="FREQ=MONTHLY",
            start_date=day(2026, 1, 1),
            created_by=books["owner"],
        )
        template.save()
        RecurringJournalRun(
            organisation=org,
            template=template,
            occurrence_date=day(2026, 6, 15),
            template_version=1,
            status="skipped",
            code="lock.violation",
        ).save()
    found = items(org)["exceptions"]
    assert found["detail"] == {"recurring_skipped": 1, "reversals_pending": 1}
