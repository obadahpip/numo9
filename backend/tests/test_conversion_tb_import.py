"""C-05-T08 — trial balance import (CSV/XLSX) with column mapping and a dry-run report.

Acceptance: mapping problems are listed per row (unknown account, both sides, not an amount,
duplicate, an account with sub-accounts); a dry run writes nothing; a real run writes all rows or
none; a signed Balance column and Debit/Credit columns both work; XLSX reads like CSV.
"""

from __future__ import annotations

import datetime as dt
import io
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from openpyxl import Workbook

from numo9.conversion.models import ConversionLine
from numo9.conversion.services import start_conversion
from numo9.conversion.tb_import import import_tb, parse_amount, suggest_mapping
from numo9.ledger.models import Account
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart

pytestmark = pytest.mark.django_db

GOOD = b"""Account Code,Account Name,Debit,Credit
1000,Chequing,"12,450.30",
1200,Accounts receivable,3390.00,
4000,Sales,,"15,840.30"
,Total,"15,840.30","15,840.30"
"""

BAD = b"""Account Code,Account Name,Debit,Credit
1000,Chequing,12450.30,
9999,Mystery,10.00,
1200,Accounts receivable,5.00,5.00
4000,Sales,,abc
1000,Chequing again,1.00,
5400,Rent,0.00,
"""


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
    return {
        "org": org,
        "session": start_conversion(org, dt.date(2026, 4, 1), user=None),
        **accounts,
    }


def lines(books: dict[str, Any]) -> list[tuple[str, Decimal, Decimal]]:
    with org_context(books["org"]):
        return [
            (line.account.code, line.debit, line.credit)
            for line in ConversionLine.objects.filter(session=books["session"]).select_related(
                "account"
            )
        ]


MAPPING = {"account": "Account Code", "debit": "Debit", "credit": "Credit"}


def test_suggested_mapping() -> None:
    suggested = suggest_mapping(GOOD, "tb.csv")
    assert suggested["mapping"] == MAPPING
    assert suggested["columns"][0] == {"name": "Account Code", "samples": ["1000", "1200", "4000"]}


def test_dry_run_reports_and_writes_nothing_then_the_real_run_writes(books: dict[str, Any]) -> None:
    report = import_tb(books["session"], GOOD, "tb.csv", MAPPING, dry_run=True)
    assert report["counts"] == {"ok": 3, "errors": 0, "skipped": 1}
    assert report["totals"] == {"debit": "15840.30", "credit": "15840.30", "difference": "0.00"}
    assert report["rows"][0]["account"]["code"] == "1000" and report["written"] == 0
    assert lines(books) == []
    done = import_tb(books["session"], GOOD, "tb.csv", MAPPING, dry_run=False)
    assert done["written"] == 3
    assert sorted(lines(books)) == [
        ("1000", Decimal("12450.30"), Decimal("0.00")),
        ("1200", Decimal("3390.00"), Decimal("0.00")),
        ("4000", Decimal("0.00"), Decimal("15840.30")),
    ]


def test_problems_are_listed_per_row_and_nothing_is_written(books: dict[str, Any]) -> None:
    report = import_tb(books["session"], BAD, "tb.csv", MAPPING, dry_run=False)
    by_row = {r["row"]: r for r in report["rows"]}
    codes = {row: [e["code"] for e in r["errors"]] for row, r in by_row.items()}
    assert codes[2] == []
    assert codes[3] == ["conversion.import.account_unknown"]
    assert codes[4] == ["conversion.import.both_sides"]
    assert codes[5] == ["conversion.import.amount"]
    assert codes[6] == ["conversion.import.duplicate"]
    assert "row 2" in by_row[6]["errors"][0]["message"]
    assert by_row[7]["status"] == "skipped"  # a zero balance
    assert report["counts"] == {"ok": 1, "errors": 4, "skipped": 1}
    assert report["refused"] is True and report["written"] == 0
    assert lines(books) == []


def test_balance_column_names_and_parents(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        parent = Account(
            organisation=books["org"],
            code="1090",
            name_i18n={"en-ca": "Cash"},
            type="asset",
            subtype="bank",
        )
        parent.save()
        books["petty"].parent = parent
        books["petty"].save()
    data = b"Account,Balance\nChequing,1250.00\nSales,(1250.00)\n1090,10.00\n"
    report = import_tb(
        books["session"], data, "tb.csv", {"account": "Account", "balance": "Balance"}
    )
    rows = report["rows"]
    assert (rows[0]["account"]["code"], rows[0]["debit"]) == ("1000", "1250.00")
    assert (rows[1]["account"]["code"], rows[1]["credit"]) == ("4000", "1250.00")
    assert rows[2]["errors"][0]["code"] == "conversion.import.account_not_postable"


def test_xlsx_reads_like_csv(books: dict[str, Any]) -> None:
    book = Workbook()
    sheet = book.active
    for row in (("Code", "Dr", "Cr"), ("1000", 500, None), ("4000", None, 500)):
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    report = import_tb(
        books["session"],
        buffer.getvalue(),
        "tb.xlsx",
        {"account": "Code", "debit": "Dr", "credit": "Cr"},
    )
    assert report["counts"]["ok"] == 2 and report["totals"]["difference"] == "0.00"


def test_mapping_errors(books: dict[str, Any]) -> None:
    for mapping in (
        {"debit": "Debit"},
        {"account": "Account Code", "balance": "Debit", "debit": "Debit"},
        {"account": "Nope", "debit": "Debit", "credit": "Credit"},
    ):
        with pytest.raises(ValidationError) as caught:
            import_tb(books["session"], GOOD, "tb.csv", mapping)
        assert caught.value.error_dict["mapping"][0].code == "conversion.import.mapping"


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1,234.56", Decimal("1234.56")),
        ("$1,234.56", Decimal("1234.56")),
        ("(123.45)", Decimal("-123.45")),
        ("-5", Decimal("-5")),
        ("12.00 CR", Decimal("-12.00")),
        ("12.00 DR", Decimal("12.00")),
        ("", Decimal("0.00")),
        ("1.234", None),
        ("abc", None),
        ("12,34", None),
    ],
)
def test_parse_amount(text: str, value: Decimal | None) -> None:
    assert parse_amount(text) == value
