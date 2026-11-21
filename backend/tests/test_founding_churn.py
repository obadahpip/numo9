"""U-08-T06 — Churn rule config + evaluation on cancel/return (and the refund release window).

Acceptance: each rule fixture behaves as configured — ``keep_on_return`` keeps the slot whenever
the organisation comes back; ``lose_on_cancel`` releases it on cancellation; the default
``keep_if_returns_within_days`` (90) keeps it within the window and releases it after. A first
payment refunded within ``refund_release_hours`` (24) releases the slot; later, or 0, it doesn't.
The Stripe events drive the same rules.
"""

from __future__ import annotations

import datetime as dt
import time
from collections.abc import Iterator

import pytest
from django.utils import timezone

from numo9.entitlements.models import Subscription
from numo9.founding.models import ChurnRule, FoundingCounter, FoundingSlot
from numo9.founding.services import (
    allocate_founding_slot,
    founding_slot_of,
    on_cancel,
    on_refund,
    on_return,
)
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
DAY = dt.timedelta(days=1)


def configure(**fields: object) -> None:
    FoundingCounter.objects.filter(pk=1).update(**fields)


def subscription(org: Organisation) -> Subscription:
    return Subscription._base_manager.get(organisation=org)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    Subscription._base_manager.create(organisation=organisation, status="active")
    assert allocate_founding_slot(organisation, payment_ref="in_1") is not None
    return organisation


@pytest.mark.parametrize(
    ("rule", "days_away", "keeps"),
    [
        (ChurnRule.KEEP_ON_RETURN, 400, True),
        (ChurnRule.LOSE_ON_CANCEL, 1, False),
        (ChurnRule.KEEP_IF_RETURNS_WITHIN_DAYS, 89, True),
        (ChurnRule.KEEP_IF_RETURNS_WITHIN_DAYS, 90, True),
        (ChurnRule.KEEP_IF_RETURNS_WITHIN_DAYS, 91, False),
    ],
)
def test_each_rule_behaves_as_configured(
    org: Organisation, rule: str, days_away: int, keeps: bool
) -> None:
    configure(churn_rule=rule, return_window_days=90)
    cancelled = timezone.now()
    on_cancel(org, cancelled)
    on_return(org, cancelled + days_away * DAY)
    slot = FoundingSlot.objects.get(organisation=org)
    assert (slot.released_at is None) is keeps
    assert subscription(org).founding is keeps
    if keeps:
        assert slot.lapsed_at is None  # back: the cancellation is forgotten
    else:
        assert slot.release_reason in {"cancelled", "not_returned_in_time"}


def test_default_rule_is_keep_within_90_days() -> None:
    counter = FoundingCounter.current()
    assert (counter.churn_rule, counter.return_window_days) == (
        ChurnRule.KEEP_IF_RETURNS_WITHIN_DAYS,
        90,
    )
    assert counter.refund_release_hours == 24


def test_cancel_marks_the_slot_lapsed_but_held(org: Organisation) -> None:
    on_cancel(org, timezone.now())
    slot = FoundingSlot.objects.get(organisation=org)
    assert slot.lapsed_at is not None and slot.released_at is None
    assert FoundingCounter.current().allocated == 1  # the number is not given back


def test_released_number_is_not_reused(org: Organisation) -> None:
    configure(churn_rule=ChurnRule.LOSE_ON_CANCEL)
    on_cancel(org, timezone.now())
    other = Organisation.objects.create(name="Birch Ltd.")
    slot = allocate_founding_slot(other)
    assert slot is not None and slot.slot_no == 2


@pytest.mark.parametrize(
    ("hours", "after", "released"), [(24, 2, True), (24, 25, False), (0, 1, False)]
)
def test_refund_release_window(org: Organisation, hours: int, after: int, released: bool) -> None:
    configure(refund_release_hours=hours)
    slot = FoundingSlot.objects.get(organisation=org)
    on_refund(org, "in_1", slot.allocated_at + dt.timedelta(hours=after))
    assert (founding_slot_of(org) is None) is released


def test_refund_of_another_payment_keeps_the_slot(org: Organisation) -> None:
    on_refund(org, "in_other", timezone.now())
    assert founding_slot_of(org) is not None


# ---- through the Stripe events ----------------------------------------------------------------


@pytest.fixture
def paying() -> Iterator[Organisation]:
    FakeGateway.reset()
    sold_package("growth")
    organisation: Organisation = owned_org()[0]
    Subscription._base_manager.filter(organisation=organisation).update(
        stripe_customer_id="cus_test_0001", stripe_subscription_id="sub_1", status="active"
    )
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=int(time.time())))
    assert founding_slot_of(organisation) is not None
    yield organisation


def test_events_lose_on_cancel(paying: Organisation) -> None:
    configure(churn_rule=ChurnRule.LOSE_ON_CANCEL)
    now = int(time.time())
    deliver(
        stripe_event(
            "customer.subscription.deleted", stripe_subscription(status="canceled"), created=now
        )
    )
    assert subscription(paying).status == "cancelled"
    assert founding_slot_of(paying) is None
    assert not subscription(paying).founding


def test_events_cancel_and_return_within_window(paying: Organisation) -> None:
    now = int(time.time())
    deliver(
        stripe_event(
            "customer.subscription.deleted", stripe_subscription(status="canceled"), created=now
        )
    )
    assert FoundingSlot.objects.get(organisation=paying).lapsed_at is not None
    deliver(stripe_event("customer.subscription.updated", stripe_subscription(), created=now + 60))
    assert subscription(paying).status == "active"
    slot = FoundingSlot.objects.get(organisation=paying)
    assert slot.released_at is None and slot.lapsed_at is None
    assert subscription(paying).founding


def test_events_refund_within_a_day(paying: Organisation) -> None:
    charge = {
        "id": "ch_1",
        "object": "charge",
        "customer": "cus_test_0001",
        "invoice": "in_1",
        "refunded": True,
    }
    deliver(stripe_event("charge.refunded", charge, created=int(time.time()) + 3600))
    assert founding_slot_of(paying) is None
    assert FoundingSlot.objects.get(organisation=paying).release_reason == "refunded"
