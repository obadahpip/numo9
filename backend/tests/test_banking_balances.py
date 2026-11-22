"""F-01-T06 — ledger balance of a bank account: accounting view, as_of, cached, busted on post.

Acceptance: the balance equals the accounting-book trial-balance balance of the linked ledger
account; ``as_of`` excludes later entries; a cached balance is recomputed after a post, a
reversal and a rolled-back post leaves it unchanged; tax-book-only lines and drafts don't count.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import transaction

from numo9.banking.balances import ledger_balance, ledger_balances
from numo9.banking.models import BankAccount
from numo9.banking.services import create_bank_account
from numo9.ledger.models import Account, Book
from numo9.ledger.services import post_journal, reverse, save_draft
from numo9.ledger.trial_balance import trial_balance
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import pay
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    return create_bank_account(org, type="chequing", display_name="TD Chequing")


@pytest.fixture
def sales(org: Organisation) -> Account:
    with org_context(org):
        return account(org, "4000", "Sales", subtype="revenue")


def _post(org: Organisation, debit: Account, credit: Account, amount: str, day: int = 15) -> object:
    with org_context(org):
        return post_journal(
            pay(debit, credit, amount, dt.date(2026, 6, day)), organisation=org, user=None
        )


def test_equals_trial_balance(org: Organisation, bank: BankAccount, sales: Account) -> None:
    _post(org, bank.gl_account, sales, "500.00")
    with org_context(org):
        rent = account(org, "5400", "Rent")
    _post(org, rent, bank.gl_account, "120.55")
    with org_context(org):
        row = next(
            r for r in trial_balance(Book.ACCOUNTING).rows if r.account_id == bank.gl_account_id
        )
    assert ledger_balance(bank) == row.debit - row.credit == D("379.45")


def test_as_of(org: Organisation, bank: BankAccount, sales: Account) -> None:
    _post(org, bank.gl_account, sales, "100.00", day=1)
    _post(org, bank.gl_account, sales, "50.00", day=20)
    assert ledger_balance(bank, dt.date(2026, 6, 10)) == D("100.00")
    assert ledger_balance(bank, dt.date(2026, 6, 20)) == D("150.00")
    assert ledger_balance(bank) == D("150.00")


def test_cache_busted_on_post_and_reversal(
    org: Organisation, bank: BankAccount, sales: Account
) -> None:
    first = _post(org, bank.gl_account, sales, "10.00")
    assert ledger_balance(bank) == D("10.00")
    assert ledger_balance(bank) == D("10.00")  # cached
    _post(org, bank.gl_account, sales, "5.00")
    assert ledger_balance(bank) == D("15.00")
    with org_context(org):
        reverse(first, user=None)  # type: ignore[arg-type]
    assert ledger_balance(bank) == D("5.00")


def test_second_read_hits_the_cache(org: Organisation, bank: BankAccount, sales: Account) -> None:
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _post(org, bank.gl_account, sales, "10.00")
    ledger_balance(bank)
    with CaptureQueriesContext(connection) as queries:
        assert ledger_balance(bank) == D("10.00")
    assert not [q for q in queries if "ledger_journalline" in q["sql"]]


def test_rolled_back_post_leaves_it(org: Organisation, bank: BankAccount, sales: Account) -> None:
    _post(org, bank.gl_account, sales, "10.00")
    assert ledger_balance(bank) == D("10.00")
    with pytest.raises(RuntimeError), transaction.atomic():
        _post(org, bank.gl_account, sales, "99.00")
        raise RuntimeError
    assert ledger_balance(bank) == D("10.00")


def test_drafts_and_tax_book_lines_do_not_count(
    org: Organisation, bank: BankAccount, sales: Account
) -> None:
    with org_context(org):
        save_draft(pay(bank.gl_account, sales, "70.00"), organisation=org, user=None)
        post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 15),
                lines=(
                    LineSpec(bank.gl_account, debit=D("3.00"), book=Book.TAX),
                    LineSpec(sales, credit=D("3.00"), book=Book.TAX),
                ),
            ),
            organisation=org,
            user=None,
        )
    assert ledger_balance(bank) == D("0.00")


def test_several_accounts(org: Organisation, bank: BankAccount, sales: Account) -> None:
    card = create_bank_account(org, type="credit_card", display_name="Visa")
    with org_context(org):
        rent = account(org, "5400", "Rent")
    _post(org, bank.gl_account, sales, "40.00")
    _post(org, rent, card.gl_account, "25.00")
    assert ledger_balances([bank, card]) == {bank.pk: D("40.00"), card.pk: D("-25.00")}
