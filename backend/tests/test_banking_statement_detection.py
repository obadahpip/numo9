"""F-02-T06 — mapping auto-detection: header similarity scoring picks the best saved mapping;
the person's choice is saved per bank account.

Acceptance: the TD sample (no header row) auto-selects the TD mapping. Also: every bank fixture
selects its bank's mapping; a file no mapping fits gets a layout guessed from its header and is
not "chosen"; ambiguous dates list every fitting format; the bank account's own mapping wins
while it fits; a changed layout is saved as the account's own mapping (never over a built-in).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from numo9.banking.models import BankAccount, StatementMapping
from numo9.banking.services import create_bank_account
from numo9.banking.statements.layout import Role, Sign, Table, TableRow
from numo9.banking.statements.mappings import (
    MIN_SCORE,
    builtin,
    detect_mapping,
    ensure_builtin_mappings,
    guess_layout,
    header_similarity,
    remember_mapping,
)
from numo9.banking.statements.parsers import parse_statement
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
def chequing(org: Organisation) -> BankAccount:
    return create_bank_account(org, type="chequing", display_name="TD Chequing")


def table(name: str) -> Table:
    parsed = parse_statement((FIXTURES / name).read_bytes(), name)
    assert parsed.table is not None
    return parsed.table


def test_td_sample_auto_selects_the_td_mapping(org: Organisation) -> None:
    detection = detect_mapping(table("td_chequing.csv"), ensure_builtin_mappings(org))
    assert detection.mapping is not None and detection.mapping.builtin_key == "td"
    assert detection.score >= MIN_SCORE
    assert detection.candidates[1].score < detection.score
    assert detection.date_formats == ("MM/DD/YYYY",)  # 06/20/2026: never DD/MM


@pytest.mark.parametrize(
    ("fixture", "key"),
    [
        ("rbc_chequing.csv", "rbc"),
        ("td_chequing.csv", "td"),
        ("national_bank_fr_cp1252.csv", "national_bank"),
        ("bmo_preamble_bom.csv", "bmo"),
        ("tangerine_quoted.csv", "tangerine"),
        ("scotiabank.xlsx", "scotiabank"),
    ],
)
def test_each_bank_fixture_selects_its_bank(org: Organisation, fixture: str, key: str) -> None:
    detection = detect_mapping(table(fixture), ensure_builtin_mappings(org))
    assert detection.mapping is not None and detection.mapping.builtin_key == key


def test_rbc_scores_a_perfect_match(org: Organisation) -> None:
    detection = detect_mapping(table("rbc_chequing.csv"), ensure_builtin_mappings(org))
    assert detection.score == 1.0


def test_an_unknown_layout_gets_a_guess_to_check(org: Organisation) -> None:
    unknown = Table(
        (
            TableRow(1, ("Posted Date", "Payee", "Withdrawal", "Deposit", "Running Balance")),
            TableRow(2, ("03/04/2026", "TIM HORTONS", "4.25", "", "100.00")),
            TableRow(3, ("05/04/2026", "PAYROLL", "", "50.00", "150.00")),
        )
    )
    detection = detect_mapping(unknown, ensure_builtin_mappings(org))
    assert detection.mapping is None and detection.score < MIN_SCORE
    assert detection.layout.columns == (
        Role.DATE,
        Role.PAYEE,
        Role.DEBIT,
        Role.CREDIT,
        Role.BALANCE,
    )
    assert detection.layout.sign == Sign.DEBIT_CREDIT
    assert detection.date_ambiguous  # 03/04 and 05/04: DD/MM or MM/DD — the person confirms
    assert set(detection.date_formats) == {"DD/MM/YYYY", "MM/DD/YYYY"}


def test_guess_with_french_headers_and_single_amount() -> None:
    layout, formats = guess_layout(
        Table(
            (
                TableRow(1, ("Date", "Libellé", "Montant")),
                TableRow(2, ("2026-06-03", "Café", "-4,25")),
            )
        )
    )
    assert layout.columns == (Role.DATE, Role.DESCRIPTION, Role.AMOUNT)
    assert layout.sign == Sign.SIGNED and formats[0] == "YYYY-MM-DD"


def test_header_similarity_ignores_accents_case_and_spacing() -> None:
    assert header_similarity(["Débit", "Crédit"], ["DEBIT ", "credit"]) == 1.0
    assert header_similarity(["Date", "Amount"], ["Date", "Amount", "Extra"]) < 1.0
    assert header_similarity([], ["Date"]) == 0.0


def test_the_accounts_own_mapping_wins_while_it_fits(
    org: Organisation, chequing: BankAccount
) -> None:
    mappings = ensure_builtin_mappings(org)
    generic = builtin(mappings, "generic")
    assert generic is not None
    sample = Table(
        (
            TableRow(1, ("Date", "Description", "Amount")),
            TableRow(2, ("2026-06-03", "COFFEE", "-4.25")),
        )
    )
    mine = StatementMapping.objects.create(
        organisation=org,
        name="My export",
        headers=["Date", "Details", "Amount"],
        columns=["date", "description", "amount"],
    )
    plain = detect_mapping(sample, [*mappings, mine])
    assert plain.mapping is not None and plain.mapping.pk == generic.pk
    preferred = detect_mapping(sample, [*mappings, mine], preferred=mine)
    assert preferred.mapping is not None and preferred.mapping.pk == mine.pk and preferred.preferred
    rbc = builtin(mappings, "rbc")
    assert rbc is not None  # the account's RBC mapping doesn't fit this file: not used
    assert detect_mapping(sample, mappings, preferred=rbc).mapping == generic


def test_choice_is_saved_per_bank_account(org: Organisation, chequing: BankAccount) -> None:
    mappings = ensure_builtin_mappings(org)
    td = builtin(mappings, "td")
    assert td is not None
    used = remember_mapping(chequing, td.layout(), td)
    chequing.refresh_from_db()
    assert used.pk == td.pk and chequing.statement_mapping_id == td.pk
    td.refresh_from_db()
    assert td.use_count == 1 and td.last_used_at is not None

    changed = td.layout().with_columns(
        [Role.DATE, Role.DESCRIPTION, Role.DEBIT, Role.CREDIT, Role.IGNORE]
    )
    custom = remember_mapping(chequing, changed, td)
    chequing.refresh_from_db()
    td.refresh_from_db()
    assert custom.pk != td.pk and custom.name == "TD Chequing (custom)"
    assert custom.layout() == changed and not custom.is_builtin
    assert td.columns == ["date", "description", "debit", "credit", "balance"]  # untouched
    assert chequing.statement_mapping_id == custom.pk
    again = remember_mapping(chequing, changed.with_columns([*changed.columns]), None)
    assert again.pk == custom.pk  # the account keeps one custom mapping, updated
    detection = detect_mapping(table("td_chequing.csv"), [*mappings, custom], preferred=custom)
    assert detection.mapping is not None and detection.mapping.pk == custom.pk
