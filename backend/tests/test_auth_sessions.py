"""A-02-T07 — Session registry (device, IP, user agent, last seen) + revoke one / revoke others;
new-device email.

Acceptance: a revoked session gets 401 on its next request — Dana signs in on two browsers,
lists her sessions from the first (device, IP, user agent, created, last seen, current marked),
ends the other one: that browser's next request (allauth session and a Numo9 API) is 401; "sign
out other sessions" ends every session but the current. New-device email: the first sign-in
sends none; a second browser/system sends the new_device email in the person's language; the
same device again sends none. Also: device names from user agents, sessions of other people
can't be ended, the session list needs a signed-in user.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail
from django.test import Client

from numo9.accounts.devices import describe, device_name
from numo9.accounts.models import KnownDevice
from tests.auth_helpers import API, login, make_user

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("mail_worker")]

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like "
    "Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
)
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0"


def browser(agent: str, ip: str) -> Client:
    return Client(HTTP_USER_AGENT=agent, REMOTE_ADDR=ip)


def sessions(client: Client) -> Any:
    return client.get(f"{API}/auth/sessions")


@pytest.mark.django_db(transaction=True)
def test_revoked_session_gets_401_on_its_next_request() -> None:
    make_user()
    laptop = browser(CHROME_WINDOWS, "203.0.113.24")
    phone = browser(SAFARI_IPHONE, "198.51.100.7")
    assert login(laptop).status_code == 200
    assert login(phone).status_code == 200

    listed = sessions(laptop)
    assert listed.status_code == 200
    rows = listed.json()["data"]
    assert len(rows) == 2
    by_device = {row["device"]: row for row in rows}
    assert set(by_device) == {"Chrome on Windows", "Safari on iPhone"}
    current = by_device["Chrome on Windows"]
    assert current["is_current"] is True and current["ip"] == "203.0.113.24"
    assert current["user_agent"] == CHROME_WINDOWS
    assert current["created_at"] and current["last_seen_at"]
    other = by_device["Safari on iPhone"]
    assert other["is_current"] is False and other["ip"] == "198.51.100.7"

    assert phone.get(f"{API}/auth/session").status_code == 200
    ended = laptop.delete(
        f"{API}/auth/sessions", {"sessions": [other["id"]]}, content_type="application/json"
    )
    assert ended.status_code == 200
    assert [row["device"] for row in ended.json()["data"]] == ["Chrome on Windows"]
    # The revoked browser is signed out: 401 on its next request, allauth's and Numo9's.
    assert phone.get(f"{API}/auth/session").status_code == 401
    assert phone.get("/api/v1/me/organisations").status_code in (401, 403)
    assert laptop.get(f"{API}/auth/session").status_code == 200


@pytest.mark.django_db(transaction=True)
def test_sign_out_other_sessions_keeps_the_current_one() -> None:
    make_user()
    clients = [browser(agent, f"203.0.113.{i}") for i, agent in enumerate(
        (CHROME_WINDOWS, SAFARI_IPHONE, FIREFOX_LINUX)
    )]  # fmt: skip
    for client in clients:
        assert login(client).status_code == 200
    rows = sessions(clients[0]).json()["data"]
    others = [row["id"] for row in rows if not row["is_current"]]
    assert len(others) == 2
    clients[0].delete(f"{API}/auth/sessions", {"sessions": others}, content_type="application/json")
    assert clients[0].get(f"{API}/auth/session").status_code == 200
    assert [c.get(f"{API}/auth/session").status_code for c in clients[1:]] == [401, 401]


@pytest.mark.django_db(transaction=True)
def test_someone_elses_session_cannot_be_ended() -> None:
    make_user()
    make_user("sam@maple.ca")
    dana, sam = browser(CHROME_WINDOWS, "203.0.113.1"), browser(SAFARI_IPHONE, "203.0.113.2")
    login(dana)
    login(sam, "sam@maple.ca")
    sams = sessions(sam).json()["data"][0]["id"]
    refused = dana.delete(
        f"{API}/auth/sessions", {"sessions": [sams]}, content_type="application/json"
    )
    assert refused.status_code == 400
    assert sam.get(f"{API}/auth/session").status_code == 200
    assert Client().get(f"{API}/auth/sessions").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_new_device_email() -> None:
    make_user(locale="fr-ca")
    assert login(browser(CHROME_WINDOWS, "203.0.113.24")).status_code == 200
    assert mail.outbox == []  # first sign-in ever: nothing to compare with
    login(browser(CHROME_WINDOWS, "203.0.113.99"))  # same device, other network
    assert mail.outbox == []
    assert login(browser(SAFARI_IPHONE, "198.51.100.7")).status_code == 200
    [alert] = mail.outbox
    assert alert.to == ["dana@maple.ca"]
    assert alert.subject == "Nouvelle connexion à votre compte Numo9"
    assert "Safari sur iPhone" in alert.body and "198.51.100.7" in alert.body
    assert "/account/security" in alert.body
    assert KnownDevice.objects.count() == 2
    login(browser(SAFARI_IPHONE, "198.51.100.8"))
    assert len(mail.outbox) == 1


def test_device_names() -> None:
    assert describe(CHROME_WINDOWS) == ("Chrome", "Windows")
    assert describe(SAFARI_IPHONE) == ("Safari", "iPhone")
    assert describe(FIREFOX_LINUX) == ("Firefox", "Linux")
    edge = CHROME_WINDOWS + " Edg/131.0.0.0"
    assert device_name(edge) == "Edge on Windows"
    assert device_name("") == "Unknown device"
    assert device_name("curl/8.5.0") == "Unknown device"
