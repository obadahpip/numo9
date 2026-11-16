"""U-04-T01 — Stripe configuration: keys from the secrets file, none in the repository.

Acceptance (gitleaks): the gitleaks rules catch Stripe secret, restricted and webhook keys (test
and live) — sample keys are built at run time so none is ever written in the repository — and
leave publishable keys and placeholders alone; the secrets template names the three Stripe
variables; the settings read them from the environment and default to empty (billing off); no
tracked file holds a Stripe secret.
"""

from __future__ import annotations

import re
import secrets
import string
import subprocess
import tomllib
from pathlib import Path

import pytest
from django.conf import settings

ROOT = Path(__file__).resolve().parents[2]
RULES = {r["id"]: r for r in tomllib.loads((ROOT / ".gitleaks.toml").read_text())["rules"]}


def _random(n: int) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))


def _matches(rule_id: str, text: str) -> bool:
    return re.search(RULES[rule_id]["regex"], text) is not None


@pytest.mark.parametrize("prefix", ["sk_test_", "sk_live_", "rk_test_", "rk_live_"])
def test_secret_and_restricted_keys_are_caught(prefix: str) -> None:
    key = prefix + _random(99)
    assert _matches("numo9-stripe-secret-key", f"STRIPE_SECRET_KEY={key}")
    assert _matches("numo9-stripe-secret-key", f'api_key = "{key}"')


def test_webhook_secret_is_caught() -> None:
    assert _matches("numo9-stripe-webhook-secret", "STRIPE_WEBHOOK_SECRET=whsec_" + _random(32))


def test_publishable_keys_and_placeholders_pass() -> None:
    assert not _matches("numo9-stripe-secret-key", "pk_live_" + _random(99))
    assert not _matches("numo9-stripe-secret-key", "STRIPE_SECRET_KEY=")
    assert not _matches("numo9-stripe-webhook-secret", "whsec_…")


def test_template_names_the_variables() -> None:
    template = (ROOT / "infra" / "secrets" / "env.template").read_text()
    for name in ("STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET"):
        assert re.search(rf"^{name}=$", template, re.M), name


def test_settings_default_to_billing_off() -> None:
    assert settings.STRIPE_PUBLISHABLE_KEY == ""
    assert settings.STRIPE_WEBHOOK_SECRET == ""


def test_no_stripe_secret_in_tracked_files() -> None:
    files = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],  # noqa: S607 - git from PATH
        capture_output=True,
        check=True,
    ).stdout.decode()
    found: list[str] = []
    for name in filter(None, files.split("\0")):
        path = ROOT / name
        if not path.is_file() or path.suffix in {".png", ".jpg", ".pdf", ".docx", ".woff2"}:
            continue
        text = path.read_text(errors="ignore")
        for rule in ("numo9-stripe-secret-key", "numo9-stripe-webhook-secret"):
            if _matches(rule, text):
                found.append(f"{name} ({rule})")
    assert found == []
