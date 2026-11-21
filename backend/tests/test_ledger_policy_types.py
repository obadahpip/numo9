"""C-03-T03 — ``JournalPolicy`` type rules: a tax adjustment posts every line to the tax book and
never touches a bank account; system types (Closing, Payroll, Depreciation) only from their own
process.

Acceptance: a tax adjustment with a bank line raises ``JournalRuleError`` naming the line (and a
both-books line too, each problem listed); a tax-book-only tax adjustment posts; Closing posts only
from the year-end caller; drafts keep any type (the rules apply when posting).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.ledger.models import JournalCategory, JournalStatus
from numo9.ledger.policy import JournalRuleError
from numo9.ledger.services import post_entry, post_journal, save_draft
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        account(organisation, "1000", "Chequing", subtype="bank")
        account(organisation, "1500", "Equipment", subtype="fixed_asset")
        account(organisation, "1550", "Accumulated CCA", subtype="accumulated_amortisation")
        account(organisation, "5400", "Rent")
    return organisation


def lines(org: Organisation, debit: str, credit: str, book: str = "tax") -> tuple[LineSpec, ...]:
    from numo9.ledger.models import Account

    with org_context(org):
        d, c = Account.objects.get(code=debit), Account.objects.get(code=credit)
    return (
        LineSpec(d, debit=Decimal("417.22"), book=book),
        LineSpec(c, credit=Decimal("417.22"), book=book),
    )


def codes(error: JournalRuleError) -> list[str]:
    return [e.code for e in error.error_list]  # type: ignore[misc]


def test_tax_adjustment_with_a_bank_line_names_the_line(org: Organisation) -> None:
    with org_context(org), pytest.raises(JournalRuleError) as raised:
        post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 15),
                lines=lines(org, "5400", "1000"),
                journal_type=JournalCategory.TAX_ADJUSTMENT,
            )
        )
    assert codes(raised.value) == ["ledger.journal.tax_adjustment_bank"]
    assert raised.value.messages[0].startswith("Line 2 (1000")


def test_tax_adjustment_in_both_books_lists_every_line(org: Organisation) -> None:
    with org_context(org), pytest.raises(JournalRuleError) as raised:
        post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 15),
                lines=lines(org, "5400", "1550", book="both"),
                journal_type=JournalCategory.TAX_ADJUSTMENT,
            )
        )
    assert codes(raised.value) == ["ledger.journal.tax_adjustment_book"] * 2


def test_tax_book_tax_adjustment_posts(org: Organisation) -> None:
    with org_context(org):
        entry = post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 15),
                lines=lines(org, "5400", "1550"),
                journal_type=JournalCategory.TAX_ADJUSTMENT,
            )
        )
    assert (entry.status, entry.book_scope) == (JournalStatus.POSTED, "tax")


@pytest.mark.parametrize(
    ("journal_type", "caller"),
    [("closing", "year_end"), ("payroll", "payroll"), ("depreciation", "depreciation")],
)
def test_system_types_only_from_their_process(
    org: Organisation, journal_type: str, caller: str
) -> None:
    spec = JournalSpec(
        date=dt.date(2026, 6, 15),
        lines=lines(org, "5400", "1550", book="both"),
        journal_type=journal_type,
    )
    with org_context(org):
        with pytest.raises(JournalRuleError) as raised:
            post_journal(spec)
        assert codes(raised.value) == ["ledger.journal.system_type"]
        draft = save_draft(spec)  # a draft may hold it; posting by hand may not
        with pytest.raises(JournalRuleError):
            post_entry(draft)
        assert post_journal(spec, caller=caller).status == JournalStatus.POSTED
        assert post_entry(draft, caller=caller).status == JournalStatus.POSTED
