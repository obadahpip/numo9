"""F-01-T03 — bank account type → ledger account: creating a bank account creates its ledger
account with the next free code of the type's range.

Acceptance: Chequing creates a current-asset Bank account 10xx; Credit card a current liability
21xx (each type checked); a loan is a non-current liability 27xx unless marked current (21xx);
codes already used (archived accounts too) are skipped; a full range and a name already used are
refused naming the reason; nothing is left half-created.
"""

from __future__ import annotations

import pytest

from numo9.banking.models import BankAccount, BankAccountType
from numo9.banking.services import create_bank_account, ledger_place
from numo9.ledger.models import Account, LedgerError
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
T = BankAccountType


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.mark.parametrize(
    ("kind", "code", "account_type", "subtype"),
    [
        (T.CHEQUING, "1000", "asset", "bank"),
        (T.SAVINGS, "1000", "asset", "bank"),
        (T.CASH, "1000", "asset", "bank"),
        (T.CLEARING, "1000", "asset", "bank"),
        (T.CREDIT_CARD, "2100", "liability", "current_liability"),
        (T.LINE_OF_CREDIT, "2100", "liability", "current_liability"),
        (T.LOAN, "2700", "liability", "non_current_liability"),
    ],
)
def test_each_type_creates_its_ledger_account(
    org: Organisation, kind: str, code: str, account_type: str, subtype: str
) -> None:
    bank = create_bank_account(org, type=kind, display_name=f"My {kind}", institution=" TD ")
    ledger = bank.gl_account
    assert (ledger.code, ledger.type, ledger.subtype, ledger.is_bank) == (
        code,
        account_type,
        subtype,
        True,
    )
    assert ledger.name == f"My {kind}" and bank.institution == "TD"


def test_next_free_code_skips_used_and_archived(org: Organisation) -> None:
    with org_context(org):
        account(org, "1000", "Chequing", subtype="bank")
        old = account(org, "1001", "Old cash", subtype="bank")
        old.status, old.archived_at = "archived", old.created_at
        old.save()
    assert create_bank_account(org, type=T.CHEQUING, display_name="TD").gl_account.code == "1002"
    assert create_bank_account(org, type=T.SAVINGS, display_name="EQ").gl_account.code == "1003"


def test_loan_marked_current(org: Organisation) -> None:
    assert ledger_place(T.LOAN, loan_current=True).subtype == "current_liability"
    bank = create_bank_account(org, type=T.LOAN, display_name="BDC loan", loan_current=True)
    assert (bank.gl_account.code, bank.gl_account.subtype) == ("2100", "current_liability")


def test_full_range_and_taken_name_are_refused(org: Organisation) -> None:
    with org_context(org):
        for number in range(2100, 2200):
            account(org, str(number), f"Liability {number}", subtype="current_liability")
    with pytest.raises(LedgerError) as raised:
        create_bank_account(org, type=T.CREDIT_CARD, display_name="Visa")
    assert raised.value.code == "ledger.bank.no_free_code"
    create_bank_account(org, type=T.CHEQUING, display_name="TD Chequing")
    with pytest.raises(LedgerError) as raised:
        create_bank_account(org, type=T.SAVINGS, display_name="td  chequing")
    assert raised.value.code == "banking.account.name_taken"
    with org_context(org):
        assert BankAccount.objects.count() == 1
        assert Account.objects.filter(is_bank=True).count() == 1
