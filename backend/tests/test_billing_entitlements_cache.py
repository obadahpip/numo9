"""U-04-T14 — Entitlement cache invalidation on every subscription change.

Acceptance: the entitlements reflect each change within one request. With the cache warm before
each step, the next ``entitlements_for`` (and the bootstrap API) answers the new state after:
checkout completed (trial → paid package: its products), an upgrade webhook (more products), a
failed payment (past due, full access, grace end), the dunning's read-only step, a paid renewal
(full again), a cancellation at period end then the subscription deleted (cancelled: read-only),
a customer saved by ``ensure_customer``; and a handler that changes state without
``Subscription.save()`` still bumps the version (the processing bump).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from django.test import Client, override_settings

from numo9.billing.dunning import run_dunning
from numo9.billing.processing import _handlers, register_handler
from numo9.entitlements.cache import entitlements_for, version
from numo9.entitlements.models import Subscription
from numo9.tenancy.models import Organisation
from tests.billing_helpers import (
    FakeGateway,
    deliver,
    owned_org,
    sold_package,
    stripe_event,
    stripe_invoice,
    stripe_subscription,
)

pytestmark = pytest.mark.django_db
T = int(dt.datetime.now(dt.UTC).timestamp())


@pytest.fixture(autouse=True)
def packages() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("starter", 2900, 29000, products=("accounting",))
    sold_package("complete", 9900, 99000, products=("accounting", "payroll"))
    with override_settings(NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway"):
        yield


def warm(org: Organisation) -> None:
    entitlements_for(org)  # the cache now holds the current answer


def now_state(org: Organisation) -> tuple[str, str, str | None, bool]:
    org.refresh_from_db()
    answer = entitlements_for(org)
    return answer.mode, answer.reason, answer.package, "payroll" in answer.products


def test_every_change_is_visible_on_the_next_request() -> None:
    org, owner = owned_org()
    Subscription._base_manager.filter(organisation=org).update(stripe_customer_id="cus_test_0001")
    meta = {"numo9_org": str(org.public_id), "numo9_package": "starter", "numo9_interval": "month"}
    warm(org)
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
            created=T,
        )
    )
    assert now_state(org) == ("full", "active", "starter", False)

    warm(org)
    deliver(
        stripe_event(
            "customer.subscription.updated",
            stripe_subscription(price="price_complete_month"),
            created=T + 10,
        )
    )
    assert now_state(org) == ("full", "active", "complete", True)

    warm(org)
    deliver(stripe_event("invoice.payment_failed", stripe_invoice(status="open"), created=T + 20))
    assert now_state(org)[:2] == ("full", "past_due")

    warm(org)
    run_dunning(dt.datetime.fromtimestamp(T + 20, tz=dt.UTC) + dt.timedelta(days=7))
    assert now_state(org)[:2] == ("read_only", "payment_failed")

    warm(org)
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=T + 30))
    assert now_state(org)[:2] == ("full", "active")

    client = Client()
    client.force_login(owner)
    warm(org)
    deliver(
        stripe_event(
            "customer.subscription.deleted",
            stripe_subscription(status="canceled", price="price_complete_month"),
            created=T + 40,
        )
    )
    body = client.get(f"/api/v1/o/{org.public_id}/entitlements").json()
    assert (body["mode"], body["reason"]) == ("read_only", "cancelled")


def test_customer_saved_bumps_the_version() -> None:
    from numo9.billing.customers import ensure_customer

    org, _ = owned_org()
    before = version(org)
    ensure_customer(org)
    assert version(org) != before


def test_handler_without_save_still_bumps() -> None:
    org, _ = owned_org()
    Subscription._base_manager.filter(organisation=org).update(stripe_customer_id="cus_test_0001")

    def quiet(event: object) -> None:
        from numo9.billing.models import StripeEvent

        Subscription._base_manager.filter(organisation=org).update(status="active")
        StripeEvent.objects.filter(pk=event.pk).update(organisation=org)  # type: ignore[attr-defined]

    register_handler("test.quiet")(quiet)
    try:
        warm(org)
        before = version(org)
        deliver(stripe_event("test.quiet", {}))
        assert version(org) != before
        assert now_state(org)[1] == "active"
    finally:
        _handlers.pop("test.quiet", None)
