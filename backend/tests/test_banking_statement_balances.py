"""F-02-T14 — capture the statement's opening and closing balance from the file (OFX
``LEDGERBAL``) and update the account's ``statement_balance`` / ``statement_balance_date``.

Acceptance: the OFX fixture sets the statement balance and date. Also: the opening balance is the
closing one minus the lines (on ``DTSTART``); a CSV running-balance column gives both, in either
line order; an older statement imported afterwards leaves a later balance alone; undo puts back
the previous import's balance; the import keeps its balances and the preview / API show them; the
change is in the account's audit trail.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest

from numo9.audit.models import AuditEvent
from numo9.banking.models import BankAccount, StatementImport
from numo9.banking.services import create_bank_account
from numo9.banking.statements.mappings import builtin, ensure_builtin_mappings
from numo9.banking.statements.service import build_preview, commit_import, undo_import
from numo9.banking.statements.source import Balance, FileStatementSource
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.statement_helpers import batch, fixture

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    return create_bank_account(org, type="chequing", display_name="Chequing")


def ofx(name: str = "sgml_chequing_cp1252.ofx", data: bytes | None = None) -> FileStatementSource:
    return FileStatementSource(data or fixture(name), name)


def test_ofx_fixture_sets_the_statement_balance_and_date(bank: BankAccount) -> None:
    source = ofx()
    balances = source.balances()
    # LEDGERBAL 1245.75 on 2026-06-30; lines -4.25, -12.50, +2500.00 since DTSTART 2026-06-01.
    assert balances.closing == Balance(Decimal("1245.75"), dt.date(2026, 6, 30))
    assert balances.opening == Balance(Decimal("-1237.50"), dt.date(2026, 6, 1))
    done = commit_import(batch(bank, "june.ofx"), source)
    assert (done.closing_balance, done.closing_balance_date) == (
        Decimal("1245.75"),
        dt.date(2026, 6, 30),
    )
    assert done.opening_balance == Decimal("-1237.50")
    bank.refresh_from_db()
    assert bank.statement_balance == Decimal("1245.75")
    assert bank.statement_balance_date == dt.date(2026, 6, 30)
    assert AuditEvent.objects.filter(
        object_type="banking.BankAccount", object_id=str(bank.public_id)
    ).exists()


def test_credit_card_and_qbo_balances() -> None:
    card = ofx("creditcard.ofx").balances()
    assert card.closing == Balance(Decimal("1245.75"), dt.date(2026, 6, 30))
    xml = ofx("xml_v220.ofx").balances()
    assert xml.closing == Balance(Decimal("3658.62"), dt.date(2026, 6, 30))
    assert ofx("empty_list.qbo").balances().opening == Balance(
        Decimal("1245.75"), dt.date(2026, 6, 1)
    )


def test_unreadable_lines_leave_the_opening_balance_unknown() -> None:
    balances = ofx("entities_checknum.ofx").balances()
    assert balances.closing is not None and balances.opening is None


def test_csv_running_balance_column(org: Organisation, bank: BankAccount) -> None:
    td = builtin(ensure_builtin_mappings(org), "td")
    assert td is not None
    data = fixture("td_chequing.csv")
    source = FileStatementSource(data, "td.csv", td.layout())
    balances = source.balances()
    assert balances.opening == Balance(Decimal("1250.00"), dt.date(2026, 6, 3))
    assert balances.closing == Balance(Decimal("2863.27"), dt.date(2026, 6, 20))
    newest_first = b"\n".join(reversed(data.strip().splitlines())) + b"\n"
    assert FileStatementSource(newest_first, "td.csv", td.layout()).balances() == balances
    preview = build_preview(bank, source)
    assert preview.balances == balances
    commit_import(batch(bank), source)
    bank.refresh_from_db()
    assert (bank.statement_balance, bank.statement_balance_date) == (
        Decimal("2863.27"),
        dt.date(2026, 6, 20),
    )


def test_no_balance_column_no_balance(org: Organisation, bank: BankAccount) -> None:
    rbc = builtin(ensure_builtin_mappings(org), "rbc")
    assert rbc is not None
    source = FileStatementSource(fixture("rbc_chequing.csv"), "rbc.csv", rbc.layout())
    assert source.balances().closing is None
    commit_import(batch(bank), source)
    bank.refresh_from_db()
    assert bank.statement_balance is None


def _june_then_may(bank: BankAccount) -> tuple[StatementImport, StatementImport]:
    june = commit_import(batch(bank, "june.ofx"), ofx())
    may_data = (
        fixture("sgml_chequing_cp1252.ofx")
        .replace(b"<BALAMT>1245.75<DTASOF>20260630", b"<BALAMT>900.00<DTASOF>20260531")
        .replace(b"202606", b"202605")
    )
    may = commit_import(batch(bank, "may.ofx"), ofx("may.ofx", may_data))
    assert may.closing_balance == Decimal("900.00")
    bank.refresh_from_db()
    assert bank.statement_balance == Decimal("1245.75")  # June is later: kept
    return june, may


def test_undo_of_an_import_that_did_not_set_the_balance_leaves_it(bank: BankAccount) -> None:
    june, may = _june_then_may(bank)
    undo_import(may)
    bank.refresh_from_db()
    assert bank.statement_balance == Decimal("1245.75")
    undo_import(june)
    bank.refresh_from_db()
    assert bank.statement_balance is None
    assert bank.statement_balance_date is None


def test_undo_restores_the_previous_imports_balance(bank: BankAccount) -> None:
    june, _may = _june_then_may(bank)
    undo_import(june)
    bank.refresh_from_db()
    assert bank.statement_balance == Decimal("900.00")
    assert bank.statement_balance_date == dt.date(2026, 5, 31)
