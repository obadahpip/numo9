"""check_secrets — no plaintext secret files in the repository (S-03-T03).

    python tools/ci/check_secrets.py [repo-root]

Fails (exit 1) when, among the files tracked by git (or present, outside a git checkout):
- an ``infra/secrets/*.sops.env`` file has a value that is not SOPS-encrypted
  (``ENC[AES256_GCM,…]``) or lacks the SOPS metadata (``sops_mac``, ``sops_version``);
- a recipients file (``infra/secrets/recipients/*.txt``) holds anything but age public keys;
- a private key or plain environment file is committed: ``AGE-SECRET-KEY-…`` anywhere,
  ``.env`` / ``.env.<name>`` (``.env.example`` is allowed), ``*.age``, ``*.key``, ``*.pem``.
gitleaks (security workflow) scans the content of every commit; this check covers the
SOPS-specific rules gitleaks cannot know.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

B64 = r"[A-Za-z0-9+/=]"
ENCRYPTED = re.compile(rf"^ENC\[AES256_GCM,data:{B64}*,iv:{B64}+,tag:{B64}+,type:\w+\]$")
AGE_PUBLIC = re.compile(r"^age1[02-9ac-hj-np-z]{58}$")
AGE_SECRET = re.compile(r"AGE-SECRET-KEY-1[0-9A-Z]{50,}")
REQUIRED_METADATA = ("sops_mac", "sops_version")
FORBIDDEN_NAME = re.compile(r"(^|/)(\.env(\.(?!example$)[^/]+)?|[^/]+\.(age|key|pem))$")


def tracked_files(root: Path) -> list[str]:
    try:
        out = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "-C", str(root), "ls-files", "-z"],  # noqa: S607 — git from PATH
            capture_output=True,
            check=True,
        ).stdout
        return [name for name in out.decode().split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        return [str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()]


def check_sops_env(path: Path, rel: str) -> list[str]:
    problems: list[str] = []
    keys: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if not sep:
            problems.append(f"{rel}:{number}: not a NAME=value line")
            continue
        keys.add(name)
        if name.startswith("sops_") or value == "":
            continue
        if not ENCRYPTED.match(value):
            problems.append(f"{rel}:{number}: {name} is not encrypted (plain text value)")
    for meta in REQUIRED_METADATA:
        if meta not in keys:
            problems.append(f"{rel}: missing SOPS metadata '{meta}' — not a SOPS file")
    if not any(k.startswith("sops_age__") for k in keys):
        problems.append(f"{rel}: no age recipient in the SOPS metadata")
    return problems


def check_recipients(path: Path, rel: str) -> list[str]:
    problems: list[str] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        key = raw.split("#", 1)[0].strip()
        if key and not AGE_PUBLIC.match(key):
            problems.append(f"{rel}:{number}: not an age public key (age1…)")
    return problems


def run(root: Path) -> list[str]:
    problems: list[str] = []
    for rel in tracked_files(root):
        path = root / rel
        if not path.is_file():
            continue
        if FORBIDDEN_NAME.search(rel):
            problems.append(f"{rel}: secret/key/environment files must not be committed")
            continue
        if re.fullmatch(r"infra/secrets/[^/]+\.sops\.env", rel):
            problems.extend(check_sops_env(path, rel))
        elif re.fullmatch(r"infra/secrets/recipients/[^/]+\.txt", rel):
            problems.extend(check_recipients(path, rel))
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if AGE_SECRET.search(text):
            problems.append(f"{rel}: contains an age private key (AGE-SECRET-KEY-…)")
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    problems = run(root)
    for problem in problems:
        print(f"check_secrets: {problem}")
    print(f"check_secrets: {'FAILED' if problems else 'OK'} ({len(problems)} problem(s))")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
