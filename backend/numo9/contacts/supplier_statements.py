"""Supplier statements: import their lines from CSV/XLSX with a column mapping (B-02-T07).

A supplier's statement lists their documents (invoices, credits, our payments) with dates and
amounts; we keep it as a ``SupplierStatement`` with its ``SupplierStatementLine`` rows and
reconcile it against our bills (B-02-T08).

``import_supplier_statement(contact, data, filename, statement_date, columns=None)``:

1. the file is read with the B-03 parser (CSV in any Canadian encoding and delimiter, XLSX values
   not formulas; ``numo9.imports.parser``);
2. columns map file headers to line fields — ``date`` and ``amount`` required; ``invoice_number``,
   ``reference``, ``description`` optional; ``debit`` / ``credit`` instead of ``amount`` (amount =
   debit − credit). Given, or the saved mapping for the same headers, or auto-suggested from the
   headers (English and French names, ``numo9.imports.mapping``);
3. every row is checked: a date (``2026-10-02``, ``2026/10/02``, ``Oct 2, 2026``, ``2 oct.
   2026``…) and an amount (``$1,234.56``, ``1 234,56 $``, ``(1,234.56)`` = negative, ``-12.00``).
   Any bad row refuses the whole import with every problem listed by row number — nothing is
   half-imported;
4. one line per data row, in file order (``source_row`` = its row number): **lines imported =
   rows in the file**.

The supplier must have the supplier role. ``add_line`` types a line in by hand.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from numo9.imports.fields import ImportEntity, ImportField
from numo9.imports.mapping import as_columns, resolve
from numo9.imports.parser import parse_file

from .models import (
    SupplierStatement,
    SupplierStatementLine,
    SupplierStatementSource,
)

SUPPLIER_STATEMENT_LINE = ImportEntity(
    "supplier_statement_line",
    gettext_lazy("Supplier statement lines"),
    (
        ImportField(
            "date",
            gettext_lazy("Date"),
            ("date", "invoice date", "doc date", "transaction date"),
            ("date", "date de la facture"),
            required=True,
        ),
        ImportField(
            "invoice_number",
            gettext_lazy("Invoice number"),
            (
                "invoice",
                "invoice number",
                "invoice no",
                "inv",
                "document",
                "document number",
                "number",
            ),
            ("facture", "numero de facture", "no de facture", "document"),
        ),
        ImportField(
            "reference",
            gettext_lazy("Reference"),
            ("reference", "ref", "po", "po number"),
            ("reference", "bon de commande"),
        ),
        ImportField(
            "description",
            gettext_lazy("Description"),
            ("description", "details", "memo", "type"),
            ("description", "details", "libelle"),
        ),
        ImportField(
            "amount",
            gettext_lazy("Amount"),
            ("amount", "total", "balance due", "invoice amount"),
            ("montant", "total"),
        ),
        ImportField("debit", gettext_lazy("Debit"), ("debit", "charges"), ("debit",)),
        ImportField("credit", gettext_lazy("Credit"), ("credit", "payments"), ("credit",)),
    ),
)

_MONTHS = {
    **{
        m: i
        for i, m in enumerate(
            ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
        )
    },
    **{
        m: i
        for i, m in enumerate(
            [
                "janv",
                "fevr",
                "mars",
                "avr",
                "mai",
                "juin",
                "juil",
                "aout",
                "sept",
                "oct",
                "nov",
                "dec",
            ],
            1,
        )
    },
    "sept": 9,
    "fev": 2,
    "jui": 7,
}


class SupplierStatementError(ValidationError):
    """The statement can't be imported; ``rows`` lists the problems by file row."""

    def __init__(self, message: str, code: str, rows: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message, code=code)
        self.rows = rows or []


def _fold(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def parse_date(text: str) -> dt.date | None:
    value = text.strip()
    if not value:
        return None
    iso = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:T.*)?", value)
    if iso:
        try:
            return dt.date(int(iso[1]), int(iso[2]), int(iso[3]))
        except ValueError:
            return None
    words = re.findall(r"[a-zà-ÿ]+|\d+", _fold(value))
    numbers = [w for w in words if w.isdigit()]
    names = [w for w in words if not w.isdigit()]
    if len(numbers) == 2 and len(names) == 1:
        month = _MONTHS.get(names[0][:4]) or _MONTHS.get(names[0][:3])
        day, year = (int(numbers[0]), int(numbers[1]))
        if month and year > 1900:
            try:
                return dt.date(year, month, day)
            except ValueError:
                return None
    return None


def parse_amount(text: str) -> Decimal | None:
    value = text.strip().replace(" ", " ").replace(" ", " ")
    if not value:
        return None
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()").replace("$", "").replace("CAD", "").replace(" ", "")
    if value.upper().endswith("CR"):
        negative, value = True, value[:-2]
    if value.startswith("-"):
        negative, value = not negative, value[1:]
    if "," in value and ("." not in value or value.rfind(",") > value.rfind(".")):
        if re.fullmatch(r"\d{1,3}(\.\d{3})*,\d{1,2}|\d+,\d{1,2}", value):
            value = value.replace(".", "").replace(",", ".")  # 1.234,56 / 1234,56
        else:
            value = value.replace(",", "")  # 1,234
    else:
        value = value.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d+)?", value):
        return None
    try:
        amount = Decimal(value).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -amount if negative else amount


@dataclass(frozen=True)
class ParsedLine:
    row: int
    date: dt.date
    amount: Decimal
    invoice_number: str
    reference: str
    description: str


def _check_columns(columns: dict[str, str], headers: tuple[str, ...]) -> dict[str, str]:
    """``field → header`` for the mapped fields; refuses a mapping without date and amount."""
    by_field: dict[str, str] = {}
    for header, target in columns.items():
        if not target:
            continue
        if header not in headers:
            raise SupplierStatementError(
                _("The file has no column called %(header)s.") % {"header": header},
                "contacts.supplier_statement.unknown_column",
            )
        if target in by_field:
            raise SupplierStatementError(
                _("Two columns are mapped to %(field)s.") % {"field": target},
                "contacts.supplier_statement.duplicate_field",
            )
        by_field[target] = header
    has_amount = "amount" in by_field or "debit" in by_field or "credit" in by_field
    if "date" not in by_field or not has_amount:
        raise SupplierStatementError(
            _("Map a column to Date and one to Amount (or Debit and Credit)."),
            "contacts.supplier_statement.required_columns",
        )
    return by_field


def parse_lines(
    data: bytes, filename: str, columns: dict[str, str] | None = None
) -> tuple[list[ParsedLine], dict[str, str]]:
    """The file's lines, checked, and the column mapping used (header → field)."""
    sheet = parse_file(data, filename).sheet
    mapping = (
        columns
        if columns is not None
        else as_columns(resolve(SUPPLIER_STATEMENT_LINE.key, sheet.headers))
    )
    by_field = _check_columns(mapping, sheet.headers)
    index = {target: sheet.headers.index(header) for target, header in by_field.items()}
    lines: list[ParsedLine] = []
    problems: list[dict[str, Any]] = []

    def cell(row: Any, target: str) -> str:
        return str(row.cells[index[target]]) if target in index else ""

    for row in sheet.rows:
        date = parse_date(cell(row, "date"))
        if "amount" in index:
            amount = parse_amount(cell(row, "amount"))
        else:
            debit = parse_amount(cell(row, "debit") or "0")
            credit = parse_amount(cell(row, "credit") or "0")
            amount = None if debit is None or credit is None else debit - credit
        if date is None:
            problems.append({"row": row.number, "field": "date", "value": cell(row, "date")})
        if amount is None:
            problems.append({"row": row.number, "field": "amount", "value": cell(row, "amount")})
        if date is None or amount is None:
            continue
        lines.append(
            ParsedLine(
                row.number,
                date,
                amount,
                cell(row, "invoice_number")[:100],
                cell(row, "reference")[:200],
                cell(row, "description")[:500],
            )
        )
    if problems:
        raise SupplierStatementError(
            _("%(count)d rows can't be read: fix them in the file and import it again.")
            % {"count": len({p["row"] for p in problems})},
            "contacts.supplier_statement.bad_rows",
            problems,
        )
    if not lines:
        raise SupplierStatementError(
            _("The file has no lines."), "contacts.supplier_statement.empty"
        )
    return lines, mapping


def _require_supplier(contact: Any) -> None:
    if "supplier" not in (contact.roles or []):
        raise SupplierStatementError(
            _("%(name)s isn't a supplier.") % {"name": contact.display_name},
            "contacts.supplier_statement.not_supplier",
        )


@transaction.atomic
def import_supplier_statement(
    contact: Any,
    data: bytes,
    filename: str,
    statement_date: dt.date,
    *,
    columns: dict[str, str] | None = None,
    their_balance: Decimal | None = None,
) -> SupplierStatement:
    _require_supplier(contact)
    lines, mapping = parse_lines(data, filename, columns)
    statement: SupplierStatement = SupplierStatement.objects.create(
        organisation=contact.organisation,
        contact=contact,
        statement_date=statement_date,
        their_balance=their_balance,
        currency=contact.currency,
        source=SupplierStatementSource.FILE,
        file_name=filename[:255],
        columns=mapping,
    )
    SupplierStatementLine.objects.bulk_create(
        [
            SupplierStatementLine(
                organisation=contact.organisation,
                statement=statement,
                position=position,
                date=line.date,
                invoice_number=line.invoice_number,
                reference=line.reference,
                description=line.description,
                amount=line.amount,
                source_row=line.row,
            )
            for position, line in enumerate(lines, start=1)
        ]
    )
    return statement


@transaction.atomic
def create_manual_statement(
    contact: Any, statement_date: dt.date, their_balance: Decimal | None = None
) -> SupplierStatement:
    _require_supplier(contact)
    statement: SupplierStatement = SupplierStatement.objects.create(
        organisation=contact.organisation,
        contact=contact,
        statement_date=statement_date,
        their_balance=their_balance,
        currency=contact.currency,
        source=SupplierStatementSource.MANUAL,
    )
    return statement


def add_line(
    statement: SupplierStatement,
    date: dt.date,
    amount: Decimal,
    *,
    invoice_number: str = "",
    reference: str = "",
    description: str = "",
) -> SupplierStatementLine:
    last = statement.lines.order_by("-position").values_list("position", flat=True).first()
    line: SupplierStatementLine = SupplierStatementLine.objects.create(
        organisation=statement.organisation,
        statement=statement,
        position=(last or 0) + 1,
        date=date,
        amount=amount,
        invoice_number=invoice_number,
        reference=reference,
        description=description,
    )
    return line
