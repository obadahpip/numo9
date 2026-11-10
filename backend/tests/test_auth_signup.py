"""A-02-T02 — sign-up through django-allauth headless: accountant and organisation paths, email
verification required before the first login, Argon2id hashing, breached-password validator."""

from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.error
import urllib.request
from typing import Any, cast

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.hashers import make_password
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, override_settings

from numo9.accounts import validators
from numo9.accounts.models import User
from numo9.settings import base as base_settings
from numo9.tenancy.models import (
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
    PracticeMember,
    PracticeRole,
)

API = "/_allauth/browser/v1"
PASSWORD = "correct horse battery 42"  # noqa: S105 — test credential


def post(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.post(f"{API}{path}", json.dumps(body), content_type="application/json")


def accountant(**overrides: str) -> dict[str, str]:
    body = {
        "path": "accountant",
        "name": "Dana Lee",
        "email": "Dana.Lee@Example.ca",
        "password": PASSWORD,
        "practice_name": "Maple Leaf Accounting",
    }
    body.update(overrides)
    return body


def owner(**overrides: str) -> dict[str, str]:
    body = {
        "path": "organisation",
        "name": "Sam Roy",
        "email": "sam@refined.ca",
        "password": PASSWORD,
        "organisation_name": "Refined Interiors Inc.",
    }
    body.update(overrides)
    return body


def verification_key(message: Any) -> str:
    match = re.search(r"/verify/(\S+)", message.body)
    assert match, message.body
    from urllib.parse import unquote

    return unquote(match.group(1))


def error_codes(response: Any) -> dict[str, str]:
    return {e.get("param", ""): e["code"] for e in response.json().get("errors", [])}


# ---- accountant path ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_accountant_signup_creates_practice_and_waits_for_verification() -> None:
    client = Client()
    response = post(client, "/auth/signup", accountant())
    assert response.status_code == 401
    flows = {f["id"]: f for f in response.json()["data"]["flows"]}
    assert flows["verify_email"]["is_pending"] is True
    assert response.json()["meta"]["is_authenticated"] is False

    user = User.objects.get(email="dana.lee@example.ca")
    assert user.name == "Dana Lee"
    member = PracticeMember.objects.get(user=user)
    assert member.role == PracticeRole.PRACTICE_ADMIN
    assert member.practice.name == "Maple Leaf Accounting"
    assert not OrganisationMember.objects.filter(user=user).exists()
    assert EmailAddress.objects.get(user=user).verified is False

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["dana.lee@example.ca"]
    assert "/verify/" in mail.outbox[0].body
    assert "testserver" not in mail.outbox[0].body  # emails name the product, not the API host


@pytest.mark.django_db
def test_organisation_signup_creates_trial_organisation_with_owner() -> None:
    response = post(Client(), "/auth/signup", owner())
    assert response.status_code == 401
    user = User.objects.get(email="sam@refined.ca")
    member = OrganisationMember.objects.get(user=user)
    assert member.role == OrganisationRole.OWNER
    assert member.organisation.name == "Refined Interiors Inc."
    assert member.organisation.status == OrganisationStatus.TRIAL
    assert not PracticeMember.objects.filter(user=user).exists()


# ---- acceptance: unverified login refused ------------------------------------------------------


@pytest.mark.django_db
def test_unverified_user_cannot_log_in() -> None:
    post(Client(), "/auth/signup", accountant())
    client = Client()
    response = post(client, "/auth/login", {"email": "dana.lee@example.ca", "password": PASSWORD})
    assert response.status_code == 401
    assert response.json()["meta"]["is_authenticated"] is False
    pending = [f["id"] for f in response.json()["data"]["flows"] if f.get("is_pending")]
    assert pending == ["verify_email"]
    session = client.get(f"{API}/auth/session")
    assert session.status_code == 401
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_verifying_the_email_signs_in_and_allows_login() -> None:
    client = Client()
    post(client, "/auth/signup", accountant())
    key = verification_key(mail.outbox[0])

    response = post(client, "/auth/email/verify", {"key": key})
    assert response.status_code == 200, response.json()
    assert response.json()["meta"]["is_authenticated"] is True
    assert EmailAddress.objects.get(email="dana.lee@example.ca").verified is True

    fresh = Client()
    login = post(fresh, "/auth/login", {"email": "DANA.LEE@example.ca", "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["data"]["user"]["email"] == "dana.lee@example.ca"


@pytest.mark.django_db
def test_verification_key_is_single_use_and_tamper_proof() -> None:
    client = Client()
    post(client, "/auth/signup", accountant())
    key = verification_key(mail.outbox[0])
    assert post(Client(), "/auth/email/verify", {"key": key[:-2] + "xx"}).status_code == 400
    assert post(Client(), "/auth/email/verify", {"key": key}).status_code in {200, 401}
    assert post(Client(), "/auth/email/verify", {"key": key}).status_code in {400, 409}


# ---- validation ----------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("body", "param", "code"),
    [
        (accountant(practice_name=""), "practice_name", "practice_name_required"),
        (owner(organisation_name=""), "organisation_name", "organisation_name_required"),
        (accountant(path="investor"), "path", "invalid_choice"),
        (accountant(name=""), "name", "required"),
        (accountant(password="short pass"), "password", "password_too_short"),  # noqa: S106
        (accountant(email="not-an-email"), "email", "invalid"),
    ],
)
def test_invalid_signup_is_refused_with_a_field_error(
    body: dict[str, str], param: str, code: str
) -> None:
    response = post(Client(), "/auth/signup", body)
    assert response.status_code == 400
    assert error_codes(response).get(param) == code
    assert not User.objects.exists()


@pytest.mark.django_db
def test_signup_with_a_registered_email_reveals_nothing_and_creates_nothing() -> None:
    post(Client(), "/auth/signup", accountant())
    mail.outbox.clear()
    cache.clear()  # a later attempt (allauth sends at most one email per address per 3 min)
    second = post(Client(), "/auth/signup", accountant(practice_name="Other Practice"))
    # Same answer as a new sign-up (no account enumeration) …
    assert second.status_code == 401
    assert [f["id"] for f in second.json()["data"]["flows"] if f.get("is_pending")] == [
        "verify_email"
    ]
    # … no second account or practice, and the mailbox owner is told instead.
    assert User.objects.count() == 1
    assert PracticeMember.objects.count() == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["dana.lee@example.ca"]


@pytest.mark.django_db
def test_signup_is_atomic(monkeypatch: pytest.MonkeyPatch) -> None:
    from numo9.tenancy import models as tenancy_models

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(tenancy_models.PracticeMember.objects, "create", boom)
    with pytest.raises(RuntimeError):
        post(Client(raise_request_exception=True), "/auth/signup", accountant())
    assert not User.objects.exists()


# ---- Argon2id --------------------------------------------------------------------------------


def test_argon2id_is_the_password_hasher() -> None:
    assert base_settings.PASSWORD_HASHERS[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"
    with override_settings(PASSWORD_HASHERS=base_settings.PASSWORD_HASHERS):
        assert make_password(PASSWORD).startswith("argon2$argon2id$")


@pytest.mark.django_db
def test_signup_stores_an_argon2id_hash() -> None:
    with override_settings(PASSWORD_HASHERS=base_settings.PASSWORD_HASHERS):
        post(Client(), "/auth/signup", accountant())
    user = User.objects.get()
    assert user.password.startswith("argon2$argon2id$")
    assert PASSWORD not in user.password


def test_minimum_length_is_twelve() -> None:
    validators_config = cast(list[dict[str, Any]], base_settings.AUTH_PASSWORD_VALIDATORS)
    lengths = [
        v.get("OPTIONS", {}).get("min_length")
        for v in validators_config
        if v["NAME"].endswith("MinimumLengthValidator")
    ]
    assert lengths == [12]


# ---- breached-password validator (k-anonymity) ----------------------------------------------


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def stub_range(monkeypatch: pytest.MonkeyPatch, password: str, count: int) -> list[str]:
    digest = hashlib.sha1(password.encode()).hexdigest().upper()  # noqa: S324
    requested: list[str] = []

    def urlopen(request: Any, timeout: float) -> FakeResponse:
        requested.append(request.full_url)
        assert request.headers.get("Add-padding") == "true"
        lines = ["0" * 35 + ":0", f"{digest[5:]}:{count}", "F" * 35 + ":3"]
        return FakeResponse("\r\n".join(lines).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return requested


@override_settings(BREACHED_PASSWORD_CHECK=True)
def test_breached_password_is_refused_and_only_the_prefix_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = stub_range(monkeypatch, PASSWORD, 52_000)
    with pytest.raises(ValidationError) as excinfo:
        validators.BreachedPasswordValidator().validate(PASSWORD)
    assert excinfo.value.code == "password_breached"
    digest = hashlib.sha1(PASSWORD.encode()).hexdigest().upper()  # noqa: S324
    assert requested == [f"https://api.pwnedpasswords.com/range/{digest[:5]}"]
    assert digest[5:] not in requested[0]


@override_settings(BREACHED_PASSWORD_CHECK=True)
def test_password_not_in_a_breach_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_range(monkeypatch, "some other password", 9)
    validators.BreachedPasswordValidator().validate(PASSWORD)  # no error


@override_settings(BREACHED_PASSWORD_CHECK=True)
def test_breach_check_fails_open_when_the_api_is_down(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def urlopen(request: Any, timeout: float) -> FakeResponse:
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    validators.BreachedPasswordValidator().validate(PASSWORD)  # accepted, warning logged
    assert validators.breach_count(PASSWORD) is None


@pytest.mark.django_db
@override_settings(BREACHED_PASSWORD_CHECK=True)
def test_signup_with_a_breached_password_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_range(monkeypatch, PASSWORD, 3)
    response = post(Client(), "/auth/signup", accountant())
    assert response.status_code == 400
    assert error_codes(response) == {"password": "password_breached"}
    assert not User.objects.exists()
