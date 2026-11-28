"""How a CSV / XLSX statement is read (F-02-T03): the ``Layout`` and the row normaliser.

A ``Layout`` says, for a table of text cells:

- ``columns`` — the **role** of each column, by position: ``date``, ``description`` (several
  description columns are joined with a space), ``payee``, ``reference``, ``fitid`` (the bank's
  transaction ID), ``amount``, ``debit`` (money out), ``credit`` (money in), ``balance`` (the
  running balance, F-02-T14) or ``ignore``. Columns past the end of the list are ignored;
- ``date_format`` — one of ``DATE_FORMATS`` (``DD/MM/YYYY``, ``MM/DD/YYYY``, ``YYYY-MM-DD``…).
  Dates are parsed with the declared format only: ``03/04/2026`` is never guessed (F-02 business
  rule). A date cell of an XLSX file (``2026-04-03`` once read) is accepted whatever the format;
- ``sign`` — ``signed`` (one amount column, positive = money in, negative = money out),
  ``inverted`` (one amount column, positive = money out — many credit-card exports) or
  ``debit_credit`` (a withdrawal column and a deposit column; withdrawals are money out whatever
  their sign in the file);
- ``has_header`` / ``skip_rows`` — the non-empty rows before the header (or before the first data
  row when the file has no header) that are not data: a title, "Following data is valid as of…";
- ``decimal_separator`` — ``.`` (``1,234.56``) or ``,`` (``1 234,56``, French exports).

``apply_layout(table, layout)`` turns the data rows into ``RawLine`` objects: amounts signed from
the account holder's side (``StatementLine.amount``), text trimmed and whitespace collapsed, and
each row that can't be read carries the ``LineProblem`` that names the row and the fix.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from . import errors
from .errors import LineProblem, StatementError


class Role(StrEnum):
    DATE = "date"
    DESCRIPTION = "description"
    PAYEE = "payee"
    REFERENCE = "reference"
    FITID = "fitid"
    AMOUNT = "amount"
    DEBIT = "debit"
    CREDIT = "credit"
    BALANCE = "balance"
    IGNORE = "ignore"


class Sign(StrEnum):
    SIGNED = "signed"
    INVERTED = "inverted"
    DEBIT_CREDIT = "debit_credit"


#: Date formats a person can choose, as shown → ``strptime`` pattern. Days and months may be
#: written without their leading zero (``3/4/2026``) in every numeric format.
DATE_FORMATS: dict[str, str] = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "YYYY/MM/DD": "%Y/%m/%d",
    "YYYYMMDD": "%Y%m%d",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD-MM-YYYY": "%d-%m-%Y",
    "MM-DD-YYYY": "%m-%d-%Y",
    "DD.MM.YYYY": "%d.%m.%Y",
    "DD/MM/YY": "%d/%m/%y",
    "MM/DD/YY": "%m/%d/%y",
    "DD MMM YYYY": "%d %b %Y",
    "MMM DD, YYYY": "%b %d, %Y",
}
DECIMAL_SEPARATORS = (".", ",")
CENTS = Decimal("0.01")
#: ``StatementLine.amount`` holds 18 digits, 2 of them decimals.
MAX_AMOUNT = Decimal("9999999999999999.99")
ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:T[\d:.]+)?$")
_SPACES = re.compile(r"\s+")
_AMOUNT_NOISE = re.compile(r"[\s  '$€£]|CAD|USD|EUR", re.IGNORECASE)


@dataclass(frozen=True)
class Layout:
    columns: tuple[str, ...]
    date_format: str = "YYYY-MM-DD"
    sign: str = Sign.SIGNED
    has_header: bool = True
    skip_rows: int = 0
    decimal_separator: str = "."

    # ---- (de)serialisation: ``StatementImport.mapping`` and the API keep it as JSON ----------

    def as_dict(self) -> dict[str, Any]:
        return {
            "columns": list(self.columns),
            "date_format": self.date_format,
            "sign": str(self.sign),
            "has_header": self.has_header,
            "skip_rows": self.skip_rows,
            "decimal_separator": self.decimal_separator,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Layout:
        """A layout from JSON; refuses anything it can't use (``StatementError``)."""
        try:
            columns = tuple(str(Role(str(c or Role.IGNORE))) for c in data.get("columns") or ())
            sign = str(Sign(str(data.get("sign") or Sign.SIGNED)))
            skip = int(data.get("skip_rows") or 0)
        except (TypeError, ValueError) as exc:
            raise StatementError(errors.LAYOUT_INVALID, reason=str(exc)) from exc
        separator = str(data.get("decimal_separator") or ".")
        if separator not in DECIMAL_SEPARATORS or not 0 <= skip <= 100:
            raise StatementError(errors.LAYOUT_INVALID, reason=f"{separator!r} / {skip}")
        layout = cls(
            columns=columns,
            date_format=str(data.get("date_format") or "YYYY-MM-DD"),
            sign=sign,
            has_header=bool(data.get("has_header", True)),
            skip_rows=skip,
            decimal_separator=separator,
        )
        layout.check()
        return layout

    def with_columns(self, columns: Iterable[str]) -> Layout:
        return replace(self, columns=tuple(columns))

    # ---- checks ---------------------------------------------------------------------------------

    def check(self) -> None:
        """Refuse a layout that can't produce a date and an amount for a line."""
        if self.date_format not in DATE_FORMATS:
            raise StatementError(errors.LAYOUT_DATE_FORMAT, format=self.date_format)
        roles = set(self.columns)
        if Role.DATE not in roles:
            raise StatementError(errors.LAYOUT_NO_DATE)
        if self.sign == Sign.DEBIT_CREDIT:
            if not {Role.DEBIT, Role.CREDIT} <= roles:
                raise StatementError(errors.LAYOUT_NO_DEBIT_CREDIT)
        elif Role.AMOUNT not in roles:
            raise StatementError(errors.LAYOUT_NO_AMOUNT)

    def positions(self, role: str) -> list[int]:
        return [i for i, r in enumerate(self.columns) if r == role]


# ---- tables (what the CSV / XLSX parsers give, F-02-T04) ----------------------------------------


@dataclass(frozen=True)
class TableRow:
    number: int  # the row's number in the file (1-based), for messages
    cells: tuple[str, ...]


@dataclass(frozen=True)
class Table:
    """Every non-empty row of a CSV file or of an XLSX file's first visible sheet, as text."""

    rows: tuple[TableRow, ...]
    iso_dates: bool = False  # XLSX: date cells were read as ISO dates

    def header_and_data(self, layout: Layout) -> tuple[TableRow | None, tuple[TableRow, ...]]:
        rest = self.rows[layout.skip_rows :]
        if layout.has_header:
            return (rest[0] if rest else None), rest[1:]
        return None, rest

    @property
    def width(self) -> int:
        return max((len(r.cells) for r in self.rows), default=0)


# ---- the row normaliser -------------------------------------------------------------------------


@dataclass(frozen=True)
class RawLine:
    """One statement line, normalised (F-02-T03): what every ``BankStatementSource`` returns.

    ``amount`` is signed from the account holder's side (positive = money in). ``row`` is the
    line's row in the file (CSV / XLSX) or its position (OFX), for messages. A line that can't be
    read has ``problems`` (and ``date`` / ``amount`` may be missing)."""

    row: int
    date: dt.date | None
    amount: Decimal | None
    description: str = ""
    payee: str = ""
    reference: str = ""
    fitid: str = ""
    balance: Decimal | None = None
    problems: tuple[LineProblem, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.problems and self.date is not None and self.amount is not None


def clean_text(value: str) -> str:
    return _SPACES.sub(" ", value or "").strip()


def parse_date(value: str, date_format: str, *, iso_ok: bool = False) -> dt.date | None:
    """``value`` read with ``date_format`` only; ``None`` when it doesn't fit."""
    text = clean_text(value)
    if not text:
        return None
    if iso_ok and (match := ISO_DATE.match(text)):
        try:
            return dt.date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return None
    pattern = DATE_FORMATS[date_format]
    candidates = [text]
    if " " in text and " " not in date_format:
        candidates.append(text.split(" ", 1)[0])  # "06/03/2026 12:00:00 AM"
    for candidate in candidates:
        try:
            return dt.datetime.strptime(candidate, pattern).date()  # noqa: DTZ007 (a date)
        except ValueError:
            continue
    return None


class AmountError(ValueError):
    pass


def parse_amount(value: str, decimal_separator: str = ".") -> Decimal | None:
    """``1,234.56`` / ``(4.25)`` / ``4.25-`` / ``-$4.25`` / ``1 234,56`` → Decimal (2 places);
    ``None`` for an empty cell; ``AmountError`` when it isn't a number."""
    text = _AMOUNT_NOISE.sub("", value or "")
    if not text:
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    if text.endswith("-"):
        negative, text = not negative, text[:-1]
    if text.startswith(("-", "+")):
        negative, text = (not negative) if text[0] == "-" else negative, text[1:]
    if decimal_separator == ",":
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d+)?|\.\d+", text):
        raise AmountError(value)
    try:
        amount = Decimal(text).quantize(CENTS, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:  # pragma: no cover - the pattern above rules it out
        raise AmountError(value) from exc
    if amount > MAX_AMOUNT:
        raise AmountError(value)
    return -amount if negative else amount


def _cell(cells: Sequence[str], index: int) -> str:
    return cells[index] if index < len(cells) else ""


def _amount(
    row: int, cells: Sequence[str], positions: list[int], separator: str
) -> tuple[Decimal | None, LineProblem | None]:
    """The first non-empty amount among ``positions``."""
    for index in positions:
        raw = _cell(cells, index)
        try:
            amount = parse_amount(raw, separator)
        except AmountError:
            digits = re.sub(r"\D", "", raw)
            error = errors.ROW_AMOUNT_TOO_LARGE if len(digits) > 18 else errors.ROW_AMOUNT_INVALID
            return None, LineProblem(error, {"row": row, "value": clean_text(raw)})
        if amount is not None:
            return amount, None
    return None, None


def normalise_row(row: TableRow, layout: Layout, *, iso_dates: bool = False) -> RawLine:
    """One data row → ``RawLine`` (see the module docstring)."""
    cells = row.cells
    problems: list[LineProblem] = []

    def joined(role: str) -> str:
        return clean_text(" ".join(_cell(cells, i) for i in layout.positions(role)))

    raw_date = joined(Role.DATE)
    date = parse_date(raw_date, layout.date_format, iso_ok=iso_dates)
    if not raw_date:
        problems.append(LineProblem(errors.ROW_DATE_MISSING, {"row": row.number}))
    elif date is None:
        problems.append(
            LineProblem(
                errors.ROW_DATE_FORMAT,
                {"row": row.number, "value": raw_date, "format": layout.date_format},
            )
        )

    separator = layout.decimal_separator
    amount: Decimal | None = None
    if layout.sign == Sign.DEBIT_CREDIT:
        debit, debit_problem = _amount(row.number, cells, layout.positions(Role.DEBIT), separator)
        credit, credit_problem = _amount(
            row.number, cells, layout.positions(Role.CREDIT), separator
        )
        problem = debit_problem or credit_problem
        if problem:
            problems.append(problem)
        elif debit and credit:
            problems.append(
                LineProblem(
                    errors.ROW_TWO_AMOUNTS, {"row": row.number, "debit": debit, "credit": credit}
                )
            )
        elif debit is not None or credit is not None:
            amount = abs(credit) if credit else -abs(debit or Decimal(0))
        else:
            problems.append(LineProblem(errors.ROW_AMOUNT_MISSING, {"row": row.number}))
    else:
        amount, problem = _amount(row.number, cells, layout.positions(Role.AMOUNT), separator)
        if problem:
            problems.append(problem)
        elif amount is None:
            problems.append(LineProblem(errors.ROW_AMOUNT_MISSING, {"row": row.number}))
        elif layout.sign == Sign.INVERTED:
            amount = -amount
    if amount is not None and not amount:
        amount = CENTS * 0  # never -0.00
    # A running balance that can't be read is left out; it is never a reason to refuse the line.
    balance, _problem = _amount(row.number, cells, layout.positions(Role.BALANCE), separator)

    return RawLine(
        row=row.number,
        date=date,
        amount=amount,
        description=joined(Role.DESCRIPTION),
        payee=joined(Role.PAYEE),
        reference=joined(Role.REFERENCE),
        fitid=joined(Role.FITID),
        balance=balance,
        problems=tuple(problems),
    )


def apply_layout(table: Table, layout: Layout) -> Iterator[RawLine]:
    """The data rows of ``table`` read with ``layout`` (checked first)."""
    layout.check()
    _, data = table.header_and_data(layout)
    for row in data:
        yield normalise_row(row, layout, iso_dates=table.iso_dates)
