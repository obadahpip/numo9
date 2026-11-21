"""F-01-T02 — ``BankAccount``: the banking profile of a ledger account (one-to-one), with its type
(Chequing, Savings, Credit card, Line of credit, Loan, Cash, Clearing), institution, name,
currency, encrypted and masked numbers, optional statement balance, reconciliation-tracking flag
and archive date.

Acceptance: the migration applies (with row-level security); the name is unique per organisation
(case-insensitive) — another organisation may use it; one bank account per ledger account; the
numbers are encrypted at rest, masked in Python and in the audit log; an unknown type is refused.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction

from numo9.audit.models import AuditEvent
from numo9.banking.models import BankAccount, BankAccountType
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


def bank(
    org: Organisation, code: str, name: str, kind: str = BankAccountType.CHEQUING, **fields: Any
) -> BankAccount:
    item = BankAccount(
        organisation=org,
        gl_account=account(org, code, name, subtype="bank"),
        type=kind,
        display_name=name,
        **fields,
    )
    item.save()
    return item


def test_table_has_row_level_security() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = 'banking_bankaccount'"
        )
        assert cursor.fetchone() == (True, True)


def test_name_unique_per_organisation_case_insensitive() -> None:
    maple = Organisation.objects.create(name="Maple Bakery Inc.")
    birch = Organisation.objects.create(name="Birch Garage Inc.")
    with org_context(maple):
        bank(maple, "1000", "TD Chequing")
        with pytest.raises(IntegrityError), transaction.atomic():
            bank(maple, "1001", "td chequing")
    with org_context(birch):
        assert bank(birch, "1000", "TD Chequing").pk


def test_one_bank_account_per_ledger_account() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        first = bank(org, "1000", "TD Chequing")
        with pytest.raises(IntegrityError), transaction.atomic():
            BankAccount.objects.create(
                organisation=org,
                gl_account=first.gl_account,
                type=BankAccountType.SAVINGS,
                display_name="Second profile",
            )


def test_numbers_encrypted_masked_and_not_in_the_audit_log() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        item = bank(
            org,
            "1000",
            "TD Chequing",
            institution="TD Canada Trust",
            account_last4="4821",
            transit_number="10202",
            institution_number="004",
            statement_balance=Decimal("4120.00"),
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT account_last4, transit_number FROM banking_bankaccount WHERE id = %s",
                [item.pk],
            )
            stored = cursor.fetchone()
        assert all(value.startswith("n9e1:") for value in stored)
        fresh = BankAccount.objects.get(pk=item.pk)
        assert (fresh.account_last4, fresh.masked_number) == ("4821", "•••• 4821")
        event = AuditEvent.objects.filter(object_type="banking.BankAccount").latest("pk")
    assert "4821" not in str(event.changes) and "10202" not in str(event.changes)
    assert fresh.currency == "CAD" and fresh.is_reconciled_tracking is False
    assert not fresh.is_archived


def test_unknown_type_refused() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        bank(org, "1000", "Mystery", kind="crypto_wallet")
