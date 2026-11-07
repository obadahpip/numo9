"""check_glossary — banned-term lint over en-CA i18n catalogues (S-01-T10; gaps #31, #38).

    python backend/tools/check_glossary.py            # default catalogue locations
    python backend/tools/check_glossary.py --json path/en-CA.json --po path/django.po

Scans the en-CA frontend catalogue values and the en_CA backend gettext msgids/msgstrs for
terms listed in backend/tools/glossary.toml. Exit code 1 if any banned term is found.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # executed as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.i18n_catalogs import (
    BACKEND_LOCALE_DIR,
    FRONTEND_MESSAGES_DIR,
    SOURCE_BACKEND_LOCALE,
    SOURCE_FRONTEND_LOCALE,
    load_json_catalogue,
    load_po,
)

GLOSSARY_FILE = Path(__file__).with_name("glossary.toml")


@dataclass(frozen=True)
class BannedTerm:
    term: str
    pattern: re.Pattern[str]
    exclude: re.Pattern[str] | None
    use: str
    gap: str
    allow: frozenset[str]

    def matches(self, text: str) -> list[str]:
        found = []
        for match in self.pattern.finditer(text):
            if self.exclude and self.exclude.fullmatch(match.group(0)):
                continue
            found.append(match.group(0))
        return found


def load_glossary(path: Path = GLOSSARY_FILE) -> list[BannedTerm]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    terms = []
    for entry in data.get("banned", []):
        flags = 0 if entry.get("case_sensitive", False) else re.IGNORECASE
        exclude = entry.get("exclude")
        terms.append(
            BannedTerm(
                term=entry["term"],
                pattern=re.compile(entry["pattern"], flags),
                exclude=re.compile(exclude, flags) if exclude else None,
                use=entry["use"],
                gap=entry.get("gap", ""),
                allow=frozenset(entry.get("allow", [])),
            )
        )
    return terms


def scan(texts: dict[str, str], terms: list[BannedTerm], origin: str) -> list[str]:
    problems = []
    for key, text in sorted(texts.items()):
        for term in terms:
            if key in term.allow:
                continue
            for hit in term.matches(text):
                problems.append(
                    f"{origin}: {key!r}: banned term '{hit}' ({term.term}) — use {term.use}"
                    + (f" [{term.gap}]" if term.gap else "")
                )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--json",
        type=Path,
        action="append",
        help=f"frontend catalogue (default: frontend/messages/{SOURCE_FRONTEND_LOCALE}.json)",
    )
    parser.add_argument(
        "--po",
        type=Path,
        action="append",
        help=f"gettext catalogue (default: backend/locale/{SOURCE_BACKEND_LOCALE}/…/django.po)",
    )
    parser.add_argument("--glossary", type=Path, default=GLOSSARY_FILE)
    args = parser.parse_args(argv)

    json_files = args.json or [FRONTEND_MESSAGES_DIR / f"{SOURCE_FRONTEND_LOCALE}.json"]
    po_files = args.po or [BACKEND_LOCALE_DIR / SOURCE_BACKEND_LOCALE / "LC_MESSAGES" / "django.po"]
    terms = load_glossary(args.glossary)

    problems: list[str] = []
    scanned = 0
    for path in json_files:
        texts = load_json_catalogue(path)
        scanned += len(texts)
        problems += scan(texts, terms, path.name)
    for path in po_files:
        if not path.exists():
            continue
        texts = {}
        for entry in load_po(path):
            texts[entry.key] = " ".join([entry.msgid, entry.msgid_plural or "", *entry.msgstr])
        scanned += len(texts)
        problems += scan(texts, terms, f"{path.parent.parent.name}/{path.name}")

    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    print(f"check_glossary: {scanned} messages scanned, {len(problems)} banned term(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
