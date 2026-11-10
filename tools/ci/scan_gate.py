"""scan_gate — fail the build on scanner findings not on the justified allow-list (S-03-T09).

    python tools/ci/scan_gate.py validate [--allowlist FILE]
    python tools/ci/scan_gate.py pip-audit REPORT.json [--allowlist FILE]
    python tools/ci/scan_gate.py npm REPORT.json [--min-severity high] [--allowlist FILE]
    python tools/ci/scan_gate.py trivy REPORT.json [--min-severity high] [--allowlist FILE]

Reports are the scanners' JSON output:

- ``pip-audit -f json`` — every known vulnerability fails (pip-audit reports no severity);
- ``pnpm audit --json`` (npm v6 format) — advisories at or above ``--min-severity`` (default high);
- ``trivy image --format json`` — vulnerabilities at or above ``--min-severity`` (default high)
  and every secret Trivy finds in the image.

A finding passes only when ``.security-allowlist.toml`` holds a matching entry (same scanner,
same package, the finding id or one of its aliases — CVE, GHSA, PYSEC) whose justification,
owner and expiry are valid. The allow-list itself is validated on every run: an entry without a
real justification (at least 40 characters, no placeholder), without an owner, already expired or
expiring more than 90 days ahead fails the build, so an accepted risk is re-reviewed at least
every quarter. A missing or unreadable report fails too (a scanner that crashed is not a pass).

Exit codes: 0 pass · 1 findings not allowed or invalid allow-list · 2 unreadable report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCANNERS = ("pip-audit", "npm", "trivy")
SEVERITY_RANK = {
    "info": 0,
    "unknown": 0,
    "low": 1,
    "moderate": 2,
    "medium": 2,
    "high": 3,
    "critical": 4,
}
MIN_JUSTIFICATION = 40
MAX_EXPIRY_DAYS = 90
PLACEHOLDER = re.compile(r"^\s*(todo|tbd|n/?a|none|fixme|-+|\.+|x+)\b", re.IGNORECASE)
DEFAULT_ALLOWLIST = Path(__file__).resolve().parents[2] / ".security-allowlist.toml"


@dataclass(frozen=True)
class Finding:
    scanner: str
    package: str
    version: str
    ids: tuple[str, ...]  # primary id first, then aliases
    severity: str
    title: str = ""

    @property
    def primary(self) -> str:
        return self.ids[0] if self.ids else "?"


@dataclass
class Entry:
    scanner: str
    package: str
    id: str
    justification: str
    owner: str
    expires: dt.date | None
    ticket: str = ""
    index: int = 0
    used: bool = field(default=False, compare=False)

    def matches(self, finding: Finding) -> bool:
        return (
            self.scanner == finding.scanner
            and normalise_package(self.package) == normalise_package(finding.package)
            and self.id.upper() in {i.upper() for i in finding.ids}
        )


class ReportError(Exception):
    """The scanner report is missing or not in the expected format."""


def normalise_package(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def severity_rank(value: str) -> int:
    return SEVERITY_RANK.get(value.strip().lower(), 0)


# ---- allow-list ------------------------------------------------------------------------------


def load_allowlist(path: Path, today: dt.date) -> tuple[list[Entry], list[str]]:
    """Read and validate the allow-list; returns (entries, problems)."""
    if not path.is_file():
        return [], [f"{path.name}: allow-list file not found"]
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        return [], [f"{path.name}: not valid TOML ({exc})"]
    raw = data.get("finding", [])
    if not isinstance(raw, list):
        return [], [f"{path.name}: 'finding' must be an array of tables ([[finding]])"]
    entries: list[Entry] = []
    problems: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for number, item in enumerate(raw, start=1):
        where = f"{path.name} entry #{number}"
        if not isinstance(item, dict):
            problems.append(f"{where}: must be a table")
            continue
        entry_problems: list[str] = []
        scanner = str(item.get("scanner", "")).strip()
        package = str(item.get("package", "")).strip()
        finding_id = str(item.get("id", "")).strip()
        justification = " ".join(str(item.get("justification", "")).split())
        owner = str(item.get("owner", "")).strip()
        expires = item.get("expires")
        unknown = set(item) - {"scanner", "package", "id", "justification", "owner", "expires"}
        unknown -= {"ticket"}
        if unknown:
            entry_problems.append(f"unknown key(s) {sorted(unknown)}")
        if scanner not in SCANNERS:
            entry_problems.append(f"scanner must be one of {', '.join(SCANNERS)}")
        if not package:
            entry_problems.append("package is required")
        if not finding_id:
            entry_problems.append("id is required (CVE, GHSA, PYSEC or Trivy rule id)")
        if len(justification) < MIN_JUSTIFICATION or PLACEHOLDER.match(justification):
            entry_problems.append(
                f"justification must explain why the risk is accepted and how it is mitigated "
                f"(at least {MIN_JUSTIFICATION} characters, no placeholder)"
            )
        if not owner:
            entry_problems.append("owner is required (who re-reviews it)")
        expiry: dt.date | None = None
        if isinstance(expires, dt.datetime):
            expiry = expires.date()
        elif isinstance(expires, dt.date):
            expiry = expires
        else:
            entry_problems.append("expires must be a TOML date, e.g. expires = 2027-01-31")
        if expiry is not None:
            if expiry < today:
                entry_problems.append(f"expired on {expiry.isoformat()} — re-review or remove it")
            elif expiry > today + dt.timedelta(days=MAX_EXPIRY_DAYS):
                entry_problems.append(
                    f"expires {expiry.isoformat()} is more than {MAX_EXPIRY_DAYS} days ahead"
                )
        key = (scanner, normalise_package(package), finding_id.upper())
        if key in seen:
            entry_problems.append("duplicate of an earlier entry")
        seen.add(key)
        if entry_problems:
            problems.extend(f"{where} ({finding_id or '?'}): {p}" for p in entry_problems)
            continue
        entries.append(
            Entry(
                scanner=scanner,
                package=package,
                id=finding_id,
                justification=justification,
                owner=owner,
                expires=expiry,
                ticket=str(item.get("ticket", "")),
                index=number,
            )
        )
    return entries, problems


# ---- report parsers --------------------------------------------------------------------------


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReportError(f"report {path} not found — did the scanner run?") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ReportError(f"report {path} is not JSON ({exc})") from exc


def parse_pip_audit(report: Any) -> list[Finding]:
    if not isinstance(report, dict) or not isinstance(report.get("dependencies"), list):
        raise ReportError("not a pip-audit JSON report (no 'dependencies' list)")
    findings: list[Finding] = []
    for dep in report["dependencies"]:
        for vuln in dep.get("vulns", []) or []:
            ids = (str(vuln.get("id", "")), *(str(a) for a in vuln.get("aliases", []) or []))
            fixes = ", ".join(vuln.get("fix_versions", []) or []) or "no fix released"
            findings.append(
                Finding(
                    scanner="pip-audit",
                    package=str(dep.get("name", "")),
                    version=str(dep.get("version", "")),
                    ids=tuple(i for i in ids if i),
                    severity="unknown",
                    title=f"fix: {fixes}",
                )
            )
    return findings


def parse_npm(report: Any) -> list[Finding]:
    if not isinstance(report, dict) or not isinstance(report.get("advisories"), dict):
        raise ReportError("not a pnpm/npm audit JSON report (no 'advisories' object)")
    findings: list[Finding] = []
    for key, adv in report["advisories"].items():
        ids = [str(adv.get("github_advisory_id") or ""), *(str(c) for c in adv.get("cves") or [])]
        ids.append(str(adv.get("id") or key))
        versions = sorted({str(f.get("version", "")) for f in adv.get("findings", []) or []})
        findings.append(
            Finding(
                scanner="npm",
                package=str(adv.get("module_name", "")),
                version=", ".join(v for v in versions if v),
                ids=tuple(dict.fromkeys(i for i in ids if i)),
                severity=str(adv.get("severity", "unknown")),
                title=str(adv.get("title", "")),
            )
        )
    return findings


def parse_trivy(report: Any) -> list[Finding]:
    if not isinstance(report, dict) or "Results" not in report:
        raise ReportError("not a Trivy JSON report (no 'Results')")
    findings: list[Finding] = []
    for result in report.get("Results") or []:
        target = str(result.get("Target", ""))
        for vuln in result.get("Vulnerabilities") or []:
            findings.append(
                Finding(
                    scanner="trivy",
                    package=str(vuln.get("PkgName", "")),
                    version=str(vuln.get("InstalledVersion", "")),
                    ids=(str(vuln.get("VulnerabilityID", "")),),
                    severity=str(vuln.get("Severity", "unknown")),
                    title=f"{target}: fix {vuln.get('FixedVersion') or 'not released'}",
                )
            )
        for secret in result.get("Secrets") or []:
            # A secret baked into an image is always blocking, whatever Trivy's severity.
            findings.append(
                Finding(
                    scanner="trivy",
                    package=target,
                    version="",
                    ids=(str(secret.get("RuleID", "secret")),),
                    severity="critical",
                    title=f"secret: {secret.get('Title', '')}",
                )
            )
    return findings


PARSERS = {"pip-audit": parse_pip_audit, "npm": parse_npm, "trivy": parse_trivy}


# ---- gate ------------------------------------------------------------------------------------


@dataclass
class GateResult:
    blocking: list[Finding]
    allowed: list[tuple[Finding, Entry]]
    below_threshold: list[Finding]
    stale: list[Entry]


def gate(
    scanner: str, findings: list[Finding], entries: list[Entry], min_severity: str
) -> GateResult:
    threshold = severity_rank(min_severity)
    result = GateResult(blocking=[], allowed=[], below_threshold=[], stale=[])
    for finding in findings:
        # pip-audit has no severity: every finding is gated.
        if scanner != "pip-audit" and severity_rank(finding.severity) < threshold:
            result.below_threshold.append(finding)
            continue
        entry = next((e for e in entries if e.matches(finding)), None)
        if entry is None:
            result.blocking.append(finding)
        else:
            entry.used = True
            result.allowed.append((finding, entry))
    result.stale = [e for e in entries if e.scanner == scanner and not e.used]
    return result


def describe(finding: Finding) -> str:
    aliases = f" ({', '.join(finding.ids[1:])})" if len(finding.ids) > 1 else ""
    version = f" {finding.version}" if finding.version else ""
    title = f" — {finding.title}" if finding.title else ""
    head = f"[{finding.severity.upper()}] {finding.package}{version}"
    return f"{head}: {finding.primary}{aliases}{title}"


def annotate(level: str, message: str) -> None:
    print(f"::{level}::{message}")


def run(argv: list[str], today: dt.date | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scan_gate", description=__doc__.splitlines()[0])
    parser.add_argument("scanner", choices=("validate", *SCANNERS))
    parser.add_argument("report", nargs="?", type=Path)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--min-severity", default="high", choices=sorted(SEVERITY_RANK))
    args = parser.parse_args(argv)
    today = today or dt.datetime.now(dt.UTC).date()

    entries, problems = load_allowlist(args.allowlist, today)
    for problem in problems:
        annotate("error", f"scan_gate: {problem}")
    if args.scanner == "validate":
        print(f"scan_gate: allow-list {'INVALID' if problems else 'OK'} ({len(entries)} entries)")
        return 1 if problems else 0
    if args.report is None:
        parser.error("a report file is required")

    try:
        findings = PARSERS[args.scanner](read_json(args.report))
    except ReportError as exc:
        annotate("error", f"scan_gate: {exc}")
        return 2

    result = gate(args.scanner, findings, entries, args.min_severity)
    for finding in result.blocking:
        annotate("error", f"scan_gate {args.scanner}: {describe(finding)}")
    for finding, entry in result.allowed:
        print(
            f"scan_gate {args.scanner}: allowed {describe(finding)} — owner {entry.owner}, "
            f"expires {entry.expires}, entry #{entry.index}"
        )
    for entry in result.stale:
        annotate(
            "warning",
            f"scan_gate: allow-list entry #{entry.index} ({entry.package} {entry.id}) matched "
            f"nothing in this {args.scanner} report — remove it if the finding is gone",
        )
    gated = "all findings" if args.scanner == "pip-audit" else f">= {args.min_severity}"
    failed = bool(result.blocking or problems)
    print(
        f"scan_gate {args.scanner}: {'FAILED' if failed else 'OK'} — {len(findings)} finding(s), "
        f"{len(result.blocking)} blocking, {len(result.allowed)} allowed, "
        f"{len(result.below_threshold)} below threshold (gate: {gated})"
    )
    return 1 if failed else 0


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
