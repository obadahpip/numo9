# Spreadsheet imports (B-03)

| | |
|---|---|
| **Deliverable** | B-03 · Import/export, Phase 0 (component B — Contacts); the framework is shared |
| **Branch** | `feature/B-03-contact-import` |
| **Code** | `backend/numo9/imports/` (parser, mapping) |
| **Wireframes** | [Phase 0 wireframes §17–20](../design/wireframes.md#17-import-contacts-step-1-upload-b-03-t01) |
| **Depends on** | A-01 (tenancy, row-level security), A-04 (audit), A-06 (25 MB file limit), A-08 (apply job) |
| **Used by** | B-03 contacts import, C-01-T13 chart-of-accounts import/export, later every list that imports (items, opening balances, bank rules…) |
| **Gaps** | gap-15 (CSV + XLSX, column mapping, dry run), gap-21 (stable matching, non-destructive updates) |

What Xero ships (xero_teardown §2.6): CSV only, headers must match its template exactly, no
mapping, no dry run; matching on the contact name, so a renamed contact is imported as a duplicate.
Numo9 reads CSV and XLSX in any encoding, maps any headers (English or French) to fields, and
shows what an import would do before anything is saved.

## File parser (B-03-T02)

`numo9.imports.parser.parse_file(data, filename) → ParsedFile` turns an uploaded file into sheets
of text cells. Everything downstream (mapping, normaliser, matcher, dry run) works on text, so a
CSV and an XLSX copy of the same data behave the same.

| | CSV | XLSX |
|---|---|---|
| Recognised by | Anything that isn't a ZIP or OLE file (`.csv`, `.txt`, `.tsv` or no extension) | ZIP containing `xl/workbook.xml` (`.xlsx`, `.xlsm`) |
| Encoding | BOM first (UTF-8, UTF-16 LE/BE); strict UTF-8; else `charset-normalizer` among Windows-1252, ISO-8859-1/15, Mac Roman; Windows-1252 if inconclusive | — |
| Delimiter | Sniffed: `,` `;` tab `|` | — |
| Sheets | One, named after the file | Every visible worksheet (hidden ones skipped) |
| Values | As written | Values only (`data_only=True`): a formula gives Excel's cached value; numbers without a trailing `.0`; dates ISO `YYYY-MM-DD` (`THH:MM:SS` when not midnight); `TRUE`/`FALSE` |

Rules for both: the header row is the first row with any value; headers and cells are trimmed;
header names are unique per sheet (case-insensitive — they are the keys of saved mappings); a
column with data but no header is named "Column F" so nothing is dropped silently; trailing empty
columns and empty rows are skipped; each row keeps its number in the file for error reports.

Limits and refusals (`ImportFileError`, a `ValidationError` with a stable code):

| Code | When |
|---|---|
| `imports.file.empty` | No bytes, only blank rows, or a workbook without a visible sheet with data |
| `imports.file.too_large` | Over 25 MB (A-06), or an XLSX that expands beyond 400 MB / 10,000 members (zip bomb) |
| `imports.file.too_many_rows` / `too_many_columns` | Over 100,000 data rows / 200 columns in a sheet |
| `imports.file.legacy_xls` | An old binary `.xls` (advice: save as .xlsx or .csv) |
| `imports.file.type` | Another type (PDF, Word, binary data) |
| `imports.file.unreadable` | A damaged or password-protected workbook |
| `imports.file.duplicate_header` | Two columns with the same name (names both column letters) |
| `imports.file.malformed` | A CSV the reader can't parse (names the line) |

Security: XLSX XML is parsed with `defusedxml` (openpyxl uses it when installed — entity
expansion and external entities are refused); the archive's member count and uncompressed size
are checked before openpyxl opens it; the file is read in memory from the uploaded document, never
executed or written to disk.
