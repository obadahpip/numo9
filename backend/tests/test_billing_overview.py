"""U-04-T12 (API) — The billing page's data and the payment-method portal.

Covers: the overview (subscription with package, interval, price, period end, cancellation,
method, grace; a pending downgrade; the packages offered with monthly and annual prices; the Numo9
invoices newest first); the portal session for the organisation's customer coming back to the
billing page; owner only; billing off is reported (and the portal answers 503).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from django.test import Client, override_settings

from numo9.accounts.models import User
from numo9.billing.models import PlatformInvoice, ScheduledChange
from numo9.entitlements.models import Subscription
from numo9.packages.models import Package
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.billing_helpers import FakeGateway, owned_org, sold_package

pytestmark = pytest.mark.django_db
END = dt.datetime(2026, 12, 31, tzinfo=dt.UTC)


@pytest.fixture(autouse=True)
def fake() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("starter", 2900, 29000)
    sold_package("growth", 4900, 49000)
    with override_settings(
        NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway",
        FRONTEND_URL="https://app.numo9.ca",
    ):
        yield


def test_overview_and_portal() -> None:
    org, owner = owned_org()
    growth = Package.objects.get(code="growth")
    Subscription._base_manager.filter(organisation=org).update(
        stripe_customer_id="cus_test_0001",
        stripe_subscription_id="sub_1",
        status="active",
        package=growth,
        current_period_end=END,
        payment_method_type="card",
    )
    with org_context(org):
        for n, day in ((1, 1), (2, 2)):
            PlatformInvoice.objects.create(
                organisation=org,
                stripe_invoice_id=f"in_{n}",
                number=f"NUMO9-000{n}",
                status="paid",
                total_cents=5537,
                issued_at=dt.datetime(2026, 10 + n, day, tzinfo=dt.UTC),
                pdf_url=f"https://pay.stripe.com/invoice/in_{n}/pdf",
            )
        ScheduledChange.objects.create(
            organisation=org,
            subscription=Subscription._base_manager.get(organisation=org),
            package=Package.objects.get(code="starter"),
            interval="month",
            effective_at=END,
        )
    client = Client()
    client.force_login(owner)
    body = client.get(f"/api/v1/o/{org.public_id}/billing").json()
    assert body["billing_available"] is True
    sub = body["subscription"]
    assert sub["package"] == {"code": "growth", "name": "Growth"} and sub["amount_cents"] == 4900
    assert (sub["status"], sub["interval"], sub["payment_method_type"]) == (
        "active",
        "month",
        "card",
    )
    assert sub["paying"] is True and sub["cancel_at_period_end"] is False
    assert body["pending_change"]["package"]["code"] == "starter"
    assert {p["code"]: p["prices"] for p in body["packages"]} == {
        "starter": {"month": 2900, "year": 29000},
        "growth": {"month": 4900, "year": 49000},
    }
    assert [i["number"] for i in body["invoices"]] == ["NUMO9-0002", "NUMO9-0001"]
    portal = client.post(f"/api/v1/o/{org.public_id}/billing/portal")
    assert portal.status_code == 201
    assert portal.json()["url"] == "https://billing.stripe.com/p/session/cus_test_0001"
    assert FakeGateway.calls[-1][1]["return_url"] == (
        f"https://app.numo9.ca/o/{org.public_id}/settings/subscription"
    )


def test_owner_only_and_billing_off() -> None:
    org, owner = owned_org()
    admin = User.objects.create_user("admin@maple.ca", password="x" * 12)
    OrganisationMember.objects.create(organisation=org, user=admin, role="admin")
    other = Client()
    other.force_login(admin)
    assert other.get(f"/api/v1/o/{org.public_id}/billing").status_code == 403
    client = Client()
    client.force_login(owner)
    with override_settings(NUMO9_BILLING_GATEWAY="", STRIPE_SECRET_KEY=""):
        body = client.get(f"/api/v1/o/{org.public_id}/billing").json()
        assert body["billing_available"] is False and body["subscription"]["status"] == "trialing"
        assert client.post(f"/api/v1/o/{org.public_id}/billing/portal").status_code == 503
