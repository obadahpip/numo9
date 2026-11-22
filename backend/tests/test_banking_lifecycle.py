"""F-01-T04 — delete / archive guard for bank accounts.

Acceptance: deleting an account with 1 line is refused — "has 1 transaction — archive it
instead" (409 in the API, ``banking.account.has_transactions``, count named); an account with no
transaction is deleted with its ledger account; archive is allowed with transactions and a
balance; archived accounts are hidden from pickers but stay in the ledger (reports); restore makes
them pickable again; each change is audited.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.audit.models import AuditEvent
from numo9.banking.lifecycle import (
    BankAccountInUse,
    archive_bank_account,
    delete_bank_account,
    restore_bank_account,
    transaction_count,
)
from numo9.banking.models import BankAccount, BankAccountType
from numo9.banking.services import create_bank_account
from numo9.ledger.archive import balances
from numo9.ledger.models import Account, Book
from numo9.ledger.services import post_journal, save_draft
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import pay
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    return create_bank_account(org, type=BankAccountType.CHEQUING, display_name="TD Chequing")


def _spend(org: Organisation, bank: BankAccount, amount: str = "50.00") -> None:
    with org_context(org):
        rent = Account.objects.filter(code="5400").first() or account(org, "5400", "Rent")
        post_journal(pay(rent, bank.gl_account, amount), organisation=org, user=None)


def test_delete_refused_with_one_transaction(org: Organisation, bank: BankAccount) -> None:
    _spend(org, bank)
    with pytest.raises(BankAccountInUse) as caught:
        delete_bank_account(bank)
    assert caught.value.code == "banking.account.has_transactions"
    assert caught.value.status_code == 409
    assert caught.value.params == {"name": "TD Chequing", "count": 1}
    assert str(caught.value.messages[0]) == "TD Chequing has 1 transaction — archive it instead."
    with org_context(org):
        assert BankAccount.objects.filter(pk=bank.pk, deleted_at__isnull=True).exists()


def test_count_is_plural_and_includes_drafts(org: Organisation, bank: BankAccount) -> None:
    _spend(org, bank, "10.00")
    with org_context(org):
        rent = Account.objects.get(code="5400")
        save_draft(pay(rent, bank.gl_account, "5.00"), organisation=org, user=None)
    assert transaction_count(bank) == 2
    with pytest.raises(BankAccountInUse, match="has 2 transactions"):
        delete_bank_account(bank)


def test_delete_without_transactions_removes_both(org: Organisation, bank: BankAccount) -> None:
    delete_bank_account(bank)
    with org_context(org):
        assert BankAccount._base_manager.get(pk=bank.pk).deleted_at is not None
        assert Account._base_manager.get(pk=bank.gl_account_id).deleted_at is not None
        assert not BankAccount.objects.pickable().exists()


def test_archive_allowed_with_transactions_and_kept_in_ledger(
    org: Organisation, bank: BankAccount
) -> None:
    _spend(org, bank, "113.00")
    archived = archive_bank_account(bank)
    assert archived.archived_at is not None and archived.is_archived
    with org_context(org):
        assert not BankAccount.objects.pickable().filter(pk=bank.pk).exists()
        assert BankAccount.objects.filter(pk=bank.pk).exists()  # still listed for reports
        ledger = Account.objects.get(pk=bank.gl_account_id)
    assert ledger.status == "active"  # its history and balance stay in every report
    assert balances(ledger)[Book.ACCOUNTING] == Decimal("-113.00")


def test_archive_is_idempotent_and_restore_makes_pickable(
    org: Organisation, bank: BankAccount
) -> None:
    first = archive_bank_account(bank)
    again = archive_bank_account(bank)
    assert again.archived_at == first.archived_at
    restored = restore_bank_account(bank)
    assert restored.archived_at is None
    assert restore_bank_account(bank).archived_at is None
    with org_context(org):
        assert list(BankAccount.objects.pickable()) == [restored]


def test_archive_and_restore_are_audited(org: Organisation, bank: BankAccount) -> None:
    archive_bank_account(bank)
    restore_bank_account(bank)
    with org_context(org):
        events = AuditEvent.objects.filter(
            object_type="banking.BankAccount", object_id=str(bank.public_id)
        ).order_by("pk")
        changed = [set((e.changes or {}).keys()) for e in events]
    assert sum("archived_at" in fields for fields in changed) == 2


def test_other_dates_do_not_matter(org: Organisation, bank: BankAccount) -> None:
    with org_context(org):
        rent = account(org, "5400", "Rent")
        post_journal(
            pay(rent, bank.gl_account, "1.00", dt.date(2025, 1, 2)), organisation=org, user=None
        )
    assert transaction_count(bank) == 1
