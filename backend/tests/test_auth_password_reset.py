"""A-02-T04 — password reset: the emailed key is valid for 1 hour and works once; the new
password ends every existing session; nothing reveals whether an address has an account."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import unquote

import pytest
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.test import Client

from numo9.accounts.models import User
from numo9.security import bruteforce
from tests.auth_helpers import API, PASSWORD, codes, login, make_user, post

NEW_PASSWORD = "a brand new passphrase 77"  # noqa: S105 — test credential


def request_reset(email: str = "dana@maple.ca") -> Any:
    return post(Client(), "/auth/password/request", {"email": email})


def reset_key() -> str:
    match = re.search(r"/reset/(\S+)", str(mail.outbox[-1].body))
    assert match, mail.outbox[-1].body
    return unquote(match.group(1))


def reset(key: str, password: str = NEW_PASSWORD) -> Any:
    return post(Client(), "/auth/password/reset", {"key": key, "password": password})


@pytest.mark.django_db
def test_reset_link_sets_a_new_password() -> None:
    make_user()
    assert request_reset().status_code == 200
    assert mail.outbox[-1].to == ["dana@maple.ca"]
    key = reset_key()
    check = Client().get(f"{API}/auth/password/reset", HTTP_X_PASSWORD_RESET_KEY=key)
    assert check.status_code == 200

    response = reset(key)
    assert response.status_code == 401  # password set; the user signs in again
    assert login(Client(), password=NEW_PASSWORD).status_code == 200
    assert login(Client(), password=PASSWORD).status_code == 401


@pytest.mark.django_db
def test_reused_key_is_refused() -> None:
    make_user()
    request_reset()
    key = reset_key()
    assert reset(key).status_code == 401
    again = reset(key, "yet another passphrase 88")
    assert again.status_code == 400
    assert codes(again) == ["invalid_password_reset"]
    assert login(Client(), password=NEW_PASSWORD).status_code == 200


@pytest.mark.django_db
def test_key_expires_after_one_hour(monkeypatch: pytest.MonkeyPatch) -> None:
    assert settings.PASSWORD_RESET_TIMEOUT == 3600
    make_user()
    request_reset()
    key = reset_key()
    issued = datetime.now()

    monkeypatch.setattr(
        PasswordResetTokenGenerator, "_now", lambda self: issued + timedelta(minutes=59)
    )
    check = Client().get(f"{API}/auth/password/reset", HTTP_X_PASSWORD_RESET_KEY=key)
    assert check.status_code == 200

    monkeypatch.setattr(
        PasswordResetTokenGenerator, "_now", lambda self: issued + timedelta(hours=1, seconds=5)
    )
    expired = reset(key)
    assert expired.status_code == 400
    assert codes(expired) == ["invalid_password_reset"]
    assert login(Client()).status_code == 200  # the old password still works


@pytest.mark.django_db
def test_reset_ends_every_existing_session() -> None:
    make_user()
    laptop, phone = Client(), Client()
    assert login(laptop).status_code == 200
    assert login(phone).status_code == 200
    request_reset()
    reset(reset_key())
    for client in (laptop, phone):
        assert client.get(f"{API}/auth/session").status_code == 401
        assert client.get("/api/v1/me/organisations").status_code == 403


@pytest.mark.django_db
def test_unknown_address_gets_the_same_answer() -> None:
    make_user()
    known = request_reset("dana@maple.ca")
    unknown = request_reset("nobody@maple.ca")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_tampered_key_is_refused() -> None:
    make_user()
    request_reset()
    key = reset_key()
    response = reset(key[:-3] + "abc")
    assert response.status_code == 400
    assert login(Client()).status_code == 200


@pytest.mark.django_db
def test_new_password_must_pass_the_validators() -> None:
    make_user()
    request_reset()
    response = reset(reset_key(), "short")
    assert response.status_code == 400
    assert "password_too_short" in codes(response)


@pytest.mark.django_db
def test_reset_unlocks_a_locked_account() -> None:
    make_user()
    for _ in range(10):
        login(Client(), password="wrong password 123")  # noqa: S106
    assert bruteforce.locked_for("dana@maple.ca") > 0
    request_reset()
    reset(reset_key())
    assert bruteforce.locked_for("dana@maple.ca") == 0
    assert login(Client(), password=NEW_PASSWORD).status_code == 200
