"""check_glossary — Canadian English glossary lint (S-01-T10, A-10-T15; gaps #31, #38).

    python backend/tools/check_glossary.py            # default locations (below)
    python backend/tools/check_glossary.py --json path/en-CA.json --po path/django.po
    python backend/tools/check_glossary.py --terms    # print the glossary as a Markdown table

Scans, for the terms banned in backend/tools/glossary.toml:
- the en-CA frontend catalogue values and the en_CA backend gettext msgids/msgstrs;
- the string literals of the design system's stories and sample data
  (packages/ui/src/**/*.stories.tsx, fixtures.ts[x]) — the text people read in Storybook and
  the sample data shown in previews (gap-43: Canadian sample data).
The glossary's `[[preferred]]` list names the en-CA terms to use (organisation, cheque, Province,
Postal code, GST/HST, vacation pay). Exit code 1 if any banned term is found.
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
REPO_ROOT = Path(__file__).resolve().parents[2]
UI_SOURCE_DIR = REPO_ROOT / "packages" / "ui" / "src"
UI_SOURCE_GLOBS = ("**/*.stories.tsx", "**/fixtures.ts", "**/fixtures.tsx")

# String literals in TS/TSX: "…", '…' and `…` (template parts between ${…} included).
_LITERAL = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`')
# Text between JSX tags (not after an arrow `=>` or a comparison).
_JSX_TEXT = re.compile(r"(?<![=\-])>([^<>{};=]*[A-Za-z][^<>{};=]*)<")
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
_IMPORT = re.compile(
    r"^(?:import|export)\b[^;]*?\bfrom\s+[\"'][^\"']+[\"'];?", re.MULTILINE | re.DOTALL
)


def source_texts(
    root: Path = UI_SOURCE_DIR, globs: tuple[str, ...] = UI_SOURCE_GLOBS
) -> dict[str, str]:
    """User-visible text of the design system's stories and fixtures, keyed `file:line`."""
    texts: dict[str, str] = {}
    files = sorted({path for pattern in globs for path in root.glob(pattern)})
    for path in files:
        source = path.read_text(encoding="utf-8")
        # Blank out comments and import lines (keeping line numbers): only code text is scanned.
        blank = lambda m: re.sub(r"[^\n]", " ", m.group(0))  # noqa: E731
        source = _IMPORT.sub(blank, _COMMENT.sub(blank, source))
        for pattern in (_LITERAL, _JSX_TEXT):
            for match in pattern.finditer(source):
                text = match.group(1) if match.lastindex else match.group(0)[1:-1]
                if not re.search(r"[A-Za-z]{2}", text):
                    continue
                line = source.count("\n", 0, match.start()) + 1
                shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
                key = f"{shown}:{line}"
                texts[key] = f"{texts[key]} {text}" if key in texts else text
    return texts


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


@dataclass(frozen=True)
class PreferredTerm:
    term: str
    meaning: str
    instead_of: str


def load_preferred(path: Path = GLOSSARY_FILE) -> list[PreferredTerm]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        PreferredTerm(entry["term"], entry["meaning"], entry.get("instead_of", ""))
        for entry in data.get("preferred", [])
    ]


def glossary_markdown(path: Path = GLOSSARY_FILE) -> str:
    rows = ["| Use | Meaning | Instead of |", "|---|---|---|"]
    rows += [f"| {p.term} | {p.meaning} | {p.instead_of} |" for p in load_preferred(path)]
    rows += ["", "| Banned | Use | Gap |", "|---|---|---|"]
    rows += [f"| {t.term} | {t.use} | {t.gap} |" for t in load_glossary(path)]
    return "\n".join(rows)


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
    parser.add_argument(
        "--ui-src",
        type=Path,
        default=UI_SOURCE_DIR,
        help="design-system sources whose stories/fixtures are scanned (default packages/ui/src)",
    )
    parser.add_argument("--no-ui", action="store_true", help="skip the design-system sources")
    parser.add_argument("--terms", action="store_true", help="print the glossary and exit")
    args = parser.parse_args(argv)
    if args.terms:
        print(glossary_markdown(args.glossary))
        return 0

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

    if not args.no_ui and args.ui_src.exists():
        texts = source_texts(args.ui_src)
        scanned += len(texts)
        problems += scan(texts, terms, "packages/ui")

    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    print(f"check_glossary: {scanned} messages scanned, {len(problems)} banned term(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
