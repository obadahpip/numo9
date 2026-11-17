"""U-01-T12 — "Package & features" with real packages (U-02) and the current package (U-03/U-04).

The page's API with the production sources — ``OfferedPackages`` (U-02 packages for sale) and
``Subscriptions`` (U-03) — and the current package set by billing (U-04): before paying, a trial
organisation has no package highlighted; after Stripe's checkout and subscription events, its
package is highlighted; an upgrade moves the highlight. Every feature key is a row; each package
ticks exactly the keys of its products (plus the free sets); searching "reminder" in the matrix
finds the invoice-reminder keys (the screen filters the same rows; Playwright:
``frontend/e2e/package-features.spec.ts``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient

from numo9.catalogue.models import FeatureKey
from numo9.entitlements.models import Subscription
from tests.billing_helpers import (
    FakeGateway,
    deliver,
    owned_org,
    sold_package,
    stripe_event,
    stripe_subscription,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def real_sources() -> Iterator[None]:
    assert settings.NUMO9_PACKAGE_SOURCE == "numo9.packages.source.OfferedPackages"
    assert settings.NUMO9_SUBSCRIPTION_SOURCE == "numo9.entitlements.source.Subscriptions"
    FakeGateway.reset()
    sold_package("starter", 2900, 29000, products=("accounting",))
    sold_package("complete", 9900, 99000, products=("accounting", "payroll", "tax"))
    with override_settings(NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway"):
        yield


def matrix(api: APIClient, org: Any) -> dict[str, Any]:
    response = api.get(f"/api/v1/o/{org.public_id}/package-features")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_current_package_follows_billing() -> None:
    org, owner = owned_org()
    api = APIClient()
    api.force_authenticate(owner)
    body = matrix(api, org)
    assert body["current_package"] is None
    assert {p["code"] for p in body["packages"]} == {"starter", "complete"}
    assert len(body["features"]) == FeatureKey.objects.count()

    Subscription._base_manager.filter(organisation=org).update(stripe_customer_id="cus_test_0001")
    meta = {"numo9_org": str(org.public_id), "numo9_package": "starter", "numo9_interval": "month"}
    deliver(
        stripe_event(
            "checkout.session.completed",
            {
                "mode": "subscription",
                "customer": "cus_test_0001",
                "subscription": "sub_1",
                "payment_status": "paid",
                "metadata": meta,
            },
        )
    )
    deliver(
        stripe_event(
            "customer.subscription.created", stripe_subscription(price="price_starter_month")
        )
    )
    assert matrix(api, org)["current_package"] == "starter"
    deliver(
        stripe_event(
            "customer.subscription.updated",
            stripe_subscription(price="price_complete_month"),
            created=2_000_000_000,
        )
    )
    assert matrix(api, org)["current_package"] == "complete"


def test_ticks_follow_the_products_and_reminders_are_found() -> None:
    org, owner = owned_org()
    api = APIClient()
    api.force_authenticate(owner)
    body = matrix(api, org)
    packages = {p["code"]: set(p["products"]) for p in body["packages"]}
    assert {"accounting"} <= packages["starter"] and "payroll" not in packages["starter"]
    assert {"accounting", "payroll", "tax"} <= packages["complete"]
    for row in body["features"]:
        product = row["key"].split(".")[0]
        ticked = {code for code, products in packages.items() if product in products}
        assert set(row["packages"]) == ticked, row["key"]
    reminders = [
        r["key"] for r in body["features"] if "reminder" in (r["key"] + r["description"]).lower()
    ]
    assert "accounting.invoice_reminders.write" in reminders
