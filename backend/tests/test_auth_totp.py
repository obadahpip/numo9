"""A-02-T05 — TOTP 2FA: enrolment (secret + QR code, verify), 10 hashed single-use recovery
codes shown once, challenge at login, ±1 step clock skew, "remember this device" signed cookie
for 30 days."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

import pytest
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal import auth as rc_auth
from allauth.mfa.recovery_codes.internal import flows as rc_flows
from allauth.mfa.totp.internal.auth import format_hotp_value, hotp_value
from django.conf import settings
from django.test import Client

from numo9.accounts import mfa
from numo9.security import crypto
from tests.auth_helpers import API, PASSWORD, codes, login, make_user, post

PERIOD = 30


def totp(secret: str, steps: int = 0, at: float | None = None) -> str:
    counter = int(at if at is not None else time.time()) // PERIOD + steps
    return str(format_hotp_value(hotp_value(secret, counter)))


def reauthenticate(client: Client) -> None:
    """Sensitive 2FA changes need a fresh password confirmation (allauth reauthentication)."""
    response = post(client, "/auth/reauthenticate", {"password": PASSWORD})
    assert response.status_code == 200, response.json()


def enrol(client: Client) -> tuple[str, list[str]]:
    """Set up TOTP for the signed-in user; returns (secret, recovery codes)."""
    reauthenticate(client)
    setup = client.get(f"{API}/account/authenticators/totp")
    assert setup.status_code == 404  # not enrolled yet: answer carries the set-up data
    meta = setup.json()["meta"]
    secret = meta["secret"]
    activated = post(client, "/account/authenticators/totp", {"code": totp(secret)})
    assert activated.status_code == 200, activated.json()
    return secret, activated.json()["meta"]["recovery_codes"]


def signed_in_with_totp(email: str = "dana@maple.ca") -> tuple[str, list[str]]:
    make_user(email=email)
    client = Client()
    assert login(client, email).status_code == 200
    return enrol(client)


def mfa_pending(response: Any) -> bool:
    flows = response.json().get("data", {}).get("flows", [])
    return any(f["id"] == "mfa_authenticate" and f.get("is_pending") for f in flows)


def challenge(client: Client, code: str) -> Any:
    return post(client, "/auth/2fa/authenticate", {"code": code})


# ---- enrolment -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_setup_returns_secret_otpauth_url_and_qr_code() -> None:
    make_user()
    client = Client()
    login(client)
    meta = client.get(f"{API}/account/authenticators/totp").json()["meta"]
    assert len(meta["secret"]) == 32  # 160-bit base32
    assert meta["totp_url"].startswith("otpauth://totp/dana%40maple.ca?secret=")
    assert meta["totp_url"].endswith("&issuer=Numo9")
    assert meta["qr_code"].startswith("data:image/svg+xml;base64,")


@pytest.mark.django_db
def test_wrong_code_does_not_activate() -> None:
    make_user()
    client = Client()
    login(client)
    reauthenticate(client)
    secret = client.get(f"{API}/account/authenticators/totp").json()["meta"]["secret"]
    wrong = post(client, "/account/authenticators/totp", {"code": totp(secret, steps=5)})
    assert wrong.status_code == 400
    assert not Authenticator.objects.filter(type="totp").exists()


@pytest.mark.django_db
def test_activation_returns_ten_recovery_codes_once() -> None:
    make_user()
    client = Client()
    login(client)
    _, recovery = enrol(client)
    assert len(recovery) == 10
    assert len(set(recovery)) == 10
    assert all(mfa.looks_like_recovery_code(c) and len(c) == 11 for c in recovery)
    # Never shown again.
    later = client.get(f"{API}/account/authenticators/recovery-codes")
    assert later.status_code == 200
    assert "unused_codes" not in later.json()["data"]
    assert later.json()["data"]["unused_code_count"] == 10


@pytest.mark.django_db
def test_secret_and_recovery_codes_are_unreadable_in_the_database() -> None:
    secret, recovery = signed_in_with_totp()
    stored_totp = Authenticator.objects.get(type="totp").data
    assert secret not in str(stored_totp)
    assert crypto.is_ciphertext(stored_totp["secret"])
    stored_codes = Authenticator.objects.get(type="recovery_codes").data
    assert stored_codes["scheme"] == mfa.SCHEME
    assert len(stored_codes["hashes"]) == 10
    flat = str(stored_codes)
    assert not any(mfa.normalise(code) in flat or code in flat for code in recovery)
    assert "seed" not in stored_codes


def test_allauth_uses_the_hashed_recovery_codes() -> None:
    # Guards against an allauth upgrade that bypasses the replacement (mfa.install()).
    assert rc_auth.RecoveryCodes is mfa.HashedRecoveryCodes
    assert rc_flows.RecoveryCodes is mfa.HashedRecoveryCodes
    assert Authenticator(type="recovery_codes", data={}).wrap().__class__ is mfa.HashedRecoveryCodes


# ---- login challenge ------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_asks_for_the_code_and_refuses_a_wrong_one() -> None:
    secret, _ = signed_in_with_totp()
    client = Client()
    response = login(client)
    assert response.status_code == 401
    assert mfa_pending(response)
    assert client.get("/api/v1/me/organisations").status_code == 403  # not signed in yet

    wrong = challenge(client, totp(secret, steps=3))
    assert wrong.status_code == 400
    assert codes(wrong) == ["incorrect_code"]

    right = challenge(client, totp(secret))
    # Signed in, or asked whether to trust this browser (next step) — either way, past 2FA.
    assert not mfa_pending(right)
    trust = post(client, "/auth/2fa/trust", {"trust": False})
    assert trust.status_code == 200
    assert trust.json()["meta"]["is_authenticated"] is True


@pytest.mark.django_db
@pytest.mark.parametrize("steps", [-1, 1])
def test_one_step_of_clock_skew_is_accepted(steps: int) -> None:
    secret, _ = signed_in_with_totp()
    client = Client()
    login(client)
    assert not mfa_pending(challenge(client, totp(secret, steps=steps)))


@pytest.mark.django_db
@pytest.mark.parametrize("steps", [-2, 2])
def test_two_steps_of_skew_are_refused(steps: int) -> None:
    secret, _ = signed_in_with_totp()
    client = Client()
    login(client)
    assert challenge(client, totp(secret, steps=steps)).status_code == 400


@pytest.mark.django_db
def test_a_totp_code_cannot_be_replayed() -> None:
    secret, _ = signed_in_with_totp()
    code = totp(secret)
    first = Client()
    login(first)
    assert not mfa_pending(challenge(first, code))
    second = Client()
    login(second)
    assert challenge(second, code).status_code == 400


# ---- recovery codes ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_recovery_code_works_once() -> None:
    _, recovery = signed_in_with_totp()
    client = Client()
    login(client)
    assert not mfa_pending(challenge(client, recovery[0].upper().replace("-", " ")))

    again = Client()
    login(again)
    assert challenge(again, recovery[0]).status_code == 400  # used
    assert not mfa_pending(challenge(again, recovery[1]))  # another one still works
    data = Authenticator.objects.get(type="recovery_codes").wrap()
    assert len(data.get_unused_codes()) == 8


@pytest.mark.django_db
def test_regenerating_codes_replaces_the_old_ones() -> None:
    make_user()
    client = Client()
    login(client)
    _, old = enrol(client)
    reauthenticate(client)
    fresh = post(client, "/account/authenticators/recovery-codes", {})
    assert fresh.status_code == 200
    new = fresh.json()["data"]["unused_codes"]
    assert len(new) == 10
    assert set(new).isdisjoint(old)

    other = Client()
    login(other)
    assert challenge(other, old[0]).status_code == 400
    assert not mfa_pending(challenge(other, new[0]))


@pytest.mark.django_db
def test_non_recovery_shaped_input_does_no_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(mfa, "check_password", lambda value, hashed: calls.append(value))
    wrapper = mfa.HashedRecoveryCodes(
        Authenticator(
            type="recovery_codes", data={"scheme": mfa.SCHEME, "hashes": ["x"], "used_mask": 0}
        )
    )
    assert wrapper.validate_code("123456") is False
    assert calls == []


# ---- remember this device -----------------------------------------------------------------


@pytest.mark.django_db
def test_trusted_device_skips_the_challenge_for_30_days(monkeypatch: pytest.MonkeyPatch) -> None:
    assert timedelta(days=30) == settings.MFA_TRUST_COOKIE_AGE
    secret, _ = signed_in_with_totp()
    client = Client()
    login(client)
    challenge(client, totp(secret))
    trusted = post(client, "/auth/2fa/trust", {"trust": True})
    assert trusted.status_code == 200
    cookie = trusted.cookies[settings.MFA_TRUST_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert int(cookie["max-age"]) == 30 * 24 * 3600

    client.delete(f"{API}/auth/session")
    again = login(client)
    assert again.status_code == 200  # no code asked on this browser
    client.delete(f"{API}/auth/session")

    # 30 days later the cookie is no longer honoured.
    real_time = time.time
    monkeypatch.setattr(
        "allauth.mfa.internal.flows.trust.time.time", lambda: real_time() + 30 * 24 * 3600 + 5
    )
    assert mfa_pending(login(client))


@pytest.mark.django_db
def test_trust_cookie_is_signed_and_bound_to_the_user() -> None:
    secret, _ = signed_in_with_totp()
    client = Client()
    login(client)
    challenge(client, totp(secret))
    post(client, "/auth/2fa/trust", {"trust": True})
    value = client.cookies[settings.MFA_TRUST_COOKIE_NAME].value

    forged = Client()
    forged.cookies[settings.MFA_TRUST_COOKIE_NAME] = value[:-2] + "xx"
    assert mfa_pending(login(forged))

    # Another account with 2FA does not inherit this browser's trust.
    signed_in_with_totp("sam@refined.ca")
    other = Client()
    other.cookies[settings.MFA_TRUST_COOKIE_NAME] = value
    assert mfa_pending(login(other, "sam@refined.ca"))


@pytest.mark.django_db
def test_without_2fa_login_is_one_step() -> None:
    make_user()
    assert login(Client()).status_code == 200


@pytest.mark.django_db
def test_enrolment_needs_a_fresh_password_confirmation() -> None:
    make_user()
    client = Client()
    login(client)
    secret = client.get(f"{API}/account/authenticators/totp").json()["meta"]["secret"]
    response = post(client, "/account/authenticators/totp", {"code": totp(secret)})
    assert response.status_code == 401
    assert any(f["id"] == "reauthenticate" for f in response.json()["data"]["flows"])
    assert not Authenticator.objects.exists()
