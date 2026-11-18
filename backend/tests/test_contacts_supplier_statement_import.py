"""B-02-T07 — SupplierStatement + lines import (CSV/XLSX mapping).

Acceptance: imported lines count = file rows. A supplier's statement imports from CSV (UTF-8,
Windows-1252, ``;`` French Excel) and XLSX, with the columns auto-suggested from the headers
(English or French) or given; debit/credit columns become signed amounts; dates and amounts in
the usual Canadian forms parse; a bad row refuses the whole import with every problem listed by
row; lines keep their file row; a contact that isn't a supplier is refused; lines can be typed in.
"""

from __future__ import annotations

import datetime as dt
import io
from decimal import Decimal

import openpyxl
import pytest

from numo9.contacts.models import SupplierStatement, SupplierStatementLine
from numo9.contacts.supplier_statements import (
    SupplierStatementError,
    add_line,
    create_manual_statement,
    import_supplier_statement,
    parse_amount,
    parse_date,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db

CSV = """Invoice Date,Invoice #,PO,Amount
2026-10-02,NS-8812,PO-77,"$4,200.00"
2026-10-09,NS-8830,,1450.00
"Oct 17, 2026",NS-8851,PO-80,"9,910.00"
2026/10/25,NS-8870,,(860.00)
"""


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def steel(org: Organisation) -> object:
    with org_context(org):
        return contact(org, "Northern Steel Inc.", roles=["supplier"])


def _import(
    org: Organisation, supplier: object, data: bytes, name: str, **kw: object
) -> SupplierStatement:
    with org_context(org):
        return import_supplier_statement(supplier, data, name, dt.date(2026, 10, 31), **kw)  # type: ignore[arg-type]


def _lines(org: Organisation, statement: SupplierStatement) -> list[SupplierStatementLine]:
    with org_context(org):
        return list(statement.lines.all())


def test_csv_lines_equal_file_rows(org: Organisation, steel: object) -> None:
    statement = _import(org, steel, CSV.encode(), "northern-oct.csv")
    lines = _lines(org, statement)
    assert len(lines) == CSV.strip().count("\n")  # data rows (header excluded)
    assert [(ln.invoice_number, ln.amount, ln.source_row) for ln in lines] == [
        ("NS-8812", Decimal("4200.00"), 2),
        ("NS-8830", Decimal("1450.00"), 3),
        ("NS-8851", Decimal("9910.00"), 4),
        ("NS-8870", Decimal("-860.00"), 5),
    ]
    assert lines[2].date == dt.date(2026, 10, 17) and lines[0].reference == "PO-77"
    assert statement.columns == {
        "Invoice Date": "date",
        "Invoice #": "invoice_number",
        "PO": "reference",
        "Amount": "amount",
    }
    assert statement.source == "file" and statement.file_name == "northern-oct.csv"


def test_french_windows_1252_semicolons(org: Organisation, steel: object) -> None:
    text = (
        "Date;Facture;Libellé;Débit;Crédit\n"
        "2 oct. 2026;F-1;Achat acier;1 234,56 $;\n"
        "14 oct. 2026;P-9;Paiement reçu;;500,00\n"
    )
    statement = _import(org, steel, text.encode("cp1252"), "relevé.csv")
    lines = _lines(org, statement)
    assert [(ln.date, ln.invoice_number, ln.amount) for ln in lines] == [
        (dt.date(2026, 10, 2), "F-1", Decimal("1234.56")),
        (dt.date(2026, 10, 14), "P-9", Decimal("-500.00")),
    ]
    assert lines[1].description == "Paiement reçu"


def test_xlsx_with_given_mapping(org: Organisation, steel: object) -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["When", "Doc", "Total"])
    for day in range(1, 31):
        sheet.append([dt.date(2026, 9, day), f"NS-{day}", day * 10.5])
    data = io.BytesIO()
    book.save(data)
    statement = _import(
        org,
        steel,
        data.getvalue(),
        "sept.xlsx",
        columns={"When": "date", "Doc": "invoice_number", "Total": "amount"},
    )
    lines = _lines(org, statement)
    assert len(lines) == 30 and lines[-1].amount == Decimal("315.00")


def test_a_bad_row_refuses_the_whole_file(org: Organisation, steel: object) -> None:
    bad = CSV + "someday,NS-9,,12.00\n2026-10-30,NS-10,,twelve\n"
    with pytest.raises(SupplierStatementError) as refused:
        _import(org, steel, bad.encode(), "bad.csv")
    assert refused.value.code == "contacts.supplier_statement.bad_rows"
    assert refused.value.rows == [
        {"row": 6, "field": "date", "value": "someday"},
        {"row": 7, "field": "amount", "value": "twelve"},
    ]
    with org_context(org):
        assert not SupplierStatement.objects.exists()
        assert not SupplierStatementLine.objects.exists()


def test_mapping_needs_date_and_amount(org: Organisation, steel: object) -> None:
    with pytest.raises(SupplierStatementError) as refused:
        _import(org, steel, CSV.encode(), "x.csv", columns={"Invoice #": "invoice_number"})
    assert refused.value.code == "contacts.supplier_statement.required_columns"


def test_only_suppliers_and_typed_lines(org: Organisation, steel: object) -> None:
    with org_context(org):
        customer = contact(org, "Cedar Roofing Co.")
        with pytest.raises(SupplierStatementError):
            import_supplier_statement(customer, CSV.encode(), "x.csv", dt.date(2026, 10, 31))
        manual = create_manual_statement(steel, dt.date(2026, 10, 31), Decimal("18420.00"))
        add_line(manual, dt.date(2026, 10, 2), Decimal("4200.00"), invoice_number="NS-8812")
        add_line(manual, dt.date(2026, 10, 9), Decimal("1450.00"), invoice_number="NS-8830")
        assert [ln.position for ln in manual.lines.all()] == [1, 2]
        assert manual.source == "manual"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,234.56", Decimal("1234.56")),
        ("1 234,56 $", Decimal("1234.56")),
        ("(860.00)", Decimal("-860.00")),
        ("-12", Decimal("-12.00")),
        ("125.00 CR", Decimal("-125.00")),
        ("1.234,56", Decimal("1234.56")),
        ("twelve", None),
        ("", None),
    ],
)
def test_amounts(text: str, expected: Decimal | None) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-10-02", dt.date(2026, 10, 2)),
        ("2026/10/02", dt.date(2026, 10, 2)),
        ("Oct 2, 2026", dt.date(2026, 10, 2)),
        ("2 oct. 2026", dt.date(2026, 10, 2)),
        ("17 août 2026", dt.date(2026, 8, 17)),
        ("2026-02-30", None),
        ("someday", None),
    ],
)
def test_dates(text: str, expected: dt.date | None) -> None:
    assert parse_date(text) == expected
