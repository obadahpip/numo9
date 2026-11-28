"""F-02-T02 — ``StatementImport`` (the batch: file, mapping, counts, status, created_by) and
``StatementLine`` (bank account, date, signed amount, description, payee, reference, FITID,
fingerprint, status, import).

Acceptance: the migration applies (with row-level security on both tables); a second line with the
same fingerprint on the same bank account raises an integrity error — the same fingerprint on
another account is fine; statuses default to pending / uncoded and unknown values are refused.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from numo9.banking.models import (
    BankAccount,
    BankAccountType,
    StatementImport,
    StatementImportStatus,
    StatementLine,
    StatementLineStatus,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


def bank(org: Organisation, code: str, name: str) -> BankAccount:
    item = BankAccount(
        organisation=org,
        gl_account=account(org, code, name, subtype="bank"),
        type=BankAccountType.CHEQUING,
        display_name=name,
    )
    item.save()
    return item


def line(
    org: Organisation, acct: BankAccount, fingerprint: str, batch: StatementImport | None = None
) -> StatementLine:
    item: StatementLine = StatementLine.objects.create(
        organisation=org,
        bank_account=acct,
        statement_import=batch,
        date=date(2026, 6, 3),
        amount=Decimal("-4.25"),
        description="TIM HORTONS #1234",
        fingerprint=fingerprint,
    )
    return item


@pytest.mark.parametrize("table", ["banking_statementimport", "banking_statementline"])
def test_tables_have_row_level_security(table: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s", [table]
        )
        assert cursor.fetchone() == (True, True)


def test_import_batch_defaults_and_lines() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        acct = bank(org, "1000", "TD Chequing")
        batch = StatementImport.objects.create(
            organisation=org,
            bank_account=acct,
            file_name="td.csv",
            file_format="csv",
            mapping={"date": 0, "amount": 2},
        )
        assert batch.status == StatementImportStatus.PENDING
        assert (batch.lines_total, batch.lines_new) == (0, 0)
        first = line(org, acct, "a" * 64, batch)
        assert first.status == StatementLineStatus.UNCODED
        assert list(batch.lines.all()) == [first]
        assert list(acct.statement_lines.all()) == [first]


def test_duplicate_fingerprint_on_same_account_raises() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        chequing = bank(org, "1000", "TD Chequing")
        savings = bank(org, "1010", "TD Savings")
        line(org, chequing, "f" * 64)
        with pytest.raises(IntegrityError), transaction.atomic():
            line(org, chequing, "f" * 64)
        # The same fingerprint on another account is a different line.
        assert line(org, savings, "f" * 64).pk


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        ("import", "status", "half-done"),
        ("line", "status", "reconciled"),
        ("line", "fingerprint", ""),
    ],
)
def test_invalid_values_refused(model: str, field: str, value: str) -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        acct = bank(org, "1000", "TD Chequing")
        with pytest.raises(IntegrityError), transaction.atomic():
            if model == "import":
                StatementImport.objects.create(
                    organisation=org, bank_account=acct, **{field: value}
                )
            else:
                item = line(org, acct, "b" * 64)
                StatementLine.objects.filter(pk=item.pk).update(**{field: value})
