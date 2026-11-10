"""S-03-T09 — tools/ci/scan_gate.py: scanner findings fail the build unless justified."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ci"))

import scan_gate  # noqa: E402

TODAY = dt.date(2026, 11, 10)
REPO = Path(__file__).resolve().parents[2]
JUSTIFIED = "Build-time only (Storybook); never shipped in the runtime image. Fix pending upstream."

PIP_REPORT = {
    "dependencies": [
        {"name": "django", "version": "5.2.19", "vulns": []},
        {
            "name": "Some_Lib",
            "version": "1.0",
            "vulns": [
                {
                    "id": "PYSEC-2026-1",
                    "fix_versions": ["1.1"],
                    "aliases": ["CVE-2026-0001", "GHSA-aaaa-bbbb-cccc"],
                    "description": "…",
                }
            ],
        },
    ],
    "fixes": [],
}


def npm_report(severity: str) -> dict[str, object]:
    return {
        "actions": [],
        "advisories": {
            "1001": {
                "id": 1001,
                "github_advisory_id": "GHSA-1111-2222-3333",
                "cves": ["CVE-2026-1111"],
                "module_name": "left-pad",
                "severity": severity,
                "title": "Prototype pollution",
                "findings": [{"version": "1.3.0", "paths": ["frontend>left-pad"]}],
            }
        },
        "metadata": {},
    }


def trivy_report(severity: str = "HIGH", secret: bool = False) -> dict[str, object]:
    result: dict[str, object] = {
        "Target": "numo9-backend:ci (debian 12.12)",
        "Vulnerabilities": [
            {
                "VulnerabilityID": "CVE-2026-9999",
                "PkgName": "openssl",
                "InstalledVersion": "3.0.1",
                "FixedVersion": "3.0.2",
                "Severity": severity,
            }
        ],
    }
    if secret:
        result["Secrets"] = [{"RuleID": "aws-access-key-id", "Severity": "LOW", "Title": "AWS"}]
    return {"SchemaVersion": 2, "Results": [result]}


def write(tmp_path: Path, name: str, data: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def allowlist(tmp_path: Path, body: str = "") -> Path:
    path = tmp_path / "allow.toml"
    path.write_text(body, encoding="utf-8")
    return path


def entry(**overrides: str) -> str:
    fields = {
        "scanner": '"npm"',
        "package": '"left-pad"',
        "id": '"GHSA-1111-2222-3333"',
        "justification": f'"{JUSTIFIED}"',
        "owner": '"obadahpip"',
        "expires": "2027-01-31",
    }
    fields.update(overrides)
    lines = "\n".join(f"{k} = {v}" for k, v in fields.items() if v != "")
    return f"[[finding]]\n{lines}\n"


def gate(tmp_path: Path, scanner: str, report: object, allow: str = "", *extra: str) -> int:
    path = write(tmp_path, "report.json", report)
    args = [scanner, str(path), "--allowlist", str(allowlist(tmp_path, allow)), *extra]
    return scan_gate.run(args, today=TODAY)


# ---- acceptance: a high finding fails the build ---------------------------------------------


@pytest.mark.parametrize("severity", ["high", "critical"])
def test_high_npm_finding_fails_the_build(tmp_path: Path, severity: str) -> None:
    assert gate(tmp_path, "npm", npm_report(severity)) == 1


@pytest.mark.parametrize("severity", ["moderate", "low"])
def test_npm_finding_below_threshold_passes(tmp_path: Path, severity: str) -> None:
    assert gate(tmp_path, "npm", npm_report(severity)) == 0


def test_min_severity_can_be_lowered(tmp_path: Path) -> None:
    assert gate(tmp_path, "npm", npm_report("moderate"), "", "--min-severity", "moderate") == 1


def test_any_pip_audit_finding_fails(tmp_path: Path) -> None:
    assert gate(tmp_path, "pip-audit", PIP_REPORT) == 1


def test_clean_pip_audit_report_passes(tmp_path: Path) -> None:
    clean = {"dependencies": [{"name": "django", "version": "5.2.19", "vulns": []}]}
    assert gate(tmp_path, "pip-audit", clean) == 0


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL"])
def test_high_trivy_vulnerability_fails(tmp_path: Path, severity: str) -> None:
    assert gate(tmp_path, "trivy", trivy_report(severity)) == 1


def test_medium_trivy_vulnerability_passes(tmp_path: Path) -> None:
    assert gate(tmp_path, "trivy", trivy_report("MEDIUM")) == 0


def test_trivy_secret_always_fails(tmp_path: Path) -> None:
    assert gate(tmp_path, "trivy", trivy_report("LOW", secret=True)) == 1


def test_trivy_report_without_findings_passes(tmp_path: Path) -> None:
    assert gate(tmp_path, "trivy", {"SchemaVersion": 2, "Results": None}) == 0


# ---- allow-list matching ---------------------------------------------------------------------


def test_justified_entry_allows_the_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert gate(tmp_path, "npm", npm_report("high"), entry()) == 0
    assert "allowed [HIGH] left-pad" in capsys.readouterr().out


@pytest.mark.parametrize("finding_id", ["CVE-2026-1111", "1001", "ghsa-1111-2222-3333"])
def test_entry_matches_any_alias(tmp_path: Path, finding_id: str) -> None:
    assert gate(tmp_path, "npm", npm_report("high"), entry(id=f'"{finding_id}"')) == 0


def test_pip_entry_matches_alias_and_normalised_name(tmp_path: Path) -> None:
    allow = entry(scanner='"pip-audit"', package='"some-lib"', id='"CVE-2026-0001"')
    assert gate(tmp_path, "pip-audit", PIP_REPORT, allow) == 0


def test_entry_for_another_package_does_not_allow(tmp_path: Path) -> None:
    assert gate(tmp_path, "npm", npm_report("high"), entry(package='"right-pad"')) == 1


def test_entry_for_another_scanner_does_not_allow(tmp_path: Path) -> None:
    allow = entry(scanner='"trivy"')
    assert gate(tmp_path, "npm", npm_report("high"), allow) == 1


def test_trivy_entry_allows_os_package(tmp_path: Path) -> None:
    allow = entry(scanner='"trivy"', package='"openssl"', id='"CVE-2026-9999"')
    assert gate(tmp_path, "trivy", trivy_report("CRITICAL"), allow) == 0


def test_unused_entry_is_reported_as_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert gate(tmp_path, "npm", npm_report("low"), entry()) == 0
    assert "::warning::" in capsys.readouterr().out


# ---- allow-list validation: justification required ----------------------------------------


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"justification": '"needed"'}, "justification"),
        (
            {"justification": '"TODO: write why this is fine later, it is temporary for now"'},
            "justification",
        ),
        ({"justification": ""}, "justification"),
        ({"owner": ""}, "owner"),
        ({"owner": '"  "'}, "owner"),
        ({"expires": "2026-11-09"}, "expired"),
        ({"expires": "2027-06-30"}, "90 days"),
        ({"expires": '"soon"'}, "TOML date"),
        ({"expires": ""}, "TOML date"),
        ({"scanner": '"snyk"'}, "scanner"),
        ({"package": '""'}, "package"),
        ({"id": '""'}, "id is required"),
    ],
)
def test_invalid_entry_fails_even_when_it_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], override: dict[str, str], message: str
) -> None:
    assert gate(tmp_path, "npm", npm_report("high"), entry(**override)) == 1
    assert message in capsys.readouterr().out


def test_invalid_entry_fails_a_clean_report_too(tmp_path: Path) -> None:
    assert gate(tmp_path, "npm", npm_report("low"), entry(owner="")) == 1


def test_unknown_key_and_duplicate_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    allow = (
        entry()
        + entry()
        + entry(id='"CVE-2026-1111"').replace("[[finding]]\n", '[[finding]]\nseverity = "low"\n')
    )
    path = allowlist(tmp_path, allow)
    assert scan_gate.run(["validate", "--allowlist", str(path)], today=TODAY) == 1
    out = capsys.readouterr().out
    assert "duplicate" in out
    assert "unknown key" in out


def test_expiry_on_the_last_allowed_day_is_valid(tmp_path: Path) -> None:
    last = (TODAY + dt.timedelta(days=90)).isoformat()
    path = allowlist(tmp_path, entry(expires=last))
    assert scan_gate.run(["validate", "--allowlist", str(path)], today=TODAY) == 0


def test_invalid_toml_and_missing_allowlist_fail(tmp_path: Path) -> None:
    bad = allowlist(tmp_path, "[[finding]\n")
    assert scan_gate.run(["validate", "--allowlist", str(bad)], today=TODAY) == 1
    missing = tmp_path / "nope.toml"
    assert scan_gate.run(["validate", "--allowlist", str(missing)], today=TODAY) == 1


# ---- unreadable reports fail ----------------------------------------------------------------


def test_missing_report_fails(tmp_path: Path) -> None:
    allow = str(allowlist(tmp_path))
    args = ["npm", str(tmp_path / "absent.json"), "--allowlist", allow]
    assert scan_gate.run(args, today=TODAY) == 2


@pytest.mark.parametrize(
    ("scanner", "report"),
    [("npm", {"error": {"code": "ERR_PNPM_AUDIT_BAD_RESPONSE"}}), ("pip-audit", []), ("trivy", {})],
)
def test_wrong_report_shape_fails(tmp_path: Path, scanner: str, report: object) -> None:
    assert gate(tmp_path, scanner, report) == 2


def test_non_json_report_fails(tmp_path: Path) -> None:
    path = tmp_path / "r.json"
    path.write_text("ERR_PNPM_AUDIT_ENDPOINT_NOT_EXISTS\n", encoding="utf-8")
    args = ["npm", str(path), "--allowlist", str(allowlist(tmp_path))]
    assert scan_gate.run(args, today=TODAY) == 2


# ---- the committed allow-list ---------------------------------------------------------------


def test_committed_allowlist_is_valid() -> None:
    result = subprocess.run(  # noqa: S603 — fixed argv
        [sys.executable, str(REPO / "tools/ci/scan_gate.py"), "validate"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
