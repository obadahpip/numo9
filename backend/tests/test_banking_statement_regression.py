"""F-02-T16 — regression suite: idempotent re-import, overlapping ranges, BOM, accents, empty file.

Acceptance: all fixtures green — each of the 25 statement fixtures (5 per format) imports, and
importing it again adds 0 lines; two statements overlapping by whole days add exactly the missing
lines (the two identical coffees of the shared day included, once); a byte-order mark or another
encoding of the same file is the same file (0 new lines); French accents survive Windows-1252 and
are stored as written; an empty file is refused with what to do, and a statement with no lines
imports nothing (its balance is still captured).
"""

from __future__ import annotations

import codecs
import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from numo9.accounts.models import User
from numo9.banking.models import BankAccount, StatementImportStatus, StatementLine
from numo9.banking.services import create_bank_account
from numo9.banking.statements.errors import StatementError
from numo9.banking.statements.layout import Layout
from numo9.banking.statements.mappings import builtin, ensure_builtin_mappings
from numo9.banking.statements.parsers import parse_statement
from numo9.banking.statements.service import commit_import
from numo9.banking.statements.source import FileStatementSource
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.statement_helpers import FIXTURES, batch, fixture

pytestmark = pytest.mark.django_db

EXPECTED: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    return create_bank_account(org, type="chequing", display_name="Chequing")


def source(name: str, data: bytes | None = None) -> FileStatementSource:
    expected = EXPECTED[name]
    layout = Layout.from_dict(expected["layout"]) if "layout" in expected else None
    return FileStatementSource(data if data is not None else fixture(name), name, layout)


def imported(bank: BankAccount, name: str, data: bytes | None = None) -> Any:
    return commit_import(batch(bank, name), source(name, data), skip_errors=True)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_fixture_imports_once_and_reimports_as_nothing(bank: BankAccount, name: str) -> None:
    readable = [line for line in EXPECTED[name]["lines"] if not line["problems"]]
    first = imported(bank, name)
    assert first.status == StatementImportStatus.COMMITTED
    assert first.lines_new == len(readable)
    assert first.lines_error == len(EXPECTED[name]["lines"]) - len(readable)
    again = imported(bank, name)
    assert (again.lines_new, again.lines_duplicate) == (0, len(readable))
    assert StatementLine.objects.filter(bank_account=bank).count() == len(readable)


def test_overlapping_statements_add_exactly_the_missing_lines(
    org: Organisation, bank: BankAccount
) -> None:
    rbc = builtin(ensure_builtin_mappings(org), "rbc")
    assert rbc is not None
    header, *rows = fixture("rbc_chequing.csv").strip().splitlines()
    # Statement A: June 3 (two identical coffees) and June 5; B: June 3 to June 15.
    early = b"\n".join([header, *rows[:3]])
    late = b"\n".join([header, *rows[:5]])
    a = commit_import(batch(bank), FileStatementSource(early, "a.csv", rbc.layout()))
    b = commit_import(batch(bank), FileStatementSource(late, "b.csv", rbc.layout()))
    assert (a.lines_new, b.lines_new, b.lines_duplicate) == (3, 2, 3)
    coffees = StatementLine.objects.filter(bank_account=bank, amount=Decimal("-4.25"))
    assert coffees.count() == 2
    # A third statement that starts on June 10 overlaps by whole days too: nothing new.
    tail = b"\n".join([header, *rows[3:5]])
    c = commit_import(batch(bank), FileStatementSource(tail, "c.csv", rbc.layout()))
    assert (c.lines_new, c.lines_duplicate) == (0, 2)
    assert StatementLine.objects.filter(bank_account=bank).count() == 5


def test_overlapping_ofx_statements(bank: BankAccount) -> None:
    imported(bank, "td_web.qfx")  # two coffees and a payroll, distinct FITIDs
    again = imported(bank, "intuit_header.qbo")  # the first coffee and the payroll again
    assert (again.lines_new, again.lines_duplicate) == (0, 2)


@pytest.mark.parametrize(
    "variant",
    [
        lambda data: codecs.BOM_UTF8 + data,
        lambda data: data.replace(b"\n", b"\r\n"),
        lambda data: data.decode("utf-8").encode("utf-16"),
    ],
    ids=["utf-8-bom", "crlf", "utf-16"],
)
def test_a_bom_or_another_encoding_is_the_same_file(bank: BankAccount, variant: Any) -> None:
    data = fixture("rbc_chequing.csv")
    imported(bank, "rbc_chequing.csv")
    other = variant(data)
    assert parse_statement(other, "rbc.csv").table is not None
    again = imported(bank, "rbc_chequing.csv", other)
    assert (again.lines_new, again.lines_duplicate) == (0, 5)


def test_accents_survive_windows_1252_and_match_utf_8(bank: BankAccount) -> None:
    cp1252 = fixture("national_bank_fr_cp1252.csv")
    first = imported(bank, "national_bank_fr_cp1252.csv")
    assert first.lines_new == 3
    stored = set(
        StatementLine.objects.filter(bank_account=bank).values_list("description", flat=True)
    )
    assert stored == {"Café Dépôt Montréal", "Dépôt de paie", "Épicerie Métro"}
    utf8 = cp1252.decode("cp1252").encode("utf-8")
    again = imported(bank, "national_bank_fr_cp1252.csv", utf8)
    assert (again.lines_new, again.lines_duplicate) == (0, 3)
    unaccented = utf8.decode("utf-8").replace("é", "e").replace("ô", "o").replace("É", "E")
    plain = imported(bank, "national_bank_fr_cp1252.csv", unaccented.encode("ascii"))
    assert plain.lines_new == 0  # "CAFE DEPOT MONTREAL" is the same line


@pytest.mark.parametrize("data", [b"", b"   \r\n\r\n", codecs.BOM_UTF8, codecs.BOM_UTF8 + b"\n\n"])
def test_an_empty_file_is_refused_with_what_to_do(data: bytes) -> None:
    with pytest.raises(StatementError) as refused:
        parse_statement(data, "empty.csv")
    assert refused.value.code == "banking.statement.file.empty"
    assert "Download the statement again" in refused.value.text


def test_a_header_only_file_and_an_empty_statement_import_nothing(
    org: Organisation, bank: BankAccount
) -> None:
    generic = builtin(ensure_builtin_mappings(org), "generic")
    assert generic is not None
    header_only = FileStatementSource(b"Date,Description,Amount\n", "h.csv", generic.layout())
    done = commit_import(batch(bank), header_only)
    assert (done.status, done.lines_total, done.lines_new) == (
        StatementImportStatus.COMMITTED,
        0,
        0,
    )
    empty = imported(bank, "empty_list.qbo")
    assert (empty.lines_total, empty.lines_new) == (0, 0)
    bank.refresh_from_db()
    assert bank.statement_balance == Decimal("1245.75")  # the balance is still captured


def test_an_empty_upload_is_refused_by_the_api(org: Organisation, bank: BankAccount) -> None:
    user = User.objects.create_user("dana@maple.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    client = Client()
    client.force_login(user)
    refused = client.post(
        f"/api/v1/o/{org.public_id}/bank-accounts/{bank.public_id}/imports",
        {"file": SimpleUploadedFile("empty.csv", b"")},
    )
    assert refused.status_code == 400
    assert StatementLine.objects.count() == 0


def test_fixtures_directory_is_complete() -> None:
    names = {p.name for p in Path(FIXTURES).iterdir() if p.is_file() and p.suffix != ".py"}
    assert set(EXPECTED) | {"expected.json"} == names
