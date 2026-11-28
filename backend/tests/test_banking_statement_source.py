"""F-02-T03 — ``BankStatementSource`` interface and ``FileStatementSource``.

Acceptance: the interface is documented (``fetch_lines()``, ``source_name``, ``balances()``); the
file source returns normalised ``RawLine`` objects — dates read with the declared format only,
amounts signed from the account holder's side under each sign convention, text trimmed, multiple
description columns joined — and every row that can't be read is returned with a problem naming
the row and the fix (never dropped). A tabular file is never read without a layout.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest

from numo9.banking.statements import source as source_module
from numo9.banking.statements.errors import StatementError
from numo9.banking.statements.layout import (
    Layout,
    Role,
    Sign,
    Table,
    TableRow,
    apply_layout,
    parse_amount,
    parse_date,
)
from numo9.banking.statements.source import (
    BankStatementSource,
    FileStatementSource,
    LayoutRequired,
    ParsedStatement,
    RawLine,
)

ROWS = (
    TableRow(1, ("Date", "Description", "Details", "Amount")),
    TableRow(2, ("03/06/2026", " TIM HORTONS  #1234 ", "Toronto", "-4.25")),
    TableRow(3, ("04/06/2026", "PAYROLL", "", "1,500.00")),
    TableRow(5, ("31/06/2026", "BAD DATE", "", "10.00")),
    TableRow(6, ("05/06/2026", "BAD AMOUNT", "", "ten")),
    TableRow(7, ("", "NO DATE", "", "")),
)
LAYOUT = Layout(
    columns=(Role.DATE, Role.DESCRIPTION, Role.DESCRIPTION, Role.AMOUNT),
    date_format="DD/MM/YYYY",
)


@pytest.fixture
def table_parser() -> Iterator[None]:
    def parse(data: bytes, filename: str) -> ParsedStatement:
        return ParsedStatement(format="csv", encoding="utf-8", delimiter=",", table=Table(ROWS))

    previous = source_module.set_parser(parse)
    yield
    source_module.set_parser(previous)


def test_interface_is_abstract_and_documented() -> None:
    assert BankStatementSource.__abstractmethods__ == frozenset({"fetch_lines"})
    assert "fetch_lines" in (source_module.__doc__ or "")
    assert "source_name" in (source_module.__doc__ or "")
    assert FileStatementSource.source_name == "file"


@pytest.mark.usefixtures("table_parser")
def test_file_source_returns_normalised_lines() -> None:
    lines = FileStatementSource(b"...", "june.csv", LAYOUT).fetch_lines()
    assert all(isinstance(line, RawLine) for line in lines)
    first, second, bad_date, bad_amount, no_date = lines
    assert first == RawLine(
        row=2,
        date=dt.date(2026, 6, 3),
        amount=Decimal("-4.25"),
        description="TIM HORTONS #1234 Toronto",
    )
    assert second.amount == Decimal("1500.00") and second.ok
    assert bad_date.date is None and not bad_date.ok
    assert bad_date.problems[0].message() == (
        "Row 5: date '31/06/2026' doesn't match DD/MM/YYYY. Choose the date format your bank "
        "uses on the Map step, or correct the row."
    )
    assert bad_amount.problems[0].code == "banking.statement.row.amount_invalid"
    assert "Row 6: amount 'ten'" in bad_amount.problems[0].message()
    assert [p.code for p in no_date.problems] == [
        "banking.statement.row.date_missing",
        "banking.statement.row.amount_missing",
    ]


@pytest.mark.usefixtures("table_parser")
def test_a_tabular_file_needs_a_layout() -> None:
    with pytest.raises(LayoutRequired):
        FileStatementSource(b"...", "june.csv").fetch_lines()


def test_structured_lines_pass_through() -> None:
    line = RawLine(row=1, date=dt.date(2026, 6, 3), amount=Decimal("-4.25"), fitid="A1")
    parsed = ParsedStatement(format="ofx", lines=(line,))
    previous = source_module.set_parser(lambda data, name: parsed)
    try:
        assert FileStatementSource(b"<OFX>", "june.ofx").fetch_lines() == [line]
    finally:
        source_module.set_parser(previous)


@pytest.mark.parametrize(
    ("sign", "cells", "expected"),
    [
        (Sign.SIGNED, ("2026-06-03", "x", "-4.25", ""), Decimal("-4.25")),
        (Sign.INVERTED, ("2026-06-03", "x", "4.25", ""), Decimal("-4.25")),
        (Sign.INVERTED, ("2026-06-03", "x", "-20.00", ""), Decimal("20.00")),
        (Sign.DEBIT_CREDIT, ("2026-06-03", "x", "4.25", ""), Decimal("-4.25")),
        (Sign.DEBIT_CREDIT, ("2026-06-03", "x", "-4.25", ""), Decimal("-4.25")),
        (Sign.DEBIT_CREDIT, ("2026-06-03", "x", "", "20.00"), Decimal("20.00")),
    ],
)
def test_sign_conventions(sign: Sign, cells: tuple[str, ...], expected: Decimal) -> None:
    roles = (
        (Role.DATE, Role.DESCRIPTION, Role.DEBIT, Role.CREDIT)
        if sign == Sign.DEBIT_CREDIT
        else (Role.DATE, Role.DESCRIPTION, Role.AMOUNT, Role.IGNORE)
    )
    layout = Layout(columns=roles, sign=sign, has_header=False)
    (line,) = apply_layout(Table((TableRow(1, cells),)), layout)
    assert line.amount == expected


def test_both_withdrawal_and_deposit_is_a_problem() -> None:
    layout = Layout(
        columns=(Role.DATE, Role.DESCRIPTION, Role.DEBIT, Role.CREDIT),
        sign=Sign.DEBIT_CREDIT,
        has_header=False,
    )
    (line,) = apply_layout(Table((TableRow(9, ("2026-06-03", "x", "4.25", "4.25")),)), layout)
    assert line.problems[0].code == "banking.statement.row.two_amounts"


@pytest.mark.parametrize(
    ("text", "separator", "expected"),
    [
        ("1,234.56", ".", Decimal("1234.56")),
        ("(4.25)", ".", Decimal("-4.25")),
        ("4.25-", ".", Decimal("-4.25")),
        ("-$4.25", ".", Decimal("-4.25")),
        ("$ 1 234.5", ".", Decimal("1234.50")),
        ("1 234,56", ",", Decimal("1234.56")),
        ("1.234,56", ",", Decimal("1234.56")),
        ("-0,99", ",", Decimal("-0.99")),
        ("12.345", ".", Decimal("12.35")),
        ("", ".", None),
        ("CAD 7.00", ".", Decimal("7.00")),
    ],
)
def test_parse_amount(text: str, separator: str, expected: Decimal | None) -> None:
    assert parse_amount(text, separator) == expected


@pytest.mark.parametrize(
    ("text", "fmt", "expected"),
    [
        ("03/04/2026", "DD/MM/YYYY", dt.date(2026, 4, 3)),
        ("03/04/2026", "MM/DD/YYYY", dt.date(2026, 3, 4)),
        ("3/4/2026", "MM/DD/YYYY", dt.date(2026, 3, 4)),
        ("20260403", "YYYYMMDD", dt.date(2026, 4, 3)),
        ("06/03/2026 12:00:00 AM", "MM/DD/YYYY", dt.date(2026, 6, 3)),
        ("3 Jun 2026", "DD MMM YYYY", dt.date(2026, 6, 3)),
        ("13/25/2026", "DD/MM/YYYY", None),
        ("2026-04-03", "DD/MM/YYYY", None),  # never guessed
    ],
)
def test_parse_date_uses_the_declared_format_only(
    text: str, fmt: str, expected: dt.date | None
) -> None:
    assert parse_date(text, fmt) == expected


def test_xlsx_date_cells_are_accepted_whatever_the_format() -> None:
    assert parse_date("2026-04-03", "DD/MM/YYYY", iso_ok=True) == dt.date(2026, 4, 3)


def test_layout_round_trips_and_refuses_incomplete_mappings() -> None:
    assert Layout.from_dict(LAYOUT.as_dict()) == LAYOUT
    with pytest.raises(StatementError) as no_date:
        Layout.from_dict({"columns": ["description", "amount"]})
    assert no_date.value.code == "banking.statement.layout.no_date"
    with pytest.raises(StatementError) as no_amount:
        Layout.from_dict({"columns": ["date", "description"]})
    assert no_amount.value.code == "banking.statement.layout.no_amount"
    with pytest.raises(StatementError) as no_credit:
        Layout.from_dict({"columns": ["date", "debit"], "sign": "debit_credit"})
    assert no_credit.value.code == "banking.statement.layout.no_debit_credit"
    with pytest.raises(StatementError) as bad_format:
        Layout.from_dict({"columns": ["date", "amount"], "date_format": "DD/MM"})
    assert bad_format.value.code == "banking.statement.layout.date_format"
    with pytest.raises(StatementError):
        Layout.from_dict({"columns": ["date", "amount", "colour"]})


def test_skip_rows_and_headerless_files() -> None:
    table = Table(
        (
            TableRow(1, ("Following data is valid as of 20260601",)),
            TableRow(3, ("Date", "Amount")),
            TableRow(4, ("20260603", "-4.25")),
        )
    )
    layout = Layout(columns=(Role.DATE, Role.AMOUNT), date_format="YYYYMMDD", skip_rows=1)
    header, data = table.header_and_data(layout)
    assert header is not None and header.cells == ("Date", "Amount")
    assert [line.row for line in apply_layout(table, layout)] == [4]
