"""Bank statement import (F-02): files → statement lines, without duplicates.

The pieces, in the order a file goes through them:

- ``source`` — the ``BankStatementSource`` interface (``fetch_lines()``, ``source_name``) and
  ``FileStatementSource``, which turns an uploaded file into normalised ``RawLine`` objects
  (F-02-T03). Numo9's own banking app (W-02) plugs in as another source;
- ``layout`` — how a CSV / XLSX statement is read: the role of each column, the date format, the
  sign convention and the rows to skip (F-02-T03 / T05);
- ``ofx`` / ``parsers`` — OFX, QFX, QBO, CSV and XLSX parsers (F-02-T04);
- ``mappings`` — saved mappings, the built-in Canadian bank layouts and the auto-detection
  (F-02-T05 / T06);
- ``fingerprint`` — one fingerprint per line, identical lines on the same day kept apart by a
  sequence counter (F-02-T07);
- ``service`` — preview (dry run), commit, undo (F-02-T08 – T10);
- ``errors`` — the message catalogue: every problem names the row and the fix (F-02-T15).
"""
