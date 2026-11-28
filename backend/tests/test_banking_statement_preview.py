"""F-02-T08 — dry-run preview: new / duplicate / error lines with reasons, without writing.

Acceptance: preview counts = later committed counts (the commit side is checked again in
F-02-T09's tests); here: the preview of a fixture against an account that already holds some of
its lines reports each line's status and reason, writes nothing (no statement line, no import, no
audit event), and inserting exactly its ``new`` lines makes a second preview all duplicates.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from numo9.audit.models import AuditEvent
from numo9.banking.models import BankAccount, StatementImport, StatementLine
from numo9.banking.services import create_bank_account
from numo9.banking.statements.mappings import builtin, ensure_builtin_mappings
from numo9.banking.statements.service import LineStatus, build_preview
from numo9.banking.statements.source import FileStatementSource
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "statements"


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    return create_bank_account(org, type="chequing", display_name="Chequing")


def insert_new(bank: BankAccount, source: FileStatementSource) -> int:
    preview = build_preview(bank, source)
    StatementLine.objects.bulk_create(
        StatementLine(
            organisation_id=bank.organisation_id,
            bank_account=bank,
            date=p.line.date or dt.date.today(),
            amount=p.line.amount or Decimal(0),
            description=p.line.description,
            fingerprint=p.fingerprint or "",
        )
        for p in preview.of(LineStatus.NEW)
    )
    return len(preview.of(LineStatus.NEW))


def tangerine(org: Organisation) -> FileStatementSource:
    mapping = builtin(ensure_builtin_mappings(org), "tangerine")
    assert mapping is not None
    data = (FIXTURES / "tangerine_quoted.csv").read_bytes()
    return FileStatementSource(data, "tangerine_quoted.csv", mapping.layout())


def test_preview_reports_each_line_and_writes_nothing(org: Organisation, bank: BankAccount) -> None:
    source = tangerine(org)
    events = AuditEvent.objects.count()
    with CaptureQueriesContext(connection) as queries:
        preview = build_preview(bank, source)
    writes = [
        q["sql"]
        for q in queries.captured_queries
        if not q["sql"].lstrip().startswith(("SELECT", "SAVEPOINT", "RELEASE"))
    ]
    assert writes == []
    assert preview.counts == {"total": 5, "new": 4, "duplicate": 0, "error": 1}
    (error,) = preview.of(LineStatus.ERROR)
    assert error.fingerprint is None
    assert error.reasons[0].message().startswith("Row 6: date '13/9/2026' doesn't match MM/DD/YYYY")
    assert StatementLine.objects.count() == 0 and StatementImport.objects.count() == 0
    assert AuditEvent.objects.count() == events
    assert preview.format == "csv" and preview.encoding == "utf-8" and preview.source_name == "file"


def test_lines_already_in_the_account_are_duplicates(org: Organisation, bank: BankAccount) -> None:
    source = tangerine(org)
    assert insert_new(bank, source) == 4
    preview = build_preview(bank, source)
    assert preview.counts == {"total": 5, "new": 0, "duplicate": 4, "error": 1}
    first = preview.of(LineStatus.DUPLICATE)[0]
    assert first.reasons[0].code == "banking.statement.row.duplicate"
    assert first.reasons[0].message().startswith("Row 2 is already in this account")


def test_preview_counts_are_what_gets_inserted(org: Organisation, bank: BankAccount) -> None:
    rbc = builtin(ensure_builtin_mappings(org), "rbc")
    assert rbc is not None
    data = (FIXTURES / "rbc_chequing.csv").read_bytes()
    full = FileStatementSource(data, "rbc.csv", rbc.layout())
    first_three = FileStatementSource(b"\n".join(data.splitlines()[:4]), "rbc.csv", rbc.layout())
    insert_new(bank, first_three)
    preview = build_preview(bank, full)
    assert preview.counts == {"total": 5, "new": 2, "duplicate": 3, "error": 0}
    assert insert_new(bank, full) == preview.counts["new"]
    assert StatementLine.objects.filter(bank_account=bank).count() == 5


def test_ofx_preview(bank: BankAccount) -> None:
    data = (FIXTURES / "entities_checknum.ofx").read_bytes()
    preview = build_preview(bank, FileStatementSource(data, "entities_checknum.ofx"))
    assert preview.counts == {"total": 3, "new": 2, "duplicate": 0, "error": 1}
    assert preview.format == "ofx"
