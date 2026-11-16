"""U-02-T14 — A future-dated price leaves current subscriptions unchanged.

Acceptance: a renewal before the effective date uses the old price. Fixture: Growth at $49/month
since 1 Jan 2026; a new version at $59/month from 1 Mar 2027 is scheduled (synced to Stripe as a
new Price — the old one untouched). A subscription renewing on 15 Feb 2027 renews at $49: the
renewal-price job leaves it on the old Stripe price; the one renewing on 15 Mar 2027 is moved to
the new price (no proration) in the last hour before that renewal, once. The console's count of
subscriptions affected names only that interval's subscribers; annual subscribers are untouched by
a monthly price; a subscription with a pending downgrade or cancelling at period end is left alone.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from django.test import override_settings

from numo9.billing.changes import apply_renewal_prices, renewal_price
from numo9.entitlements.models import Subscription
from numo9.entitlements.source import Subscriptions
from numo9.packages.models import Package, PackagePrice
from numo9.tenancy.models import Organisation
from tests.billing_helpers import FakeGateway, owned_org, sold_package

pytestmark = pytest.mark.django_db
NEW_FROM = dt.date(2027, 3, 1)
BEFORE = dt.datetime(2027, 2, 15, 17, 0, tzinfo=dt.UTC)
AFTER = dt.datetime(2027, 3, 15, 17, 0, tzinfo=dt.UTC)
HOUR = dt.timedelta(hours=1)


@pytest.fixture(autouse=True)
def prices() -> Iterator[None]:
    FakeGateway.reset()
    growth = sold_package("growth", 4900, 49000)
    old = PackagePrice.objects.get(package=growth, interval="month")
    old.effective_to = NEW_FROM - dt.timedelta(days=1)
    old.save()
    PackagePrice.objects.create(
        package=growth,
        interval="month",
        amount_cents=5900,
        effective_from=NEW_FROM,
        stripe_price_id="price_growth_month_2027",
    )
    with override_settings(NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway"):
        yield


def subscriber(n: int, renews: dt.datetime, interval: str = "month", **extra: Any) -> Organisation:
    org: Organisation = owned_org(f"Org {n} Inc.", f"owner{n}@maple.ca")[0]
    sub_id = f"sub_future_{n}"
    Subscription._base_manager.filter(organisation=org).update(
        stripe_customer_id=f"cus_future_{n}",
        stripe_subscription_id=sub_id,
        status="active",
        package=Package.objects.get(code="growth"),
        interval=interval,
        current_period_end=renews,
        **extra,
    )
    FakeGateway.subscriptions[sub_id] = {
        "id": sub_id,
        "items": {"data": [{"id": f"si_{n}", "price": {"id": f"price_growth_{interval}"}}]},
    }
    return org


def moved() -> list[dict[str, Any]]:
    return [params for call, params in FakeGateway.calls if call == "change_price"]


def test_renewal_before_the_effective_date_uses_the_old_price() -> None:
    before = subscriber(1, BEFORE)
    sub = Subscription._base_manager.get(organisation=before)
    assert renewal_price(sub).amount_cents == 4900  # type: ignore[union-attr]
    assert apply_renewal_prices(BEFORE - HOUR / 2) == 0
    assert moved() == []
    assert PackagePrice.objects.get(stripe_price_id="price_growth_month").amount_cents == 4900


def test_renewal_after_the_effective_date_moves_once() -> None:
    after = subscriber(2, AFTER)
    sub = Subscription._base_manager.get(organisation=after)
    assert renewal_price(sub).amount_cents == 5900  # type: ignore[union-attr]
    assert apply_renewal_prices(AFTER - 2 * HOUR) == 0  # not yet: last hour only
    assert apply_renewal_prices(AFTER - HOUR / 2) == 1
    assert moved()[0] == {
        "subscription": "sub_future_2",
        "item": "si_2",
        "price": "price_growth_month_2027",
        "proration_behavior": "none",
        "proration_date": None,
        "idempotency_key": moved()[0]["idempotency_key"],
    }
    FakeGateway.subscriptions["sub_future_2"]["items"]["data"][0]["price"]["id"] = (
        "price_growth_month_2027"
    )
    assert apply_renewal_prices(AFTER - HOUR / 4) == 0


def test_annual_and_leaving_subscribers_are_untouched() -> None:
    subscriber(3, AFTER, interval="year")
    subscriber(4, AFTER, cancel_at_period_end=True)
    assert apply_renewal_prices(AFTER - HOUR / 2) == 0


def test_affected_count_is_per_interval() -> None:
    subscriber(5, BEFORE)
    subscriber(6, AFTER)
    subscriber(7, AFTER, interval="year")
    growth = Package.objects.get(code="growth")
    assert Subscriptions().affected_by_price(growth, "month", NEW_FROM) == 2
    assert Subscriptions().affected_by_price(growth, "year", NEW_FROM) == 1
