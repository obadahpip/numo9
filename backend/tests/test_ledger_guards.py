"""C-01-T06 — system-role guard: cannot archive/delete; type immutable; one account per role.

Acceptance: archiving a system account → an error naming the role. Also: soft, hard and bulk
deletes are refused naming the role; role, type and sub-type never change once saved; a second
account for a role is refused naming the account that has it; the role must fit the sub-type;
code and name of a system account may change; an account with transactions can't be deleted.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.ledger.models import Account, LedgerError
from numo9.ledger.postings import register_posting_probe, unregister_posting_probe
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def ar(org: Organisation) -> Account:
    return account(org, "1100", "Accounts receivable", "current_asset", system_role="ar")


def test_archive_system_account_names_the_role(ar: Account) -> None:
    ar.status = "archived"
    with pytest.raises(LedgerError) as error:
        ar.save()
    assert error.value.code == "ledger.account.system_archive"
    message = error.value.messages[0]
    assert "Accounts receivable account" in message and "can't be archived" in message
    ar.refresh_from_db()
    assert ar.status == "active"


def test_delete_soft_hard_and_bulk_refused(ar: Account) -> None:
    for attempt in (ar.soft_delete, ar.delete, Account.objects.filter(pk=ar.pk).delete):
        with pytest.raises(LedgerError) as error:
            attempt()
        assert error.value.code == "ledger.account.system_delete"
        assert "Accounts receivable" in error.value.messages[0]
    ar.deleted_at = ar.created_at
    with pytest.raises(LedgerError):
        ar.save()  # a soft delete through save() too
    assert Account._base_manager.filter(pk=ar.pk, deleted_at__isnull=True).exists()


def test_role_type_and_subtype_locked(ar: Account) -> None:
    ar.refresh_from_db()
    ar.system_role = ""
    with pytest.raises(LedgerError) as error:
        ar.save()
    assert error.value.code == "ledger.account.system_role_locked"
    ar.refresh_from_db()
    ar.system_role = "itc_receivable"  # same sub-type, different role
    with pytest.raises(LedgerError) as error:
        ar.save()
    assert error.value.code == "ledger.account.system_role_locked"
    ar.refresh_from_db()
    ar.subtype = "prepayment"
    with pytest.raises(LedgerError) as error:
        ar.save()
    assert error.value.code in {
        "ledger.account.system_role_subtype",
        "ledger.account.system_type_locked",
    }


def test_code_and_name_of_a_system_account_may_change(ar: Account) -> None:
    ar.code = "1105"
    ar.set_name("Trade receivables")
    ar.save()
    ar.refresh_from_db()
    assert (ar.code, ar.name) == ("1105", "Trade receivables")


def test_one_account_per_role_names_the_holder(org: Organisation, ar: Account) -> None:
    with pytest.raises(LedgerError) as error:
        account(org, "1101", "Second AR", "current_asset", system_role="ar")
    assert error.value.code == "ledger.account.system_role_taken"
    assert "1100 · Accounts receivable" in error.value.messages[0]


def test_role_must_fit_the_subtype(org: Organisation) -> None:
    with pytest.raises(LedgerError) as error:
        account(org, "2100", "GST/HST payable", "current_liability", system_role="gst_hst_payable")
    assert error.value.code == "ledger.account.system_role_subtype"
    assert "Sales tax control" in error.value.messages[0]


def test_ordinary_accounts_archive_and_delete(org: Organisation) -> None:
    office = account(org, "6080", "Office supplies")
    office.status = "archived"
    office.save()
    assert office.archived_at is not None
    office.status = "active"
    office.save()
    assert office.archived_at is None
    office.soft_delete()
    assert office.is_deleted


def test_account_with_transactions_cannot_be_deleted(org: Organisation) -> None:
    rent = account(org, "6130", "Rent")

    def probe(item: Account) -> bool:
        return item.pk == rent.pk

    register_posting_probe(probe)
    try:
        for attempt in (rent.soft_delete, rent.delete, Account.objects.filter(pk=rent.pk).delete):
            with pytest.raises(LedgerError) as error:
                attempt()
            assert error.value.code == "ledger.account.delete_has_postings"
    finally:
        unregister_posting_probe(probe)
