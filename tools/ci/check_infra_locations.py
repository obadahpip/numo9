"""ADR-0002 fitness check: infra/ may name only the Hetzner locations hel1 and fsn1.

Fails (exit 1) when a text file under ``infra/`` references
  - a Hetzner location other than ``hel1`` (workloads) or ``fsn1`` (backup copy) — in a
    ``location`` / ``region`` / ``datacenter`` value or an Object Storage endpoint, or
  - a Hetzner network zone other than ``eu-central``, or
  - any AWS region (ADR-0002 superseded the AWS decision of ADR-0001).

A line may opt out with the marker ``adr-0002: allow`` (only for negative tests that prove a
foreign location is rejected).

Usage:  python tools/ci/check_infra_locations.py [ROOT ...]     (default: infra)
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

ALLOWED_LOCATIONS = frozenset({"hel1", "fsn1"})
ALLOWED_NETWORK_ZONES = frozenset({"eu-central"})
ALLOW_MARKER = "adr-0002: allow"

HETZNER_LOCATIONS = r"(?:fsn1|nbg1|hel1|ash|hil|sin)"
# location = "nbg1" · region: hel1 · datacenter = "ash-dc1" · --location nbg1
LOCATION_VALUE_RE = re.compile(
    r"\b(?:location|region|datacenter|datacentre)\b[\"']?\s*(?:=|:|\s)\s*[\"']?"
    rf"(?P<loc>{HETZNER_LOCATIONS})(?:-dc\d+)?\b",
    re.IGNORECASE,
)
# https://nbg1.your-objectstorage.com
ENDPOINT_RE = re.compile(rf"\b(?P<loc>{HETZNER_LOCATIONS})\.your-objectstorage\.com\b")
NETWORK_ZONE_RE = re.compile(
    r"\bnetwork_zone\b\s*=\s*\"(?P<zone>eu-central|us-east|us-west|ap-southeast)\""
)
AWS_REGION_RE = re.compile(
    r"\b(?P<region>(?:us|eu|ap|sa|ca|me|af|il|mx|cn)-(?:gov-|iso-|isob-)?"
    r"(?:north|south|east|west|central|northeast|northwest|southeast|southwest)-\d+)[a-z]?\b"
)

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


def line_violations(line: str) -> list[str]:
    """Return human-readable reasons why this line breaks ADR-0002 (empty list = fine)."""
    if ALLOW_MARKER in line:
        return []
    reasons: list[str] = []
    for regex in (LOCATION_VALUE_RE, ENDPOINT_RE):
        for match in regex.finditer(line):
            loc = match.group("loc").lower()
            if loc not in ALLOWED_LOCATIONS:
                reasons.append(f"Hetzner location '{loc}'")
    for match in NETWORK_ZONE_RE.finditer(line):
        if match.group("zone") not in ALLOWED_NETWORK_ZONES:
            reasons.append(f"network zone '{match.group('zone')}'")
    for match in AWS_REGION_RE.finditer(line):
        reasons.append(f"AWS region '{match.group('region')}'")
    return reasons


def find_violations(roots: Iterable[Path]) -> list[tuple[Path, int, str]]:
    """Return (file, line number, reason) for every reference ADR-0002 does not allow."""
    violations: list[tuple[Path, int, str]] = []
    for path in iter_files(roots):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            violations.extend((path, lineno, reason) for reason in line_violations(line))
    return violations


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] or [Path("infra")]
    missing = [r for r in roots if not r.exists()]
    if missing:
        print(f"check_infra_locations: path not found: {', '.join(map(str, missing))}")
        return 2
    violations = find_violations(roots)
    for path, lineno, reason in violations:
        print(f"{path}:{lineno}: {reason} is not allowed by ADR-0002")
    if violations:
        allowed = ", ".join(sorted(ALLOWED_LOCATIONS))
        print(f"\n{len(violations)} violation(s). Allowed Hetzner locations: {allowed}.")
        return 1
    print("check_infra_locations: OK (only hel1 / fsn1, network zone eu-central)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
