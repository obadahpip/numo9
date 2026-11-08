"""Tests for the ADR-0001 region fitness check (S-02-T02)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ci"))

from check_infra_regions import find_violations, main  # noqa: E402


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_canadian_regions_and_zones_pass(tmp_path: Path) -> None:
    write(tmp_path, "main.tf", 'region = "ca-central-1"\n')
    write(tmp_path, "azs.tf", 'azs = ["ca-central-1a", "ca-central-1b"]\n')
    write(tmp_path, "backup.tf", 'region = "ca-west-1"\n')
    assert find_violations([tmp_path]) == []
    assert main([str(tmp_path)]) == 0


def test_foreign_region_fails(tmp_path: Path) -> None:
    write(tmp_path, "main.tf", 'provider "aws" {\n  region = "us-east-1"\n}\n')
    violations = find_violations([tmp_path])
    assert [(v[1], v[2]) for v in violations] == [(2, "us-east-1")]
    assert main([str(tmp_path)]) == 1


def test_foreign_availability_zone_fails(tmp_path: Path) -> None:
    write(tmp_path, "vars.tf", 'default = ["eu-central-1a"]\n')
    assert [v[2] for v in find_violations([tmp_path])] == ["eu-central-1"]


def test_govcloud_and_any_file_type_checked(tmp_path: Path) -> None:
    write(tmp_path, "deploy/env.sh", "export AWS_REGION=us-gov-west-1\n")
    assert [v[2] for v in find_violations([tmp_path])] == ["us-gov-west-1"]


def test_terraform_cache_is_skipped(tmp_path: Path) -> None:
    write(tmp_path, ".terraform/modules/x/main.tf", 'region = "ap-southeast-2"\n')
    assert find_violations([tmp_path]) == []


def test_non_aws_names_ignored(tmp_path: Path) -> None:
    # OVHcloud / DigitalOcean location names from ADR-0001 alternatives are not AWS regions.
    write(tmp_path, "notes.md", "bhs, ca-east-tor, TOR1, us-east-coast\n")
    assert find_violations([tmp_path]) == []


def test_allow_marker_skips_line(tmp_path: Path) -> None:
    text = 'region = "us-east-1" # adr-0001: allow (negative test)\nregion = "us-west-2"\n'
    write(tmp_path, "t.tftest.hcl", text)
    assert [(v[1], v[2]) for v in find_violations([tmp_path])] == [(2, "us-west-2")]


def test_missing_path_is_usage_error(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope")]) == 2
