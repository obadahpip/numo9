"""S-03-T01 — Django security settings per environment: `check --deploy` 0 warnings in staging and
prod; Secure/HttpOnly/SameSite cookies, X-Frame-Options DENY, Referrer-Policy, HSTS, HTTPS
redirect (health check exempt) and the CSRF token endpoint."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import Client, override_settings

from numo9.accounts.models import User

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_KEYS = (
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DATABASE_URL",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SECURE_HSTS_SECONDS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
)


def _env(module: str, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env.update(
        DJANGO_SETTINGS_MODULE=f"numo9.settings.{module}",
        DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
        DJANGO_ALLOWED_HOSTS="app.numo9.ca",
        DATABASE_URL="sqlite:///:memory:",
    )
    env.update(extra)
    return env


def _check_deploy(module: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=BACKEND_DIR,
        env=_env(module, **extra),
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("module", ["staging", "prod"])
def test_check_deploy_has_no_warnings(module: str) -> None:
    result = _check_deploy(module)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "System check identified no issues" in result.stdout


def test_check_deploy_catches_a_weak_secret_key() -> None:
    # Proves the check runs against these settings: a short key is reported (security.W009).
    result = _check_deploy("prod", DJANGO_SECRET_KEY="short")  # noqa: S106 — deliberately weak
    assert result.returncode != 0
    assert "security.W009" in result.stdout + result.stderr


PROBE = """
import json, django
django.setup()
from django.conf import settings as s
names = [
    "SECURE_SSL_REDIRECT", "SECURE_PROXY_SSL_HEADER", "SECURE_REDIRECT_EXEMPT",
    "SECURE_HSTS_SECONDS", "SECURE_HSTS_INCLUDE_SUBDOMAINS", "SECURE_HSTS_PRELOAD",
    "SESSION_COOKIE_SECURE", "SESSION_COOKIE_HTTPONLY", "SESSION_COOKIE_SAMESITE",
    "CSRF_COOKIE_SECURE", "CSRF_COOKIE_HTTPONLY", "CSRF_COOKIE_SAMESITE", "CSRF_TRUSTED_ORIGINS",
    "X_FRAME_OPTIONS", "SECURE_REFERRER_POLICY", "SECURE_CONTENT_TYPE_NOSNIFF", "DEBUG",
]
print(json.dumps({n: getattr(s, n) for n in names}))
"""


def _settings(module: str, **extra: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=BACKEND_DIR,
        env=_env(module, **extra),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    loaded: dict[str, object] = json.loads(result.stdout)
    return loaded


@pytest.mark.parametrize("module", ["staging", "prod"])
def test_deployed_settings(module: str) -> None:
    s = _settings(module, DJANGO_CSRF_TRUSTED_ORIGINS="https://app.numo9.ca")
    assert s["DEBUG"] is False
    assert s["SECURE_SSL_REDIRECT"] is True
    assert s["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert s["SECURE_REDIRECT_EXEMPT"] == ["^healthz$"]
    assert s["SECURE_HSTS_SECONDS"] == 31_536_000
    assert s["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is True
    assert s["SECURE_HSTS_PRELOAD"] is True
    for cookie in ("SESSION", "CSRF"):
        assert s[f"{cookie}_COOKIE_SECURE"] is True
        assert s[f"{cookie}_COOKIE_HTTPONLY"] is True
        assert s[f"{cookie}_COOKIE_SAMESITE"] == "Lax"
    assert s["CSRF_TRUSTED_ORIGINS"] == ["https://app.numo9.ca"]
    assert s["X_FRAME_OPTIONS"] == "DENY"
    assert s["SECURE_REFERRER_POLICY"] == "strict-origin-when-cross-origin"
    assert s["SECURE_CONTENT_TYPE_NOSNIFF"] is True


@pytest.mark.parametrize("module", ["dev", "test"])
def test_local_settings_work_over_http(module: str) -> None:
    s = _settings(module)
    assert s["SECURE_SSL_REDIRECT"] is False
    assert s["SESSION_COOKIE_SECURE"] is False
    assert s["SECURE_HSTS_SECONDS"] == 0
    # Headers and HttpOnly/SameSite are the same everywhere.
    assert s["X_FRAME_OPTIONS"] == "DENY"
    assert s["CSRF_COOKIE_HTTPONLY"] is True


def test_invalid_hsts_seconds_is_rejected() -> None:
    result = _check_deploy("prod", DJANGO_SECURE_HSTS_SECONDS="one year")
    assert result.returncode != 0
    assert "DJANGO_SECURE_HSTS_SECONDS must be an integer" in result.stderr


# ---- Behaviour (in-process, test settings) ----------------------------------------------------


def test_security_headers_on_every_response(client: Client) -> None:
    response = client.get("/healthz")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"


@override_settings(
    SECURE_SSL_REDIRECT=True,
    SECURE_REDIRECT_EXEMPT=[r"^healthz$"],
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    SECURE_HSTS_SECONDS=31_536_000,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
    SECURE_HSTS_PRELOAD=True,
)
def test_https_redirect_hsts_and_health_check_exemption(client: Client) -> None:
    redirect = client.get("/api/v1/auth/csrf", HTTP_HOST="testserver")
    assert redirect.status_code == 301
    assert redirect.headers["Location"] == "https://testserver/api/v1/auth/csrf"
    assert client.get("/healthz").status_code == 200  # compose/deploy health check over HTTP

    secure = client.get("/api/v1/auth/csrf", HTTP_X_FORWARDED_PROTO="https")
    assert secure.status_code == 200
    assert (
        secure.headers["Strict-Transport-Security"]
        == "max-age=31536000; includeSubDomains; preload"
    )


@pytest.mark.django_db
def test_csrf_token_endpoint_and_httponly_cookie() -> None:
    client = Client(enforce_csrf_checks=True)
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    token = response.json()["csrfToken"]
    assert token
    cookie = response.cookies["csrftoken"]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    assert "no-cache" in response.headers["Cache-Control"]


@pytest.mark.django_db
def test_unsafe_request_needs_the_csrf_token() -> None:
    user = User.objects.create_user("csrf@example.com", name="Dana")
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)

    refused = client.post("/api/v1/practices", {"name": "Lee CPA"}, content_type="application/json")
    assert refused.status_code == 403
    assert "CSRF" in refused.json()["detail"]

    token = client.get("/api/v1/auth/csrf").json()["csrfToken"]
    accepted = client.post(
        "/api/v1/practices",
        {"name": "Lee CPA"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert accepted.status_code != 403, accepted.content
