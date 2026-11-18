"""U-07-T11 — demo entry endpoint for the website (anonymous) and signed-in accountants.

Acceptance (integration): an anonymous visitor gets a limited-session demo user — signed in by
the response (session cookie, 8-hour expiry), owner of a fresh demo, an account that can't sign
in again (unusable password, reserved domain); a signed-in accountant gets a demo of their own;
CSRF is required; anonymous opening is rate limited per address.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client

from numo9.accounts.models import User
from numo9.contacts.models import Contact
from numo9.demo import api as demo_api
from numo9.demo.users import DEMO_DOMAIN
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db


def _csrf(browser: Client) -> str:
    return str(browser.get("/api/v1/auth/csrf").json()["csrfToken"])


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    cache.clear()


def test_anonymous_visitor_gets_a_limited_demo_session() -> None:
    browser = Client(enforce_csrf_checks=True)
    response = browser.post("/api/v1/demo", HTTP_X_CSRFTOKEN=_csrf(browser))
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["anonymous"] is True and body["name"] == "Maple & Pine Supply Co."
    demo = Organisation.objects.get(public_id=body["organisation"])
    member = OrganisationMember.objects.get(organisation=demo)
    user = member.user
    assert member.role == "owner"
    assert user.email.endswith("@" + DEMO_DOMAIN) and not user.has_usable_password()
    assert 0 < browser.session.get_expiry_age() <= 8 * 60 * 60
    # The response signed the visitor in: the demo's API answers.
    contacts = browser.get(f"/api/v1/o/{demo.public_id}/contacts")
    assert contacts.status_code == 200
    with org_context(demo):
        assert Contact.objects.count() == 25


def test_signed_in_accountant_gets_their_own_demo() -> None:
    accountant = User.objects.create_user("cpa@practice.example", password="x" * 12)
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(accountant)
    response = browser.post("/api/v1/demo", HTTP_X_CSRFTOKEN=_csrf(browser))
    assert response.status_code == 201
    assert response.json()["anonymous"] is False
    demo = Organisation.objects.get(public_id=response.json()["organisation"])
    assert OrganisationMember.objects.filter(organisation=demo, user=accountant).exists()
    assert User.objects.count() == 1


def test_csrf_required() -> None:
    browser = Client(enforce_csrf_checks=True)
    assert browser.post("/api/v1/demo").status_code == 403
    assert not Organisation.objects.filter(is_demo=True, members__isnull=False).exists()


def test_anonymous_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo_api, "ANONYMOUS_PER_HOUR", 2)
    codes = []
    for _ in range(3):
        browser = Client(enforce_csrf_checks=True)
        codes.append(browser.post("/api/v1/demo", HTTP_X_CSRFTOKEN=_csrf(browser)).status_code)
    assert codes == [201, 201, 429]
