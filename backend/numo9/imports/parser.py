"""Spreadsheet file parser (B-03-T02): CSV and XLSX into rows of text cells.

``parse_file(data, filename)`` reads an uploaded file into a ``ParsedFile`` — one ``Sheet`` per CSV
file or per visible worksheet, each with its header row and data rows. Every cell is text (an
empty cell is ``""``), so the row normaliser (B-03-T04) and the CoA import (C-01-T13) see the same
thing whatever the file type:

**CSV**

- the encoding is detected, never asked: a byte-order mark decides first (UTF-8, UTF-16 LE/BE);
  then strict UTF-8; otherwise ``charset-normalizer`` chooses among the Western single-byte
  encodings a Canadian file comes in (Windows-1252 — Excel's "CSV" on Windows —, ISO-8859-1/15,
  Mac Roman), Windows-1252 when nothing is conclusive. A UTF-8, UTF-8-with-BOM and Windows-1252
  copy of the same file parse to the same rows;
- the delimiter is sniffed among ``,`` ``;`` (French Excel) tab and ``|``; quoted cells may hold
  delimiters and line breaks.

**XLSX** (Office Open XML; legacy ``.xls`` is refused with a message)

- opened read-only with ``data_only=True``: a formula cell gives the value Excel last calculated,
  never the formula (a file saved by a program that doesn't calculate has no value: the cell is
  empty);
- numbers keep their digits (``42`` not ``42.0``; ``0.1`` stays ``0.1``), dates are ISO
  ``2026-03-31`` (with ``T14:30:00`` when the time isn't midnight), booleans ``TRUE``/``FALSE``;
- hidden worksheets are skipped; XML is parsed with ``defusedxml`` (openpyxl uses it when installed)
  and the archive is checked before opening (members, uncompressed size) against zip bombs.

**Both**

- the header row is the first row with any value; header names are trimmed and must be unique in a
  sheet (they are the keys of a saved mapping, B-03-T03); a column with values but no header is
  named after its letter ("Column F") so its data is never dropped silently;
- cells are trimmed; empty rows are skipped; ``Row.number`` is the row's number in the file
  (header = its own row number, the first data row after it = +1…) for error reports;
- at most 25 MB (the A-06 file limit) and ``MAX_ROWS`` data rows per sheet.

Problems raise ``ImportFileError`` (a ``ValidationError``) with a stable code and a message that
says what to do.
"""

from __future__ import annotations

import codecs
import csv
import datetime as dt
import io
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import PurePath
from typing import Any

from charset_normalizer import from_bytes
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from numo9.files.models import MAX_FILE_SIZE

#: Data rows per sheet (well above the 500-row usability target, B-03-T12).
MAX_ROWS = 100_000
#: Columns per sheet.
MAX_COLUMNS = 200
#: Uncompressed size of an XLSX archive (a 25 MB file legitimately expands to ~10×).
MAX_XLSX_UNCOMPRESSED = 400 * 1024 * 1024
MAX_XLSX_MEMBERS = 10_000

DELIMITERS = ",;\t|"
#: Encodings tried by charset-normalizer when the bytes aren't UTF-8.
WESTERN_ENCODINGS = ["cp1252", "latin_1", "iso8859_15", "mac_roman"]
FALLBACK_ENCODING = "cp1252"

CSV_EXTENSIONS = frozenset({".csv", ".txt", ".tsv"})
XLSX_EXTENSIONS = frozenset({".xlsx", ".xlsm"})
ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .xls (and other OLE files)


class ImportFileError(ValidationError):
    """The file can't be read as a spreadsheet; ``code`` is a stable machine-readable key."""


@dataclass(frozen=True)
class Row:
    number: int  # row number in the file (1-based, the header row counts)
    cells: tuple[str, ...]  # one per header, "" when empty

    def as_dict(self, headers: tuple[str, ...]) -> dict[str, str]:
        return dict(zip(headers, self.cells, strict=True))


@dataclass(frozen=True)
class Sheet:
    name: str
    headers: tuple[str, ...]
    header_row: int
    rows: tuple[Row, ...]

    def samples(self, column: str, count: int = 3) -> list[str]:
        """The first ``count`` non-empty values of a column (the mapping step's sample values)."""
        index = self.headers.index(column)
        found: list[str] = []
        for row in self.rows:
            if row.cells[index]:
                found.append(row.cells[index])
                if len(found) == count:
                    break
        return found


@dataclass(frozen=True)
class ParsedFile:
    filename: str
    format: str  # "csv" or "xlsx"
    encoding: str  # detected encoding of a CSV file, "" for XLSX
    delimiter: str  # sniffed delimiter of a CSV file, "" for XLSX
    sheets: tuple[Sheet, ...] = field(default_factory=tuple)

    @property
    def sheet(self) -> Sheet:
        """The first sheet (a CSV file has exactly one)."""
        return self.sheets[0]


# ---- entry point -------------------------------------------------------------------------------


def parse_file(data: bytes, filename: str) -> ParsedFile:
    if len(data) > MAX_FILE_SIZE:
        raise ImportFileError(
            _("The file is larger than %(max)d MB. Split it into smaller files."),
            code="imports.file.too_large",
            params={"max": MAX_FILE_SIZE // (1024 * 1024)},
        )
    if not data.strip():
        raise ImportFileError(_("The file is empty."), code="imports.file.empty")
    extension = PurePath(filename).suffix.lower()
    if data.startswith(OLE_MAGIC) or extension == ".xls":
        raise ImportFileError(
            _(
                "%(name)s is an old Excel (.xls) file. Open it in Excel and save it as .xlsx "
                "or .csv, then try again."
            ),
            code="imports.file.legacy_xls",
            params={"name": filename},
        )
    if data.startswith(ZIP_MAGIC):
        if extension and extension not in XLSX_EXTENSIONS:
            raise _wrong_type(filename)
        return _parse_xlsx(data, filename)
    if extension and extension not in CSV_EXTENSIONS:
        raise _wrong_type(filename)
    return _parse_csv(data, filename)


def _wrong_type(filename: str) -> ImportFileError:
    return ImportFileError(
        _("%(name)s isn't a CSV or Excel file. Save it as .csv or .xlsx and try again."),
        code="imports.file.type",
        params={"name": filename},
    )


# ---- CSV ---------------------------------------------------------------------------------------


def detect_encoding(data: bytes) -> str:
    """The encoding of a CSV file's bytes (see the module docstring)."""
    if data.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        return "utf-8"
    best = from_bytes(data, cp_isolation=WESTERN_ENCODINGS).best()
    if best is None:
        return FALLBACK_ENCODING
    return str(best.encoding)


def _parse_csv(data: bytes, filename: str) -> ParsedFile:
    encoding = detect_encoding(data)
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as exc:  # pragma: no cover - cp1252 fallback decodes nearly all
        raise ImportFileError(
            _("The file's characters can't be read. Save it as CSV UTF-8 and try again."),
            code="imports.file.encoding",
        ) from exc
    if "\x00" in text:
        raise _wrong_type(filename)
    delimiter = _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        records = [list(record) for record in reader]
    except csv.Error as exc:
        raise ImportFileError(
            _("The CSV file is malformed near line %(line)d: %(reason)s"),
            code="imports.file.malformed",
            params={"line": reader.line_num, "reason": str(exc)},
        ) from exc
    sheet = _build_sheet(PurePath(filename).stem or "Sheet1", enumerate(records, start=1))
    return ParsedFile(filename, "csv", encoding, delimiter, (sheet,))


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except csv.Error:
        # One column, or a header the sniffer can't decide on: the most frequent candidate in
        # the first line, else a comma.
        first = text.splitlines()[0] if text.splitlines() else ""
        counts = {d: first.count(d) for d in DELIMITERS}
        best = max(counts, key=lambda d: counts[d])
        return best if counts[best] else ","


# ---- XLSX --------------------------------------------------------------------------------------


def _check_archive(data: bytes, filename: str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            names = {member.filename for member in members}
            total = sum(member.file_size for member in members)
    except zipfile.BadZipFile as exc:
        raise _unreadable(filename) from exc
    if "xl/workbook.xml" not in names:
        raise _wrong_type(filename)
    if len(members) > MAX_XLSX_MEMBERS or total > MAX_XLSX_UNCOMPRESSED:
        raise ImportFileError(
            _("%(name)s expands to more data than an import can take. Split it and try again."),
            code="imports.file.too_large",
            params={"name": filename},
        )


def _unreadable(filename: str) -> ImportFileError:
    return ImportFileError(
        _("%(name)s can't be opened: it may be damaged or password-protected."),
        code="imports.file.unreadable",
        params={"name": filename},
    )


def _parse_xlsx(data: bytes, filename: str) -> ParsedFile:
    from openpyxl import load_workbook

    _check_archive(data, filename)
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises many types for damaged files
        raise _unreadable(filename) from exc
    sheets: list[Sheet] = []
    try:
        for worksheet in workbook.worksheets:
            if worksheet.sheet_state != "visible":
                continue
            records = (
                (number, [xlsx_text(value) for value in values])
                for number, values in enumerate(worksheet.iter_rows(values_only=True), start=1)
            )
            sheet = _build_sheet(worksheet.title, records, allow_empty=True)
            if sheet.headers:
                sheets.append(sheet)
    finally:
        workbook.close()
    if not sheets:
        raise ImportFileError(_("The file is empty."), code="imports.file.empty")
    return ParsedFile(filename, "xlsx", "", "", tuple(sheets))


def xlsx_text(value: Any) -> str:
    """A worksheet value as the text a person sees (module docstring)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, dt.datetime):
        if value.time() == dt.time(0, 0):
            return value.date().isoformat()
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dt.time):
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        return format(Decimal(repr(value)), "f")
    if isinstance(value, int | Decimal):
        return format(value, "f") if isinstance(value, Decimal) else str(value)
    return str(value)


# ---- shared ------------------------------------------------------------------------------------


def column_letter(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _build_sheet(name: str, records: Any, *, allow_empty: bool = False) -> Sheet:
    header_row = 0
    raw_headers: list[str] = []
    data: list[tuple[int, list[str]]] = []
    for number, record in records:
        cells = [(cell or "").strip() for cell in record]
        if not any(cells):
            continue
        if not header_row:
            header_row, raw_headers = number, cells
            continue
        data.append((number, cells))
        if len(data) > MAX_ROWS:
            raise ImportFileError(
                _("The sheet %(sheet)s has more than %(max)d rows. Split it into smaller files."),
                code="imports.file.too_many_rows",
                params={"sheet": name, "max": MAX_ROWS},
            )
    if not header_row:
        if allow_empty:
            return Sheet(name, (), 0, ())
        raise ImportFileError(_("The file is empty."), code="imports.file.empty")
    width = max([len(raw_headers), *(len(cells) for _, cells in data)])
    # Trailing columns without a header and without data are dropped (Excel's used range).
    while width and not (
        (width <= len(raw_headers) and raw_headers[width - 1])
        or any(width <= len(cells) and cells[width - 1] for _, cells in data)
    ):
        width -= 1
    if width > MAX_COLUMNS:
        raise ImportFileError(
            _("The sheet %(sheet)s has more than %(max)d columns."),
            code="imports.file.too_many_columns",
            params={"sheet": name, "max": MAX_COLUMNS},
        )
    headers: list[str] = []
    for index in range(width):
        header = raw_headers[index] if index < len(raw_headers) else ""
        headers.append(header or str(_("Column %(letter)s") % {"letter": column_letter(index)}))
    seen: dict[str, int] = {}
    for index, header in enumerate(headers):
        key = header.casefold()
        if key in seen:
            raise ImportFileError(
                _(
                    "Columns %(first)s and %(second)s in %(sheet)s are both named “%(header)s”. "
                    "Give each column its own name."
                ),
                code="imports.file.duplicate_header",
                params={
                    "first": column_letter(seen[key]),
                    "second": column_letter(index),
                    "sheet": name,
                    "header": header,
                },
            )
        seen[key] = index
    rows = tuple(
        Row(number, tuple((cells + [""] * width)[:width]))
        for number, cells in data
        if any(cells[:width])
    )
    return Sheet(name, tuple(headers), header_row, rows)
