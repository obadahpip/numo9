"""Tests for the ADR-0002 location fitness check (S-02-T02)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ci"))

from check_infra_locations import find_violations, line_violations, main  # noqa: E402


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_allowed_locations_pass(tmp_path: Path) -> None:
    write(tmp_path, "main.tf", 'location = "hel1"\nnetwork_zone = "eu-central"\n')
    write(tmp_path, "backend.hcl", 'endpoints = { s3 = "https://hel1.your-objectstorage.com" }\n')
    write(tmp_path, "backup.tf", 'region = "fsn1"\n')
    assert find_violations([tmp_path]) == []
    assert main([str(tmp_path)]) == 0


def test_other_hetzner_location_fails(tmp_path: Path) -> None:
    write(tmp_path, "main.tf", 'server {\n  location = "nbg1"\n}\n')
    assert [(v[1], v[2]) for v in find_violations([tmp_path])] == [(2, "Hetzner location 'nbg1'")]
    assert main([str(tmp_path)]) == 1


def test_us_location_and_datacenter_fail() -> None:
    assert line_violations('location = "ash"') == ["Hetzner location 'ash'"]
    assert line_violations('datacenter = "hil-dc1"') == ["Hetzner location 'hil'"]


def test_object_storage_endpoint_checked() -> None:
    assert line_violations("https://nbg1.your-objectstorage.com") == ["Hetzner location 'nbg1'"]


def test_network_zone_checked() -> None:
    assert line_violations('network_zone = "us-east"') == ["network zone 'us-east'"]


def test_any_aws_region_fails() -> None:
    assert line_violations('region = "ca-central-1"') == ["AWS region 'ca-central-1'"]
    assert line_violations('azs = ["eu-central-1a"]') == ["AWS region 'eu-central-1'"]


def test_ordinary_words_not_flagged() -> None:
    # "sin", "ash", "hil" are Hetzner location codes but also ordinary text (e.g. SIN numbers).
    assert line_violations("Mask the SIN; ash and hill; since 2026") == []
    assert line_violations('network_zone = "eu-central"') == []


def test_allow_marker_skips_line() -> None:
    assert line_violations('location = "nbg1" # adr-0002: allow (negative test)') == []


def test_terraform_cache_is_skipped(tmp_path: Path) -> None:
    write(tmp_path, ".terraform/modules/x/main.tf", 'location = "sin"\n')
    assert find_violations([tmp_path]) == []


def test_missing_path_is_usage_error(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope")]) == 2
