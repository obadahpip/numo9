"""B-03-T02 — file parser: CSV with charset detection, XLSX values (read-only).

Acceptance: three encodings parse identically (UTF-8, UTF-8 with BOM, Windows-1252), here also
UTF-16 and the same data as an XLSX file. Also: delimiters (comma, semicolon, tab), quoted cells
with delimiters and line breaks, formulas give their cached values, numbers/dates/booleans as text,
hidden sheets skipped, header rules (first non-empty row, unique, unnamed columns with data), row
numbers, and the refusals (empty, too large, legacy .xls, wrong type, damaged archive, zip bomb).
"""

from __future__ import annotations

import codecs
import datetime as dt
import io
import re
import zipfile
from decimal import Decimal

import pytest
from openpyxl import Workbook

from numo9.imports import parser
from numo9.imports.parser import ImportFileError, column_letter, parse_file, xlsx_text

HEADERS = ["Nom", "Courriel", "Province", "Code postal", "Solde"]
ROWS = [
    ["Érable Café", "info@erable.ca", "QC", "H2X 1Y4", "1 250,00"],
    ["Boulangerie Tremblay", "bt@tremblay.qc.ca", "QC", "G1R 2J6", "0"],
    ["Château Fontenac — Œuvres", "", "ON", "M5V 2T6", "-12,50"],
    ["Ça coûte 5 € (rabais)", "noël@exemple.ca", "NB", "E1C 4X6", ""],
]


def csv_text(delimiter: str = ",") -> str:
    lines = [delimiter.join(HEADERS)]
    for row in ROWS:
        lines.append(delimiter.join(f'"{cell}"' if delimiter in cell else cell for cell in row))
    return "\r\n".join(lines) + "\r\n"


def expected_rows() -> list[tuple[str, ...]]:
    return [tuple(row) for row in ROWS]


def rows_of(parsed: parser.ParsedFile) -> list[tuple[str, ...]]:
    return [row.cells for row in parsed.sheet.rows]


def xlsx_bytes(build: object) -> bytes:
    workbook = Workbook()
    build(workbook)  # type: ignore[operator]
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ---- encodings (acceptance) -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("encoded", "encoding"),
    [
        (csv_text().encode("utf-8"), "utf-8"),
        (codecs.BOM_UTF8 + csv_text().encode("utf-8"), "utf-8-sig"),
        (csv_text().encode("cp1252"), "cp1252"),
        (csv_text().encode("utf-16"), "utf-16"),
    ],
    ids=["utf-8", "utf-8-bom", "windows-1252", "utf-16"],
)
def test_every_encoding_parses_identically(encoded: bytes, encoding: str) -> None:
    parsed = parse_file(encoded, "clients.csv")
    assert parsed.format == "csv"
    assert parsed.encoding == encoding
    assert parsed.sheet.headers == tuple(HEADERS)
    assert rows_of(parsed) == expected_rows()


def test_the_bom_never_reaches_the_first_header() -> None:
    parsed = parse_file(codecs.BOM_UTF8 + b"Nom,Courriel\nA,a@b.ca\n", "c.csv")
    assert parsed.sheet.headers == ("Nom", "Courriel")


def test_windows_1252_specific_characters_survive() -> None:
    # Bytes 0x80-0x9F are printable in Windows-1252 (€ — Œ ’) and invalid in ISO-8859-1 text.
    data = "Nom\n“Œuvres” d’art — 5 €\n".encode("cp1252")
    parsed = parse_file(data, "c.csv")
    assert parsed.encoding == "cp1252"
    assert rows_of(parsed) == [("“Œuvres” d’art — 5 €",)]


def test_detect_encoding_falls_back_to_windows_1252() -> None:
    assert parser.detect_encoding("é".encode("cp1252")) in {"cp1252", "latin_1", "iso8859_15"}
    assert parser.detect_encoding(b"plain ascii") == "utf-8"


# ---- delimiters and quoting --------------------------------------------------------------------


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_delimiter_is_sniffed(delimiter: str) -> None:
    parsed = parse_file(csv_text(delimiter).encode("utf-8"), "c.csv")
    assert parsed.delimiter == delimiter
    assert rows_of(parsed) == expected_rows()


def test_quoted_cells_keep_delimiters_and_line_breaks() -> None:
    data = b'Nom,Adresse\n"Nord, Ltd.","12 rue Principale\nApp. 4"\nSud,1 King St\n'
    parsed = parse_file(data, "c.csv")
    assert rows_of(parsed) == [("Nord, Ltd.", "12 rue Principale\nApp. 4"), ("Sud", "1 King St")]
    assert [row.number for row in parsed.sheet.rows] == [2, 3]


def test_single_column_file() -> None:
    parsed = parse_file(b"Name\nAlpha\nBeta\n", "c.csv")
    assert parsed.sheet.headers == ("Name",)
    assert rows_of(parsed) == [("Alpha",), ("Beta",)]


# ---- header and row rules ----------------------------------------------------------------------


def test_header_is_the_first_non_empty_row_and_row_numbers_follow_the_file() -> None:
    data = b",,\n,,\nName,Email,Code\nA,a@x.ca,1\n,,\nB,,2\n"
    sheet = parse_file(data, "c.csv").sheet
    assert sheet.header_row == 3
    assert sheet.headers == ("Name", "Email", "Code")
    assert [(row.number, row.cells) for row in sheet.rows] == [
        (4, ("A", "a@x.ca", "1")),
        (6, ("B", "", "2")),
    ]


def test_cells_and_headers_are_trimmed_and_ragged_rows_padded() -> None:
    sheet = parse_file(b" Name , Email \n  A  \nB, b@x.ca \n", "c.csv").sheet
    assert sheet.headers == ("Name", "Email")
    assert [row.cells for row in sheet.rows] == [("A", ""), ("B", "b@x.ca")]


def test_a_column_with_data_but_no_header_is_named_after_its_letter() -> None:
    sheet = parse_file(b"Name,,Email\nA,secret,a@x.ca\nB,,\n", "c.csv").sheet
    assert sheet.headers == ("Name", "Column B", "Email")
    assert sheet.rows[0].as_dict(sheet.headers) == {
        "Name": "A",
        "Column B": "secret",
        "Email": "a@x.ca",
    }


def test_extra_cells_beyond_the_header_are_kept_under_a_letter_name() -> None:
    sheet = parse_file(b"Name\nA,overflow\n", "c.csv").sheet
    assert sheet.headers == ("Name", "Column B")
    assert sheet.rows[0].cells == ("A", "overflow")


def test_trailing_empty_columns_are_dropped() -> None:
    sheet = parse_file(b"Name,Email,,,\nA,a@x.ca,,,\n", "c.csv").sheet
    assert sheet.headers == ("Name", "Email")


def test_duplicate_header_is_refused_naming_both_columns() -> None:
    with pytest.raises(ImportFileError) as error:
        parse_file(b"Email,Name,email\nx,y,z\n", "c.csv")
    assert error.value.code == "imports.file.duplicate_header"
    assert error.value.params == {"first": "A", "second": "C", "sheet": "c", "header": "email"}


def test_samples_are_the_first_non_empty_values() -> None:
    sheet = parse_file(b"Name,Email\nA,\nB,b@x.ca\nC,c@x.ca\nD,d@x.ca\nE,e@x.ca\n", "c.csv").sheet
    assert sheet.samples("Email") == ["b@x.ca", "c@x.ca", "d@x.ca"]
    assert sheet.samples("Name", 2) == ["A", "B"]


def test_column_letters() -> None:
    assert [column_letter(i) for i in (0, 1, 25, 26, 27, 51, 52, 701, 702)] == [
        "A",
        "B",
        "Z",
        "AA",
        "AB",
        "AZ",
        "BA",
        "ZZ",
        "AAA",
    ]


# ---- XLSX --------------------------------------------------------------------------------------


def test_xlsx_parses_like_the_csv() -> None:
    def build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.title = "Clients"
        sheet.append(HEADERS)
        for row in ROWS:
            sheet.append([cell or None for cell in row])

    parsed = parse_file(xlsx_bytes(build), "clients.xlsx")
    assert parsed.format == "xlsx"
    assert parsed.encoding == ""
    assert parsed.sheet.name == "Clients"
    assert parsed.sheet.headers == tuple(HEADERS)
    assert rows_of(parsed) == expected_rows()
    csv_parsed = parse_file(csv_text().encode("cp1252"), "clients.csv")
    assert rows_of(parsed) == rows_of(csv_parsed)


def test_xlsx_values_as_text() -> None:
    def build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.append(["Int", "Float", "Date", "DateTime", "Bool", "Decimal", "Big"])
        sheet.append(
            [42, 0.1, dt.date(2026, 3, 31), dt.datetime(2026, 3, 31, 14, 30), True, 1234.5, 1e20]
        )
        sheet.append([7.0, -0.25, dt.datetime(2026, 1, 1), None, False, 3, 12345678901234])

    rows = rows_of(parse_file(xlsx_bytes(build), "v.xlsx"))
    assert rows == [
        ("42", "0.1", "2026-03-31", "2026-03-31T14:30:00", "TRUE", "1234.5", "1" + "0" * 20),
        ("7", "-0.25", "2026-01-01", "", "FALSE", "3", "12345678901234"),
    ]


def test_xlsx_text_helper() -> None:
    assert xlsx_text(None) == ""
    assert xlsx_text(Decimal("12.50")) == "12.50"
    assert xlsx_text(dt.time(9, 5)) == "09:05:00"
    assert xlsx_text("  kept as is  ") == "  kept as is  "


def _with_cached_formula(data: bytes) -> bytes:
    """Rewrite sheet1 so B2 holds a formula with the value Excel would have cached (10)."""
    source = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                text = content.decode()
                text, count = re.subn(
                    r'<c r="B2"[^>]*>.*?</c>', '<c r="B2"><f>A2*2</f><v>10</v></c>', text
                )
                assert count == 1
                content = text.encode()
            target.writestr(item, content)
    return out.getvalue()


def test_xlsx_formula_gives_its_cached_value_never_the_formula() -> None:
    def build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.append(["Qty", "Total"])
        sheet.append([5, "placeholder"])

    rows = rows_of(parse_file(_with_cached_formula(xlsx_bytes(build)), "f.xlsx"))
    assert rows == [("5", "10")]


def test_xlsx_formula_without_cached_value_is_empty() -> None:
    def build(workbook: Workbook) -> None:
        sheet = workbook.active
        sheet.append(["Qty", "Total"])
        sheet.append([5, "=A2*2"])  # openpyxl stores the formula without a value

    assert rows_of(parse_file(xlsx_bytes(build), "f.xlsx")) == [("5", "")]


def test_xlsx_every_visible_sheet_and_hidden_skipped() -> None:
    def build(workbook: Workbook) -> None:
        contacts = workbook.active
        contacts.title = "Contacts"
        contacts.append(["External ID", "Name"])
        contacts.append(["OLD-1", "Nord"])
        people = workbook.create_sheet("People")
        people.append(["Contact ref", "First name"])
        people.append(["OLD-1", "Anne"])
        people.append(["OLD-1", "Luc"])
        hidden = workbook.create_sheet("Lists")
        hidden.append(["Province"])
        hidden.sheet_state = "hidden"
        workbook.create_sheet("Empty")

    parsed = parse_file(xlsx_bytes(build), "c.xlsx")
    assert [sheet.name for sheet in parsed.sheets] == ["Contacts", "People"]
    assert [row.cells for row in parsed.sheets[1].rows] == [("OLD-1", "Anne"), ("OLD-1", "Luc")]


# ---- refusals ----------------------------------------------------------------------------------


def code(data: bytes, filename: str) -> str | None:
    with pytest.raises(ImportFileError) as error:
        parse_file(data, filename)
    return error.value.code


def test_empty_files_are_refused() -> None:
    assert code(b"", "c.csv") == "imports.file.empty"
    assert code(b" \r\n,,\r\n", "c.csv") == "imports.file.empty"
    assert code(xlsx_bytes(lambda workbook: None), "c.xlsx") == "imports.file.empty"


def test_too_large_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parser, "MAX_FILE_SIZE", 10)
    assert code(b"Name\n" + b"x" * 20, "c.csv") == "imports.file.too_large"


def test_too_many_rows_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parser, "MAX_ROWS", 2)
    assert code(b"Name\na\nb\nc\n", "c.csv") == "imports.file.too_many_rows"


def test_legacy_xls_is_refused_with_advice() -> None:
    assert code(parser.OLE_MAGIC + b"\x00" * 100, "old.xls") == "imports.file.legacy_xls"
    assert code(b"Name\nA\n", "renamed.xls") == "imports.file.legacy_xls"


def test_other_file_types_are_refused() -> None:
    assert code(b"%PDF-1.7 binary", "contacts-2026.pdf") == "imports.file.type"
    assert code(b"Name\x00\x01\x02", "c.csv") == "imports.file.type"
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr("word/document.xml", "<w/>")
    assert code(zipped.getvalue(), "letter.docx") == "imports.file.type"
    assert code(zipped.getvalue(), "letter.xlsx") == "imports.file.type"


def test_damaged_xlsx_is_refused() -> None:
    assert code(parser.ZIP_MAGIC + b"garbage", "c.xlsx") == "imports.file.unreadable"


def test_zip_bomb_is_refused_before_opening(monkeypatch: pytest.MonkeyPatch) -> None:
    def build(workbook: Workbook) -> None:
        workbook.active.append(["Name"])

    monkeypatch.setattr(parser, "MAX_XLSX_UNCOMPRESSED", 100)
    assert code(xlsx_bytes(build), "c.xlsx") == "imports.file.too_large"


def test_messages_say_what_to_do() -> None:
    with pytest.raises(ImportFileError) as error:
        parse_file(b"%PDF", "contacts-2026.pdf")
    assert str(error.value.message % error.value.params) == (
        "contacts-2026.pdf isn't a CSV or Excel file. Save it as .csv or .xlsx and try again."
    )
