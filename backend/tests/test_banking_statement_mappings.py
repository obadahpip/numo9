"""F-02-T05 — ``StatementMapping`` model and the built-in mappings of 9 Canadian banks plus a
generic layout (column roles, date format, sign convention, skip rows).

Acceptance: the seeds load (ten mappings, each a valid layout, seeded once per organisation, in a
table with row-level security); the RBC fixture maps with the RBC seed with 0 manual changes —
its header row is the seed's and the seed reads every line as expected. The other banks' fixtures
read with their seeds too.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import translation

from numo9.banking.models import StatementMapping
from numo9.banking.statements.mappings import (
    BUILTIN,
    builtin,
    display_name,
    ensure_builtin_mappings,
)
from numo9.banking.statements.source import FileStatementSource
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.test_banking_statement_parsers import as_json

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "statements"
EXPECTED: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
BANKS = {
    "rbc": "RBC Royal Bank",
    "td": "TD Canada Trust",
    "scotiabank": "Scotiabank",
    "bmo": "BMO Bank of Montreal",
    "cibc": "CIBC",
    "desjardins": "Desjardins",
    "national_bank": "National Bank",
    "tangerine": "Tangerine",
    "credit_union": "Credit union (generic)",
    "generic": "Generic (date, description, amount)",
}


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def test_table_has_row_level_security() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["banking_statementmapping"],
        )
        assert cursor.fetchone() == (True, True)


def test_seeds_load_once(org: Organisation) -> None:
    mappings = ensure_builtin_mappings(org)
    assert {m.builtin_key: m.name for m in mappings} == BANKS
    assert len(BUILTIN) == 10
    for mapping in mappings:
        layout = mapping.layout()  # every seed is a valid layout
        assert layout.columns and layout.date_format
        assert mapping.has_header == bool(mapping.headers)
    assert len(ensure_builtin_mappings(org)) == 10  # idempotent
    assert StatementMapping.objects.count() == 10


def test_seeds_are_per_organisation_and_not_audited(org: Organisation) -> None:
    from numo9.audit.models import AuditEvent

    ensure_builtin_mappings(org)
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        assert StatementMapping.objects.count() == 0
        ensure_builtin_mappings(other)
        assert StatementMapping.objects.count() == 10
    assert not AuditEvent.objects.filter(object_type="banking.StatementMapping").exists()


def test_seed_names_stay_english_and_display_translated(org: Organisation) -> None:
    with translation.override("fr-ca"):
        mappings = ensure_builtin_mappings(org)
        generic = builtin(mappings, "credit_union")
        assert generic is not None and generic.name == "Credit union (generic)"
        assert display_name(generic) == "Caisse populaire / coopérative de crédit (générique)"
        rbc = builtin(mappings, "rbc")
        assert rbc is not None and display_name(rbc) == "RBC Royal Bank"


def test_an_own_mapping_with_a_seed_name_is_kept(org: Organisation) -> None:
    StatementMapping.objects.create(organisation=org, name="TD Canada Trust", columns=["date"])
    keys = {m.builtin_key: m.name for m in ensure_builtin_mappings(org)}
    assert keys["td"] == "TD Canada Trust (Numo9)"


def test_names_are_unique_per_organisation(org: Organisation) -> None:
    StatementMapping.objects.create(organisation=org, name="My bank", columns=["date"])
    with pytest.raises(IntegrityError), transaction.atomic():
        StatementMapping.objects.create(organisation=org, name="MY BANK", columns=["date"])


def test_rbc_fixture_maps_with_zero_manual_changes(org: Organisation) -> None:
    rbc = builtin(ensure_builtin_mappings(org), "rbc")
    assert rbc is not None
    data = (FIXTURES / "rbc_chequing.csv").read_bytes()
    source = FileStatementSource(data, "rbc_chequing.csv", rbc.layout())
    assert source.parsed.table is not None
    assert list(source.parsed.table.rows[0].cells) == rbc.headers
    assert [as_json(line) for line in source.fetch_lines()] == EXPECTED["rbc_chequing.csv"]["lines"]


@pytest.mark.parametrize(
    ("key", "fixture"),
    [
        ("td", "td_chequing.csv"),
        ("national_bank", "national_bank_fr_cp1252.csv"),
        ("bmo", "bmo_preamble_bom.csv"),
        ("tangerine", "tangerine_quoted.csv"),
        ("scotiabank", "scotiabank.xlsx"),
    ],
)
def test_bank_fixtures_read_with_their_seed(org: Organisation, key: str, fixture: str) -> None:
    mapping = builtin(ensure_builtin_mappings(org), key)
    assert mapping is not None
    source = FileStatementSource((FIXTURES / fixture).read_bytes(), fixture, mapping.layout())
    assert [as_json(line) for line in source.fetch_lines()] == EXPECTED[fixture]["lines"]
