"""F-06-T02 — ``BankTransfer`` (from account, to account, date, amount, reference, journal) and
its validators.

Acceptance: the same from/to account is rejected (by ``clean()`` with
``banking.transfer.same_account`` and by the database constraint). Also: the amount must be above
zero with at most 2 decimals; archived accounts are refused; accounts in different currencies get
the "deferred to multi-currency (R-02)" message; any two active same-currency accounts (chequing →
cash, chequing → card) are accepted; the table is organisation-scoped.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.banking.lifecycle import archive_bank_account
from numo9.banking.models import BankAccount, BankTransfer
from numo9.banking.services import create_bank_account
from numo9.banking.transfers import check_transfer
from numo9.ledger.models import LedgerError
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
DAY = dt.date(2026, 6, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


@pytest.fixture
def banks(org: Organisation) -> dict[str, BankAccount]:
    return {
        "chequing": create_bank_account(org, type="chequing", display_name="TD Chequing"),
        "petty": create_bank_account(org, type="cash", display_name="Petty Cash Float"),
        "visa": create_bank_account(org, type="credit_card", display_name="TD Visa"),
    }


def _transfer(org: Organisation, source: BankAccount, target: BankAccount, amount: str) -> Any:
    return BankTransfer(
        organisation=org,
        from_account=source,
        to_account=target,
        date=DAY,
        amount=Decimal(amount),
        reference="Float top-up",
    )


def _code(error: pytest.ExceptionInfo[LedgerError]) -> str | None:
    return error.value.error_list[0].code


def test_same_from_and_to_is_rejected(org: Organisation, banks: dict[str, BankAccount]) -> None:
    with org_context(org):
        transfer = _transfer(org, banks["chequing"], banks["chequing"], "100.00")
        with pytest.raises(LedgerError) as raised:
            transfer.clean()
        assert _code(raised) == "banking.transfer.same_account"


def test_database_refuses_same_account_and_non_positive(
    org: Organisation, banks: dict[str, BankAccount]
) -> None:
    with org_context(org):
        for source, target, amount in [
            (banks["chequing"], banks["chequing"], "10.00"),
            (banks["chequing"], banks["petty"], "0.00"),
        ]:
            with pytest.raises(IntegrityError), transaction.atomic():
                _transfer(org, source, target, amount).save()


@pytest.mark.parametrize(
    ("amount", "code"),
    [
        ("0", "banking.transfer.amount_positive"),
        ("-5.00", "banking.transfer.amount_positive"),
        ("10.005", "banking.amount.precision"),
    ],
)
def test_amount_must_be_positive_with_cents(
    banks: dict[str, BankAccount], amount: str, code: str
) -> None:
    with pytest.raises(LedgerError) as raised:
        check_transfer(banks["chequing"], banks["petty"], amount)
    assert _code(raised) == code


def test_missing_account(banks: dict[str, BankAccount]) -> None:
    with pytest.raises(LedgerError) as raised:
        check_transfer(banks["chequing"], None, "10.00")
    assert _code(raised) == "banking.transfer.account_required"


def test_archived_account_is_refused(org: Organisation, banks: dict[str, BankAccount]) -> None:
    archive_bank_account(banks["petty"])
    banks["petty"].refresh_from_db()
    with pytest.raises(LedgerError) as raised:
        check_transfer(banks["chequing"], banks["petty"], "10.00")
    assert _code(raised) == "banking.account.archived"


def test_cross_currency_is_deferred_to_r02(org: Organisation) -> None:
    cad = create_bank_account(org, type="chequing", display_name="RBC CAD")
    usd = create_bank_account(org, type="chequing", display_name="RBC USD", currency="USD")
    with pytest.raises(LedgerError) as raised:
        check_transfer(cad, usd, "50.00")
    assert _code(raised) == "banking.transfer.cross_currency"
    message = raised.value.messages[0]
    assert "RBC CAD is in CAD and RBC USD in USD" in message
    assert "R-02" in message


def test_valid_pairs_pass_and_save(org: Organisation, banks: dict[str, BankAccount]) -> None:
    assert check_transfer(banks["chequing"], banks["petty"], "1000") == Decimal("1000.00")
    assert check_transfer(banks["chequing"], banks["visa"], 250.5) == Decimal("250.50")
    with org_context(org):
        transfer = _transfer(org, banks["chequing"], banks["petty"], "1000.00")
        transfer.clean()
        transfer.save()
        assert BankTransfer.objects.get().status == "posted"
    other = Organisation.objects.create(name="Other Co.")
    with org_context(other):
        assert not BankTransfer.objects.exists()
