"""compile_messages — gettext .po → .mo without GNU gettext (A-10-T14).

    python backend/tools/compile_messages.py              # every backend/locale/*/LC_MESSAGES/*.po
    python backend/tools/compile_messages.py --check      # fail if a .mo is missing or stale

The runtime image and the test run need compiled catalogues; `manage.py compilemessages` needs
GNU msgfmt, which the slim images and the CI backend job don't have. This writes the same GNU
.mo format (translated entries only; fuzzy entries skipped, like msgfmt). The .mo files are build
output and are not committed.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

if __package__ in (None, ""):  # executed as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.i18n_catalogs import parse_po

MAGIC = 0x950412DE
# backend/locale — relative to this file, so it also works in the backend image (/app/locale).
LOCALE_DIR = Path(__file__).resolve().parents[1] / "locale"


def _header(text: str) -> str:
    """The header msgstr (charset, plural forms) of a .po file."""
    match = re.search(r'^msgid ""\s*\nmsgstr ((?:".*"\s*\n?)+)', text, re.MULTILINE)
    if not match:
        return "Content-Type: text/plain; charset=UTF-8\n"
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))
    return "".join(parts).encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")


def _fuzzy_msgids(text: str) -> set[str]:
    fuzzy: set[str] = set()
    for block in re.split(r"\n\s*\n", text):
        if re.search(r"^#,.*\bfuzzy\b", block, re.MULTILINE):
            match = re.search(r'^msgid "((?:[^"\\]|\\.)*)"', block, re.MULTILINE)
            if match and match.group(1):
                fuzzy.add(match.group(1))
    return fuzzy


def compile_po(text: str) -> bytes:
    """GNU .mo bytes for the .po source `text`."""
    fuzzy = _fuzzy_msgids(text)
    messages: dict[bytes, bytes] = {b"": _header(text).encode("utf-8")}
    for entry in parse_po(text):
        if entry.msgid in fuzzy or not all(entry.msgstr):
            continue
        key = (
            entry.msgid if entry.msgid_plural is None else f"{entry.msgid}\x00{entry.msgid_plural}"
        )
        if entry.msgctxt:
            key = f"{entry.msgctxt}\x04{key}"
        messages[key.encode("utf-8")] = "\x00".join(entry.msgstr).encode("utf-8")

    keys = sorted(messages)
    count = len(keys)
    originals_offset = 7 * 4
    translations_offset = originals_offset + count * 8
    data_offset = translations_offset + count * 8
    originals = b""
    translations = b""
    table_o: list[int] = []
    table_t: list[int] = []
    for raw in keys:
        table_o += [len(raw), data_offset + len(originals)]
        originals += raw + b"\x00"
    translations_start = data_offset + len(originals)
    for raw in keys:
        value = messages[raw]
        table_t += [len(value), translations_start + len(translations)]
        translations += value + b"\x00"
    header = struct.pack("<7I", MAGIC, 0, count, originals_offset, translations_offset, 0, 0)
    return (
        header
        + struct.pack(f"<{len(table_o)}I", *table_o)
        + struct.pack(f"<{len(table_t)}I", *table_t)
        + originals
        + translations
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--locale-dir", type=Path, default=LOCALE_DIR)
    parser.add_argument(
        "--check", action="store_true", help="only verify the .mo files are current"
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    stale = []
    for po in sorted(args.locale_dir.glob("*/LC_MESSAGES/*.po")):
        compiled = compile_po(po.read_text(encoding="utf-8"))
        mo = po.with_suffix(".mo")
        if args.check:
            if not mo.exists() or mo.read_bytes() != compiled:
                stale.append(mo)
            continue
        if not mo.exists() or mo.read_bytes() != compiled:
            mo.write_bytes(compiled)
        if not args.quiet:
            print(f"compile_messages: {mo.relative_to(args.locale_dir.parent)}")
    for mo in stale:
        print(f"error: {mo} is missing or out of date", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
