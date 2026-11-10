"""S-03-T03 — tools/ci/check_secrets.py: no plaintext secret files in the repository."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ci"))

import check_secrets  # noqa: E402

ENC = "ENC[AES256_GCM,data:QUJD,iv:aXZpdml2aXZpdml2,tag:dGFndGFndGFn,type:str]"
PUBLIC = "age1" + "q" * 58
# Built at run time so the test source itself holds no private-key-shaped string.
PRIVATE = "AGE-SECRET-KEY-1" + "Q" * 58

GOOD = f"""DJANGO_SECRET_KEY={ENC}
DJANGO_SECRET_KEY_FALLBACKS=
sops_age__list_0__map_enc=-----BEGIN AGE ENCRYPTED FILE-----
sops_age__list_0__map_recipient={PUBLIC}
sops_lastmodified=2026-11-10T00:00:00Z
sops_mac={ENC}
sops_version=3.11.0
"""


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)  # noqa: S603, S607
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)  # noqa: S603, S607
    return tmp_path


def test_encrypted_file_and_public_recipients_pass(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path,
        {
            "infra/secrets/staging.sops.env": GOOD,
            "infra/secrets/recipients/staging.txt": f"# lead\n{PUBLIC}  # lead\n\n",
            "backend/.env.example": "DJANGO_SECRET_KEY=change-me\n",
        },
    )
    assert check_secrets.run(repo) == []


def test_plain_text_value_fails(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path, {"infra/secrets/prod.sops.env": GOOD + "STRIPE_SECRET_KEY=plain-value\n"}
    )
    assert check_secrets.run(repo) == [
        "infra/secrets/prod.sops.env:8: STRIPE_SECRET_KEY is not encrypted (plain text value)"
    ]


def test_file_without_sops_metadata_fails(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"infra/secrets/prod.sops.env": f"DJANGO_SECRET_KEY={ENC}\n"})
    problems = check_secrets.run(repo)
    assert any("missing SOPS metadata 'sops_mac'" in p for p in problems)
    assert any("no age recipient" in p for p in problems)


@pytest.mark.parametrize(
    "name",
    [".env", "backend/.env", "infra/.env.production", "keys/host.age", "x/server.key", "a.pem"],
)
def test_committed_key_or_env_files_fail(tmp_path: Path, name: str) -> None:
    repo = make_repo(tmp_path, {name: "X=1\n"})
    assert check_secrets.run(repo) == [
        f"{name}: secret/key/environment files must not be committed"
    ]


def test_private_key_anywhere_fails(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"docs/notes.md": f"key: {PRIVATE}\n"})
    assert check_secrets.run(repo) == [
        "docs/notes.md: contains an age private key (AGE-SECRET-KEY-…)"
    ]


def test_recipients_must_be_public_keys(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"infra/secrets/recipients/prod.txt": f"{PRIVATE}\n"})
    problems = check_secrets.run(repo)
    assert "infra/secrets/recipients/prod.txt:1: not an age public key (age1…)" in problems


def test_untracked_files_are_ignored(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"README.md": "x\n"})
    (repo / ".env").write_text("DJANGO_SECRET_KEY=local\n", encoding="utf-8")  # gitignored locally
    assert check_secrets.run(repo) == []


def test_repository_is_clean() -> None:
    root = Path(__file__).resolve().parents[2]
    assert check_secrets.run(root) == []
