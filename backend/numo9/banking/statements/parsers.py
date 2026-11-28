"""Statement file parsers (F-02-T04): OFX / QFX / QBO, CSV and XLSX → ``ParsedStatement``.

``parse_statement(data, filename)`` recognises the format from the **content**, not the name:

- the OFX family (``OFXHEADER`` or ``<OFX>`` in the first 8 KB) → ``ofx.parse_ofx``; the format
  shown is the file's extension (``qfx``, ``qbo``) or ``ofx``;
- a ZIP package (``PK``) → XLSX; a legacy ``.xls`` (OLE) file is refused with how to fix it;
- anything else that is text → CSV.

**CSV** — the encoding is detected, never asked (a byte-order mark, then strict UTF-8, then
``charset-normalizer`` among the Western encodings, Windows-1252 when unsure — the same rule as
the B-03 importer, ``numo9.imports.parser.detect_encoding``). The delimiter is sniffed among
``,`` ``;`` tab and ``|``: the candidate that splits the most lines into the same number of
columns, so a bank's title line ("Following data is valid as of…") doesn't mislead it. Quoted
cells may hold delimiters and line breaks.

**XLSX** — the first visible worksheet with data, opened read-only with the values Excel last
calculated (``data_only``); dates become ISO text (``2026-06-03``) and are read as dates whatever
the layout's date format; numbers keep their digits. The archive is checked against zip bombs
before it is opened.

Both give a ``Table`` of every non-empty row (cells trimmed) with the row's number in the file —
a ``Layout`` (column roles, date format, sign convention, rows to skip) turns it into lines.
Limits: 25 MB (A-06) and ``MAX_ROWS`` rows.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import PurePath

from numo9.files.models import MAX_FILE_SIZE
from numo9.imports.parser import detect_encoding, xlsx_text

from . import errors
from .errors import StatementError
from .layout import Table, TableRow
from .ofx import looks_like_ofx, parse_ofx
from .source import ParsedStatement, set_parser

MAX_ROWS = 100_000
MAX_COLUMNS = 200
MAX_XLSX_UNCOMPRESSED = 400 * 1024 * 1024
MAX_XLSX_MEMBERS = 10_000
DELIMITERS = (",", ";", "\t", "|")
OFX_FORMATS = frozenset({"ofx", "qfx", "qbo"})
ZIP_MAGIC = b"PK\x03\x04"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

__all__ = ["detect_encoding", "parse_statement"]


def extension(filename: str) -> str:
    return PurePath(filename or "").suffix.lower().lstrip(".")


def parse_statement(data: bytes, filename: str, *, last4: str = "") -> ParsedStatement:
    """``data`` (the whole file) read as a statement; ``StatementError`` when it can't be."""
    if len(data) > MAX_FILE_SIZE:
        raise StatementError(
            errors.FILE_TOO_LARGE, name=filename, max=MAX_FILE_SIZE // (1024 * 1024)
        )
    if not data.strip().strip(b"\xef\xbb\xbf").strip():
        raise StatementError(errors.FILE_EMPTY, name=filename)
    ext = extension(filename)
    if data.startswith(OLE_MAGIC) or ext == "xls":
        raise StatementError(errors.FILE_LEGACY_XLS, name=filename)
    if looks_like_ofx(data):
        return parse_ofx(data, filename, ext if ext in OFX_FORMATS else "ofx", last4=last4)
    if ext in OFX_FORMATS:
        raise StatementError(errors.OFX_NO_STATEMENT, name=filename)
    if data.startswith(ZIP_MAGIC):
        return parse_xlsx(data, filename)
    if b"\x00" in data[:65536] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise StatementError(errors.FILE_TYPE, name=filename)
    return parse_csv(data, filename)


# ---- CSV ---------------------------------------------------------------------------------------


def sniff_delimiter(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()][:50]
    best, best_score = ",", (0, 0)
    for delimiter in DELIMITERS:
        widths = [len(next(csv.reader([line], delimiter=delimiter), [])) for line in lines]
        widths = [w for w in widths if w > 1]
        if not widths:
            continue
        common = max(set(widths), key=widths.count)
        score = (widths.count(common), common)
        if score > best_score:
            best, best_score = delimiter, score
    return best


def _table_rows(records: list[list[str]], filename: str, first: int = 1) -> list[TableRow]:
    rows: list[TableRow] = []
    for number, record in enumerate(records, start=first):
        cells = tuple(cell.strip() for cell in record)
        if not any(cells):
            continue
        if len(cells) > MAX_COLUMNS:
            raise StatementError(errors.FILE_TOO_MANY_COLUMNS, name=filename, max=MAX_COLUMNS)
        rows.append(TableRow(number, cells))
        if len(rows) > MAX_ROWS + 20:
            raise StatementError(errors.FILE_TOO_MANY_LINES, name=filename, max=MAX_ROWS)
    return rows


def parse_csv(data: bytes, filename: str) -> ParsedStatement:
    encoding = detect_encoding(data)
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as exc:  # pragma: no cover - the cp1252 fallback decodes nearly all
        raise StatementError(errors.FILE_UNREADABLE, name=filename) from exc
    if "\x00" in text:
        raise StatementError(errors.FILE_TYPE, name=filename)
    delimiter = sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        records = list(reader)
    except csv.Error as exc:
        raise StatementError(
            errors.FILE_MALFORMED, name=filename, row=reader.line_num, reason=str(exc)
        ) from exc
    rows = _table_rows(records, filename)
    if not rows:
        raise StatementError(errors.FILE_EMPTY, name=filename)
    return ParsedStatement(
        format="csv", encoding=encoding, delimiter=delimiter, table=Table(tuple(rows))
    )


# ---- XLSX --------------------------------------------------------------------------------------


def _check_archive(data: bytes, filename: str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise StatementError(errors.FILE_UNREADABLE, name=filename) from exc
    if "xl/workbook.xml" not in {member.filename for member in members}:
        raise StatementError(errors.FILE_TYPE, name=filename)
    if (
        len(members) > MAX_XLSX_MEMBERS
        or sum(member.file_size for member in members) > MAX_XLSX_UNCOMPRESSED
    ):
        raise StatementError(
            errors.FILE_TOO_LARGE, name=filename, max=MAX_FILE_SIZE // (1024 * 1024)
        )


def parse_xlsx(data: bytes, filename: str) -> ParsedStatement:
    from openpyxl import load_workbook

    _check_archive(data, filename)
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises many types for damaged files
        raise StatementError(errors.FILE_UNREADABLE, name=filename) from exc
    try:
        for worksheet in workbook.worksheets:
            if worksheet.sheet_state != "visible":
                continue
            records = [
                [xlsx_text(value) for value in values]
                for values in worksheet.iter_rows(values_only=True)
            ]
            rows = _table_rows(records, filename, first=worksheet.min_row or 1)
            if rows:
                return ParsedStatement(format="xlsx", table=Table(tuple(rows), iso_dates=True))
    finally:
        workbook.close()
    raise StatementError(errors.FILE_EMPTY, name=filename)


set_parser(parse_statement)
