"""check_i18n — missing-key gate for en-CA / fr-CA catalogues (S-01-T10).

Frontend:  compares `formatjs extract` output with frontend/messages/{en-CA,fr-CA}.json
    python backend/tools/check_i18n.py frontend --extracted frontend/.i18n/extracted.json
    python backend/tools/check_i18n.py frontend --extracted ... --write   # add missing keys

Backend:   compares freshly generated gettext catalogues (makemessages) with the committed ones
    python backend/tools/check_i18n.py backend --committed /tmp/locale --generated backend/locale

Rules
- Every message id is a dotted lower-camel key (e.g. `home.title`), never a generated hash.
- Every id exists in BOTH en-CA and fr-CA; en-CA holds the source text (= defaultMessage).
- fr-CA may hold the English text as a placeholder until Phase 6 (reported, not an error).
- Backend: every msgid found in source is present in the committed en_CA and fr_CA .po files.
Exit code 1 on any error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # executed as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.i18n_catalogs import (
    BACKEND_LOCALES,
    FRONTEND_LOCALES,
    FRONTEND_MESSAGES_DIR,
    SOURCE_FRONTEND_LOCALE,
    load_json_catalogue,
    load_po,
    write_json_catalogue,
)

MESSAGE_ID = re.compile(r"^[a-z][a-zA-Z0-9]*(\.[a-z][a-zA-Z0-9]*)+$")


def check_frontend(extracted_path: Path, messages_dir: Path, write: bool) -> list[str]:
    extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
    source = {msg_id: str(body["defaultMessage"]) for msg_id, body in extracted.items()}
    catalogues = {
        locale: load_json_catalogue(messages_dir / f"{locale}.json") for locale in FRONTEND_LOCALES
    }
    errors: list[str] = []

    for msg_id in sorted(source):
        if not MESSAGE_ID.match(msg_id):
            errors.append(f"{msg_id}: id must be a dotted lower-camel key like 'home.title'")

    en = catalogues[SOURCE_FRONTEND_LOCALE]
    for msg_id, default in sorted(source.items()):
        for locale, catalogue in catalogues.items():
            if msg_id not in catalogue:
                if write:
                    catalogue[msg_id] = default  # fr-CA placeholder = English until Phase 6
                else:
                    errors.append(f"{msg_id}: missing in {locale}.json")
        if msg_id in en and en[msg_id] != default:
            errors.append(
                f"{msg_id}: en-CA.json has {en[msg_id]!r} but source defaultMessage is {default!r}"
            )

    for locale, catalogue in catalogues.items():
        if locale == SOURCE_FRONTEND_LOCALE:
            continue
        for msg_id in sorted(set(catalogue) - set(en)):
            errors.append(f"{msg_id}: in {locale}.json but not in en-CA.json")

    if write:
        for locale, catalogue in catalogues.items():
            write_json_catalogue(messages_dir / f"{locale}.json", catalogue)

    unused = sorted(set(en) - set(source))
    for msg_id in unused:
        print(f"warning: {msg_id}: in catalogues but not used in source", file=sys.stderr)
    fr = catalogues["fr-CA"]
    placeholders = sum(1 for k in source if fr.get(k) == en.get(k) and k in fr)
    print(
        f"frontend: {len(source)} messages; fr-CA placeholders (untranslated): {placeholders}; "
        f"unused: {len(unused)}"
    )
    return errors


def check_backend(committed_dir: Path, generated_dir: Path) -> list[str]:
    errors: list[str] = []
    key_sets: dict[str, set[str]] = {}
    for locale in BACKEND_LOCALES:
        rel = Path(locale) / "LC_MESSAGES" / "django.po"
        generated_file, committed_file = generated_dir / rel, committed_dir / rel
        generated = {e.key for e in load_po(generated_file)} if generated_file.exists() else set()
        if not committed_file.exists():
            if generated:
                errors.append(f"{rel}: not committed (run `make i18n`)")
            key_sets[locale] = set()
            continue
        committed = {e.key for e in load_po(committed_file)}
        key_sets[locale] = committed
        for key in sorted(generated - committed):
            errors.append(f"{rel}: missing msgid {key!r} (run `make i18n`)")
        for key in sorted(committed - generated):
            print(f"warning: {rel}: msgid {key!r} no longer in source", file=sys.stderr)
    en, fr = (key_sets[locale] for locale in BACKEND_LOCALES)
    for key in sorted(en ^ fr):
        where = "en_CA" if key in en else "fr_CA"
        errors.append(f"msgid {key!r} only in {where} catalogue")
    print(f"backend: {len(en)} msgids in en_CA, {len(fr)} in fr_CA")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="side", required=True)
    fe = sub.add_parser("frontend")
    fe.add_argument("--extracted", type=Path, required=True)
    fe.add_argument("--messages", type=Path, default=FRONTEND_MESSAGES_DIR)
    fe.add_argument("--write", action="store_true", help="add missing keys to the catalogues")
    be = sub.add_parser("backend")
    be.add_argument("--committed", type=Path, required=True)
    be.add_argument("--generated", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.side == "frontend":
        errors = check_frontend(args.extracted, args.messages, args.write)
    else:
        errors = check_backend(args.committed, args.generated)

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        print(f"check_i18n: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("check_i18n: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
