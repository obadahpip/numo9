"""ADR-0001 fitness check: infra/ may name only the Canadian AWS regions.

Fails (exit 1) when any text file under ``infra/`` mentions an AWS region or availability zone
other than ``ca-central-1`` (workloads) or ``ca-west-1`` (backup copies).

A line may opt out with the marker ``adr-0001: allow`` (used only by negative tests that prove a
foreign region is rejected).

Usage:  python tools/ci/check_infra_regions.py [ROOT ...]     (default: infra)
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

ALLOWED_REGIONS = frozenset({"ca-central-1", "ca-west-1"})

# AWS region names, optionally followed by an availability-zone letter (ca-central-1a).
REGION_RE = re.compile(
    r"\b((?:us|eu|ap|sa|ca|me|af|il|mx|cn)-(?:gov-|iso-|isob-)?"
    r"(?:north|south|east|west|central|northeast|northwest|southeast|southwest)-\d+)[a-z]?\b"
)

ALLOW_MARKER = "adr-0001: allow"

SKIP_DIRS = frozenset({".terraform", ".git", "node_modules", "__pycache__"})
SKIP_SUFFIXES = frozenset({".zip", ".png", ".jpg", ".gz", ".tfstate", ".tfplan"})


def iter_files(roots: Iterable[Path]) -> Iterator[Path]:
    for root in roots:
        if root.is_file():
            yield root
            continue
        for path in sorted(root.rglob("*")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file() and path.suffix not in SKIP_SUFFIXES:
                yield path


def find_violations(roots: Iterable[Path]) -> list[tuple[Path, int, str]]:
    """Return (file, line number, region) for every region outside ALLOWED_REGIONS."""
    violations: list[tuple[Path, int, str]] = []
    for path in iter_files(roots):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if ALLOW_MARKER in line:
                continue
            for match in REGION_RE.finditer(line):
                region = match.group(1)
                if region not in ALLOWED_REGIONS:
                    violations.append((path, lineno, region))
    return violations


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] or [Path("infra")]
    missing = [r for r in roots if not r.exists()]
    if missing:
        print(f"check_infra_regions: path not found: {', '.join(map(str, missing))}")
        return 2
    violations = find_violations(roots)
    for path, lineno, region in violations:
        print(f"{path}:{lineno}: region '{region}' is not allowed by ADR-0001")
    if violations:
        allowed = ", ".join(sorted(ALLOWED_REGIONS))
        print(f"\n{len(violations)} violation(s). Allowed regions: {allowed}.")
        return 1
    print(f"check_infra_regions: OK (only {', '.join(sorted(ALLOWED_REGIONS))} referenced)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
