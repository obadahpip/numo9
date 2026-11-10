"""A-02-T03 — login/logout API (allauth headless + Numo9 status codes), session cookie
hardening and login rate limit: 200 signed in, 401 wrong credentials or signed out, 429 limited."""

from __future__ import annotations

import base64
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, override_settings

from tests.auth_helpers import API, PASSWORD, codes, login, make_user, post

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.django_db
def test_login_200_sets_a_fresh_hardened_session() -> None:
    make_user()
    client = Client()
    client.get(f"{API}/auth/session")  # an anonymous session cookie may exist before login
    client.session.save()
    before = client.session.session_key

    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["is_authenticated"] is True
    assert body["data"]["user"]["email"] == "dana@maple.ca"

    cookie = response.cookies[settings.SESSION_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    # Session fixation: the session id changes at login.
    assert client.session.session_key != before
    assert client.get(f"{API}/auth/session").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("email", "password"),
    [("dana@maple.ca", "wrong password 123"), ("nobody@maple.ca", PASSWORD)],
)
def test_wrong_credentials_401_without_revealing_which(email: str, password: str) -> None:
    make_user()
    response = login(Client(), email, password)
    assert response.status_code == 401
    assert codes(response) == ["email_password_mismatch"]


@pytest.mark.django_db
def test_malformed_login_is_400() -> None:
    response = post(Client(), "/auth/login", {"email": "dana@maple.ca"})
    assert response.status_code == 400
    assert codes(response) == ["required"]


@pytest.mark.django_db
def test_logout_ends_the_session_for_good() -> None:
    make_user()
    client = Client()
    login(client)
    old_cookie = client.cookies[settings.SESSION_COOKIE_NAME].value

    response = client.delete(f"{API}/auth/session")
    assert response.status_code == 401  # signed out: the answer is the unauthenticated state
    assert response.json()["meta"]["is_authenticated"] is False
    assert client.get(f"{API}/auth/session").status_code == 401

    replay = Client()
    replay.cookies[settings.SESSION_COOKIE_NAME] = old_cookie
    assert replay.get(f"{API}/auth/session").status_code == 401
    assert replay.get("/api/v1/me/organisations").status_code == 403


@pytest.mark.django_db
def test_session_works_for_the_platform_api() -> None:
    make_user()
    client = Client()
    login(client)
    assert client.get("/api/v1/me/organisations").status_code == 200


@pytest.mark.django_db
def test_login_requires_the_csrf_token() -> None:
    make_user()
    client = Client(enforce_csrf_checks=True)
    assert login(client).status_code == 403
    token = client.get("/api/v1/auth/csrf").json()["csrfToken"]
    response = post(
        client,
        "/auth/login",
        {"email": "dana@maple.ca", "password": PASSWORD},
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_rate_limit_429_per_ip() -> None:
    make_user()
    client = Client()
    statuses = [login(client, f"nobody{i}@maple.ca").status_code for i in range(20)]
    assert set(statuses) == {401}
    limited = login(client)  # the 21st attempt in a minute, even with the right password
    assert limited.status_code == 429
    # Another client address is not affected.
    other = post(
        Client(),
        "/auth/login",
        {"email": "dana@maple.ca", "password": PASSWORD},
        REMOTE_ADDR="198.51.100.7",
    )
    assert other.status_code == 200


@override_settings(ACCOUNT_RATE_LIMITS={"login": "2/m/ip"})
@pytest.mark.django_db
def test_rate_limit_comes_from_settings() -> None:
    make_user()
    client = Client()
    for attempt in (1, 2):
        assert login(client, password=f"wrong password {attempt}").status_code == 401
    assert login(client).status_code == 429


def test_deployed_session_and_csrf_cookies_use_the_host_prefix() -> None:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "numo9.settings.prod",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_ALLOWED_HOSTS": "app.numo9.ca",
        "DATABASE_URL": "sqlite:///:memory:",
        "NUMO9_FIELD_ENCRYPTION_KEYS": json.dumps(
            {"k1": base64.b64encode(os.urandom(32)).decode()}
        ),
        "NUMO9_FIELD_ENCRYPTION_ACTIVE_KEY": "k1",
    }
    script = (
        "import django; django.setup(); from django.conf import settings as s; "
        "print(s.SESSION_COOKIE_NAME, s.CSRF_COOKIE_NAME, s.SESSION_COOKIE_SECURE, "
        "s.CSRF_COOKIE_SECURE, s.SESSION_COOKIE_DOMAIN, s.SESSION_COOKIE_PATH, "
        "s.CACHES['default']['BACKEND'])"
    )
    out = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.split()
    assert out == [
        "__Host-numo9_session",
        "__Host-numo9_csrf",
        "True",
        "True",
        "None",
        "/",
        "django.core.cache.backends.redis.RedisCache",
    ]
