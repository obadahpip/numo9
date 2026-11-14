"""C-01-T04 — GIFI master table seeded from the CRA list (version-dated).

Acceptance: the seed loads; lookup by code. Also: the list is RC4088(E) Rev. 23 with its date on
every row, codes are 4 digits and unique, sections follow the CRA ranges, totals are flagged,
the seed after a flush fills missing rows only, and the GIFI picker search works by number and
by words of the description, limited to codes that fit the account type.
"""

from __future__ import annotations

import csv
from datetime import date

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction

from numo9.ledger import gifi
from numo9.ledger.models import GifiCode, GifiSection

pytestmark = pytest.mark.django_db


def test_seed_loads_the_whole_published_list() -> None:
    assert GifiCode.objects.count() == len(gifi.published_rows()) == 766
    versions = set(GifiCode.objects.values_list("list_version", "published_on"))
    assert versions == {("RC4088(E) Rev. 23", date(2023, 8, 23))}


def test_lookup_by_code() -> None:
    cash = gifi.lookup("1001")
    assert cash is not None and cash.description == "Cash"
    assert cash.section == GifiSection.CURRENT_ASSETS
    assert gifi.lookup("8523").description == "Meals and entertainment"
    assert gifi.lookup(" 2680 ").description == "Taxes payable"
    assert gifi.lookup("0001") is None  # identification lines are not codes
    assert gifi.lookup("1234") is None


def test_data_file_is_well_formed() -> None:
    with gifi.DATA.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    codes = [row["code"] for row in rows]
    assert len(codes) == len(set(codes))
    assert all(len(code) == 4 and code.isdigit() for code in codes)
    assert codes == sorted(codes)
    assert {row["section"] for row in rows} <= set(GifiSection.values)
    assert all(row["description"].strip() for row in rows)


@pytest.mark.parametrize(
    ("code", "section"),
    [
        ("1000", "current_assets"),
        ("1599", "current_assets"),
        ("1774", "tangible_capital_assets"),
        ("2012", "intangible_capital_assets"),
        ("2300", "long_term_assets"),
        ("2621", "current_liabilities"),
        ("3141", "long_term_liabilities"),
        ("3500", "shareholder_equity"),
        ("3560", "partners_capital"),
        ("3700", "retained_earnings"),
        ("7000", "other_comprehensive_income"),
        ("8000", "revenue"),
        ("8320", "cost_of_sales"),
        ("8811", "operating_expenses"),
        ("9371", "farm_revenue"),
        ("9662", "farm_expenses"),
        ("9990", "extraordinary_items_and_taxes"),
    ],
)
def test_sections_follow_cra_ranges(code: str, section: str) -> None:
    assert GifiCode.objects.get(code=code).section == section


def test_totals_are_flagged_and_not_assignable() -> None:
    for code in ("1599", "2599", "3499", "3620", "8299", "9367", "9368", "9999"):
        row = GifiCode.objects.get(code=code)
        assert row.is_summary and not row.is_assignable, code
    assert GifiCode.objects.get(code="8811").is_assignable


def test_code_is_unique_and_four_digits_in_the_database() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        GifiCode.objects.create(
            code="1001",
            description="x",
            section="current_assets",
            list_version="t",
            published_on=date(2026, 1, 1),
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        GifiCode.objects.create(
            code="12A4",
            description="x",
            section="current_assets",
            list_version="t",
            published_on=date(2026, 1, 1),
        )


def test_reseed_fills_missing_rows_and_keeps_existing() -> None:
    GifiCode.objects.filter(code="8811").update(description="Edited by a later list")
    GifiCode.objects.filter(code="8523").delete()
    assert gifi.seed_gifi(apps) == 1
    assert GifiCode.objects.get(code="8523").description == "Meals and entertainment"
    assert GifiCode.objects.get(code="8811").description == "Edited by a later list"
    assert gifi.seed_gifi(apps) == 0


def test_search_by_number_and_description_for_a_type() -> None:
    by_number = [row.code for row in gifi.search("881")]
    assert by_number == ["8810", "8811", "8812", "8813"]
    by_words = [row.code for row in gifi.search("accumulated computer")]
    assert by_words == ["1775"]
    expense_only = gifi.search("interest", account_type="expense")
    assert expense_only and all(
        row.section
        in {
            "operating_expenses",
            "cost_of_sales",
            "farm_expenses",
            "extraordinary_items_and_taxes",
            "other_comprehensive_income",
        }
        for row in expense_only
    )
    assert "8094" not in {row.code for row in expense_only}  # interest income: revenue
    assert all(not row.is_summary for row in gifi.search("total"))
    assert len(gifi.search("", limit=5)) == 5
