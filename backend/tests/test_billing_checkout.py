"""U-04-T05 — Checkout session endpoint. Acceptance: practice user → 403; owner gets the URL.

``POST /api/v1/o/<org>/billing/checkout``: the owner gets the Checkout URL (card + pre-authorised
debit by default, or the method chosen) for the package's price in force, with metadata naming the
organisation, the package and the interval, and the billing page as return addresses; the
customer is created once. Refused: practice staff (even a practice admin), the organisation's
admin and other members (403), another organisation (404), an unknown or draft package (400), a
price not synced yet (409), an organisation already paying (409), billing off (503), bad body
(400). Documented in the OpenAPI schema.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
import yaml
from django.test import Client, override_settings

from numo9.accounts.models import User
from numo9.entitlements.models import Subscription
from numo9.packages.models import PackagePrice
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)
from tests.billing_helpers import FakeGateway, owned_org, sold_package
from tests.entitlement_helpers import package

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake() -> Iterator[None]:
    FakeGateway.reset()
    with override_settings(
        NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway",
        NUMO9_FRONTEND_URL="https://app.numo9.ca",
        FRONTEND_URL="https://app.numo9.ca",
    ):
        yield


def login(user: User) -> Client:
    client = Client()
    client.force_login(user)
    return client


def url(org: Organisation) -> str:
    return f"/api/v1/o/{org.public_id}/billing/checkout"


def post(client: Client, org: Organisation, body: dict[str, Any]) -> Any:
    return client.post(url(org), body, content_type="application/json")


def test_owner_gets_the_checkout_url() -> None:
    sold_package("growth")
    org, owner = owned_org()
    response = post(login(owner), org, {"package": "growth", "interval": "year"})
    assert response.status_code == 201, response.content
    assert response.json() == {
        "url": "https://checkout.stripe.com/c/pay/cs_test_1",
        "session_id": "cs_test_1",
        "package": "growth",
        "interval": "year",
        "amount_cents": 49000,
    }
    calls = dict(FakeGateway.calls)
    session = calls["create_checkout_session"]
    assert session["customer"] == "cus_test_0001" and session["price"] == "price_growth_year"
    assert session["payment_method_types"] == ["card", "acss_debit"]
    assert session["metadata"] == {
        "numo9_org": str(org.public_id),
        "numo9_package": "growth",
        "numo9_interval": "year",
    }
    page = f"https://app.numo9.ca/o/{org.public_id}/settings/subscription"
    assert session["success_url"].startswith(f"{page}?checkout=success")
    assert session["cancel_url"] == f"{page}?checkout=cancelled"
    post(login(owner), org, {"package": "growth", "interval": "month", "methods": ["acss_debit"]})
    assert FakeGateway.calls[-1][1]["payment_method_types"] == ["acss_debit"]
    assert [c for c, _ in FakeGateway.calls].count("create_customer") == 1


def test_practice_staff_admin_and_members_are_refused() -> None:
    sold_package("growth")
    org, _ = owned_org()
    practice = Practice.objects.create(name="Tremblay CPA")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    for role in ("practice_admin", "accountant"):
        user = User.objects.create_user(f"{role}@cpa.ca", password="x" * 12)
        assignment.assigned_staff.add(
            PracticeMember.objects.create(practice=practice, user=user, role=role)
        )
        assert post(login(user), org, {"package": "growth", "interval": "month"}).status_code == 403
    for role in ("admin", "accountant_delegate", "sales"):
        user = User.objects.create_user(f"{role}@maple.ca", password="x" * 12)
        OrganisationMember.objects.create(organisation=org, user=user, role=role)
        assert post(login(user), org, {"package": "growth", "interval": "month"}).status_code == 403
    assert FakeGateway.calls == []


def test_other_organisation_is_404() -> None:
    sold_package("growth")
    org, _ = owned_org()
    _, stranger = owned_org("Other Inc.", "other@other.ca")
    assert post(login(stranger), org, {"package": "growth", "interval": "month"}).status_code == 404


def test_refusals() -> None:
    sold_package("growth")
    draft = package("draft", ["accounting"], status="draft")
    PackagePrice.objects.create(
        package=draft,
        interval="month",
        amount_cents=100,
        effective_from=date(2026, 1, 1),
        stripe_price_id="price_draft",
    )
    unsynced = package("starter", ["accounting"])
    PackagePrice.objects.create(
        package=unsynced, interval="month", amount_cents=900, effective_from=date(2026, 1, 1)
    )
    org, owner = owned_org()
    client = login(owner)
    for body, status, code in [
        ({"package": "nope", "interval": "month"}, 400, "billing.package_unknown"),
        ({"package": "draft", "interval": "month"}, 400, "billing.package_unknown"),
        ({"package": "starter", "interval": "month"}, 409, "billing.price_not_ready"),
        ({"package": "starter", "interval": "year"}, 409, "billing.price_not_ready"),
    ]:
        response = post(client, org, body)
        assert (response.status_code, response.json()["code"]) == (status, code), body
    assert post(client, org, {"package": "growth", "interval": "week"}).status_code == 400
    assert (
        post(client, org, {"package": "growth", "interval": "month", "methods": []}).status_code
        == 400
    )
    Subscription._base_manager.filter(organisation=org).update(stripe_subscription_id="sub_1")
    paying = post(client, org, {"package": "growth", "interval": "month"})
    assert (paying.status_code, paying.json()["code"]) == (409, "billing.already_subscribed")


def test_billing_off_is_503() -> None:
    sold_package("growth")
    org, owner = owned_org()
    with override_settings(NUMO9_BILLING_GATEWAY="", STRIPE_SECRET_KEY=""):
        response = post(login(owner), org, {"package": "growth", "interval": "month"})
    assert (response.status_code, response.json()["code"]) == (503, "billing.unavailable")


def test_documented() -> None:
    org, owner = owned_org()
    schema = yaml.safe_load(login(owner).get("/api/schema/").content)
    operation = schema["paths"]["/api/v1/o/{org}/billing/checkout"]["post"]
    assert operation["operationId"] == "billing_checkout" and "201" in operation["responses"]
