"""U-04-T07 — Checkout and subscription events → local state.

Acceptance: the state transitions match the table.

Covers: every Stripe status of the state table (active, trialing, past_due with a 7-day grace —
kept when already set —, unpaid, paused, canceled, incomplete and incomplete_expired leave the
status); the deleted event cancels; package from the price (or the metadata), interval, period
end, cancel at period end, payment method; checkout completed links the Stripe ids and activates
(card paid, or PAD still processing keeps access); the subscription is found by its id, its
customer or the organisation in the metadata — the checkout event before or after the
subscription event; an unknown customer fails (retried); the organisation status follows; the
event names its organisation.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest

from numo9.billing.models import StripeEvent
from numo9.billing.processing import EventFailed
from numo9.billing.subscriptions import STATE_TABLE
from numo9.entitlements.models import Subscription
from numo9.tenancy.models import Organisation
from tests.billing_helpers import (
    FakeGateway,
    deliver,
    owned_org,
    sold_package,
    stripe_event,
    stripe_subscription,
)

pytestmark = pytest.mark.django_db
T0 = 1_790_000_000


@pytest.fixture(autouse=True)
def packages() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("growth")
    sold_package("complete", 9900, 99000)
    yield


@pytest.fixture
def org() -> Organisation:
    organisation: Organisation = owned_org()[0]
    Subscription._base_manager.filter(organisation=organisation).update(
        stripe_customer_id="cus_test_0001"
    )
    return organisation


def sub(org: Organisation) -> Subscription:
    return Subscription._base_manager.get(organisation=org, deleted_at__isnull=True)


def code(subscription: Subscription) -> str:
    return subscription.package.code if subscription.package else ""


def checkout(org: Organisation, payment_status: str = "paid", **extra: object) -> dict[str, object]:
    return {
        "id": "cs_test_1",
        "object": "checkout.session",
        "mode": "subscription",
        "customer": "cus_test_0001",
        "subscription": "sub_1",
        "payment_status": payment_status,
        "metadata": {
            "numo9_org": str(org.public_id),
            "numo9_package": "growth",
            "numo9_interval": "month",
        },
        **extra,
    }


def test_state_table_is_the_plan() -> None:
    assert STATE_TABLE == {
        "active": "active",
        "trialing": "active",
        "past_due": "past_due",
        "unpaid": "read_only",
        "paused": "read_only",
        "canceled": "cancelled",
        "incomplete": None,
        "incomplete_expired": None,
    }


def test_checkout_then_subscription(org: Organisation) -> None:
    row = deliver(stripe_event("checkout.session.completed", checkout(org), created=T0))
    s = sub(org)
    assert (s.status, code(s), s.interval) == ("active", "growth", "month")
    assert (s.stripe_subscription_id, s.stripe_customer_id) == ("sub_1", "cus_test_0001")
    assert row.organisation == org and row.processed_at is not None
    org.refresh_from_db()
    assert org.status == "active"
    deliver(
        stripe_event(
            "customer.subscription.created",
            stripe_subscription(
                price="price_complete_year", interval="year", methods=["acss_debit"]
            ),
            created=T0 + 1,
        )
    )
    s = sub(org)
    assert (code(s), s.interval, s.payment_method_type) == ("complete", "year", "acss_debit")
    assert s.current_period_end == dt.datetime.fromtimestamp(1_800_000_000, tz=dt.UTC)


def test_subscription_event_before_checkout(org: Organisation) -> None:
    deliver(stripe_event("customer.subscription.created", stripe_subscription(), created=T0))
    assert sub(org).stripe_subscription_id == "sub_1" and sub(org).status == "active"
    deliver(stripe_event("checkout.session.completed", checkout(org), created=T0 - 5))
    assert sub(org).status == "active" and code(sub(org)) == "growth"


def test_pad_processing_keeps_access(org: Organisation) -> None:
    deliver(
        stripe_event(
            "checkout.session.completed",
            checkout(org, "unpaid", payment_method_types=["acss_debit"]),
            created=T0,
        )
    )
    s = sub(org)
    assert s.status == "active" and s.payment_method_type == "acss_debit"
    deliver(
        stripe_event(
            "customer.subscription.updated",
            stripe_subscription(status="incomplete"),
            created=T0 + 1,
        )
    )
    assert sub(org).status == "active"


@pytest.mark.parametrize(
    ("stripe_status", "local", "reason"),
    [
        ("active", "active", ""),
        ("trialing", "active", ""),
        ("past_due", "past_due", "payment_failed"),
        ("unpaid", "read_only", "payment_failed"),
        ("paused", "read_only", "payment_failed"),
        ("canceled", "cancelled", "cancelled"),
        ("incomplete", "trialing", ""),
        ("incomplete_expired", "trialing", ""),
    ],
)
def test_each_stripe_status(org: Organisation, stripe_status: str, local: str, reason: str) -> None:
    deliver(
        stripe_event(
            "customer.subscription.updated", stripe_subscription(status=stripe_status), created=T0
        )
    )
    s = Subscription._base_manager.filter(organisation=org).order_by("-pk").first()
    assert s is not None and (s.status, s.status_reason) == (local, reason)
    if local == "past_due":
        assert s.grace_until == dt.datetime.fromtimestamp(T0, tz=dt.UTC) + dt.timedelta(days=7)


def test_grace_is_kept_and_cleared(org: Organisation) -> None:
    deliver(
        stripe_event(
            "customer.subscription.updated", stripe_subscription(status="past_due"), created=T0
        )
    )
    grace = sub(org).grace_until
    deliver(
        stripe_event(
            "customer.subscription.updated",
            stripe_subscription(status="past_due"),
            created=T0 + 86400,
        )
    )
    assert sub(org).grace_until == grace
    deliver(
        stripe_event("customer.subscription.updated", stripe_subscription(), created=T0 + 99999)
    )
    assert sub(org).grace_until is None and sub(org).status == "active"


def test_cancel_at_period_end_then_deleted(org: Organisation) -> None:
    deliver(
        stripe_event(
            "customer.subscription.updated",
            stripe_subscription(cancel_at_period_end=True),
            created=T0,
        )
    )
    assert sub(org).cancel_at_period_end and sub(org).status == "active"
    deliver(
        stripe_event(
            "customer.subscription.deleted", stripe_subscription(status="canceled"), created=T0 + 1
        )
    )
    ended = Subscription._base_manager.get(organisation=org)
    assert ended.status == "cancelled" and not ended.cancel_at_period_end
    org.refresh_from_db()
    assert org.status == "cancelled"


def test_unknown_customer_fails_and_is_retried() -> None:
    event = stripe_event(
        "customer.subscription.updated", stripe_subscription(customer="cus_nobody"), created=T0
    )
    with pytest.raises(EventFailed):
        deliver(event)
    row = StripeEvent.objects.get()
    assert row.processed_at is None and "UnknownSubscription" in row.error
