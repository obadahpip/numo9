"""S-03-T07 — brute-force protection: 10 failed logins lock the address for 15 minutes (the 11th
attempt is refused even with the right password), CAPTCHA hook after 5 failures, per-IP limits."""

from __future__ import annotations

import pytest
from django.test import Client, override_settings

from numo9.security import bruteforce
from tests import captcha_stub
from tests.auth_helpers import PASSWORD, codes, login, make_user, post

WRONG = "wrong password 123"  # noqa: S105 — test credential


def fail(client: Client, times: int, email: str = "dana@maple.ca") -> list[int]:
    return [login(client, email, WRONG).status_code for _ in range(times)]


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [1_800_000_000.0]
    monkeypatch.setattr(bruteforce, "_now", lambda: now[0])
    return now


@pytest.mark.django_db
def test_eleventh_attempt_is_locked_even_with_the_right_password(clock: list[float]) -> None:
    make_user()
    client = Client()
    assert fail(client, 10) == [401] * 10
    locked = login(client)  # 11th attempt, correct password
    assert locked.status_code == 429
    assert codes(locked) == ["too_many_login_attempts"]
    assert "15 minutes" in locked.json()["errors"][0]["message"]
    assert int(locked["Retry-After"]) == 15 * 60
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_lock_lasts_15_minutes(clock: list[float]) -> None:
    make_user()
    fail(Client(), 10)
    clock[0] += 14 * 60 + 59
    still = login(Client())
    assert still.status_code == 429
    assert int(still["Retry-After"]) == 1
    clock[0] += 1
    assert login(Client()).status_code == 200


@pytest.mark.django_db
def test_lock_applies_from_any_ip_and_only_to_that_address(clock: list[float]) -> None:
    make_user()
    make_user(email="sam@refined.ca")
    fail(Client(), 10)
    other_ip = post(
        Client(),
        "/auth/login",
        {"email": "dana@maple.ca", "password": PASSWORD},
        REMOTE_ADDR="198.51.100.9",
    )
    assert other_ip.status_code == 429
    assert login(Client(), "sam@refined.ca").status_code == 200


@pytest.mark.django_db
def test_unknown_address_locks_the_same_way(clock: list[float]) -> None:
    # Same behaviour for an address with no account: the lock reveals nothing.
    assert fail(Client(), 10, "nobody@maple.ca") == [401] * 10
    assert login(Client(), "nobody@maple.ca").status_code == 429


@pytest.mark.django_db
def test_success_resets_the_failure_count(clock: list[float]) -> None:
    make_user()
    fail(Client(), 9)
    assert login(Client()).status_code == 200
    assert fail(Client(), 9) == [401] * 9
    assert login(Client()).status_code == 200


@pytest.mark.django_db
def test_failures_older_than_the_window_are_forgotten(clock: list[float]) -> None:
    make_user()
    fail(Client(), 9)
    clock[0] += 15 * 60 + 1
    assert fail(Client(), 9) == [401] * 9
    assert login(Client()).status_code == 200


@pytest.mark.django_db
def test_address_casing_does_not_dodge_the_lock(clock: list[float]) -> None:
    make_user()
    for i in range(10):
        login(Client(), "Dana@Maple.CA" if i % 2 else "dana@maple.ca", WRONG)
    assert login(Client(), "DANA@maple.ca").status_code == 429


def test_cache_keys_never_contain_the_address() -> None:
    fail_key, lock_key = bruteforce._keys("dana@maple.ca")
    assert "dana" not in fail_key + lock_key
    assert bruteforce._keys("DANA@maple.ca ") == (fail_key, lock_key)


@pytest.mark.django_db
def test_clear_unlocks(clock: list[float]) -> None:
    make_user()
    fail(Client(), 10)
    bruteforce.clear("dana@maple.ca")
    assert login(Client()).status_code == 200


# ---- CAPTCHA hook -------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_captcha_needed_without_a_verifier(clock: list[float]) -> None:
    make_user()
    fail(Client(), 6)
    assert login(Client()).status_code == 200


@pytest.mark.django_db
@override_settings(NUMO9_CAPTCHA_VERIFIER="tests.captcha_stub.verify")
def test_captcha_required_after_five_failures(clock: list[float]) -> None:
    make_user()
    captcha_stub.CALLS.clear()
    assert fail(Client(), 5) == [401] * 5
    assert captcha_stub.CALLS == []  # not asked before the threshold

    missing = login(Client())
    assert missing.status_code == 400
    assert codes(missing) == ["captcha_required"]

    bot = post(
        Client(), "/auth/login", {"email": "dana@maple.ca", "password": PASSWORD, "captcha": "bot"}
    )
    assert codes(bot) == ["captcha_required"]

    human = post(
        Client(),
        "/auth/login",
        {"email": "dana@maple.ca", "password": PASSWORD, "captcha": "human"},
    )
    assert human.status_code == 200
    assert captcha_stub.CALLS[-1] == ("human", "127.0.0.1")


@pytest.mark.django_db
@override_settings(NUMO9_CAPTCHA_VERIFIER="tests.captcha_stub.verify")
def test_captcha_does_not_replace_the_lockout(clock: list[float]) -> None:
    make_user()
    for _ in range(10):
        post(
            Client(),
            "/auth/login",
            {"email": "dana@maple.ca", "password": WRONG, "captcha": "human"},
        )
    locked = post(
        Client(),
        "/auth/login",
        {"email": "dana@maple.ca", "password": PASSWORD, "captcha": "human"},
    )
    assert locked.status_code == 429


def test_verifier_crash_counts_as_not_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(token: str, ip: str | None) -> bool:
        raise ConnectionError("provider down")

    monkeypatch.setattr(bruteforce, "captcha_verifier", lambda: broken)
    assert bruteforce.captcha_ok("human", "127.0.0.1") is False
