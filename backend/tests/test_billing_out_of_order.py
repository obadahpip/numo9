"""U-04-T15 — Out-of-order event resolution. Acceptance (property): shuffled events → same state.

A subscription's life as Stripe would report it (checkout, subscription created, invoices paid, a
failed renewal and its recovery, an upgrade, cancellation at period end, deletion), each event
with its own ``created`` second. Hypothesis takes any subset of that timeline and any delivery
order: processing the events in that order ends in exactly the state chronological processing
gives (status, reason, grace end, package, interval, cancellation). Also: an older event never
overwrites a newer one; on the same second the further-along status wins.
"""

from __future__ import annotations

import datetime as dt
import itertools
from collections.abc import Iterator
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.billing.subscriptions import PRECEDENCE, is_newer
from numo9.entitlements.models import Subscription
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
T = int(dt.datetime.now(dt.UTC).timestamp()) - 3600
_runs = itertools.count(1)


@pytest.fixture(autouse=True)
def packages() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("growth", 4900, 49000)
    sold_package("complete", 9900, 99000, products=("accounting", "payroll"))
    yield


def timeline(org: Any, n: int) -> list[dict[str, Any]]:
    """The lifecycle, one event per second, ids unique to this run."""
    cus, sub = f"cus_ooo_{n}", f"sub_ooo_{n}"
    meta = {"numo9_org": str(org.public_id), "numo9_package": "growth", "numo9_interval": "month"}

    def s(**kw: Any) -> dict[str, Any]:
        return stripe_subscription(sub_id=sub, customer=cus, **kw)

    def i(inv: str, status: str) -> dict[str, Any]:
        return stripe_invoice(f"in_{n}_{inv}", status=status, customer=cus, subscription=sub)

    events = [
        (
            "checkout.session.completed",
            {
                "mode": "subscription",
                "customer": cus,
                "subscription": sub,
                "payment_status": "paid",
                "metadata": meta,
            },
        ),
        ("customer.subscription.created", s()),
        ("invoice.paid", i("1", "paid")),
        ("invoice.payment_failed", i("2", "open")),
        ("customer.subscription.updated", s(status="past_due")),
        ("invoice.paid", i("2", "paid")),
        ("customer.subscription.updated", s()),
        ("customer.subscription.updated", s(price="price_complete_month")),
        (
            "customer.subscription.updated",
            s(price="price_complete_month", cancel_at_period_end=True),
        ),
        ("customer.subscription.deleted", s(status="canceled", price="price_complete_month")),
    ]
    return [
        stripe_event(kind, obj, created=T + k, event_id=f"evt_ooo_{n}_{k}")
        for k, (kind, obj) in enumerate(events)
    ]


def final_state(events: list[dict[str, Any]]) -> tuple[Any, ...]:
    org, _ = owned_org(f"Org {next(_runs)} Inc.", f"o{next(_runs)}@maple.ca")
    n = next(_runs)
    Subscription._base_manager.filter(organisation=org).update(stripe_customer_id=f"cus_ooo_{n}")
    mapped = [{**e, "id": e["id"].replace("_X_", f"_{n}_")} for e in _rebind(events, n)]
    for event in mapped:
        deliver(event)
    s = Subscription._base_manager.filter(organisation=org).order_by("-pk").first()
    assert s is not None
    return (
        s.status,
        s.status_reason,
        s.grace_until,
        s.package.code if s.package else None,
        s.interval,
        s.cancel_at_period_end,
    )


def _rebind(events: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """The same events for a fresh organisation (customer, subscription and event ids)."""
    import json

    text = json.dumps(events).replace("_ooo_X", f"_ooo_{n}").replace("in_X_", f"in_{n}_")
    return list(json.loads(text))


def template() -> list[dict[str, Any]]:
    class _Org:
        public_id = "00000000-0000-0000-0000-000000000000"

    return timeline(_Org(), "X")  # type: ignore[arg-type]


INDICES = list(range(len(template())))


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    chosen=st.lists(st.sampled_from(INDICES), unique=True, min_size=1).map(sorted),
    data=st.data(),
)
def test_shuffled_events_end_in_the_same_state(chosen: list[int], data: st.DataObject) -> None:
    events = [e for k, e in enumerate(template()) if k in chosen]
    shuffled = data.draw(st.permutations(events))
    for batch in (events, shuffled):
        _fix_metadata(batch)
    assert final_state(list(shuffled)) == final_state(events)


def _fix_metadata(events: list[dict[str, Any]]) -> None:
    """The checkout names a placeholder organisation; the lookup goes by customer instead."""
    for e in events:
        obj = e["data"]["object"]
        if e["type"] == "checkout.session.completed":
            obj["metadata"] = {k: v for k, v in obj["metadata"].items() if k != "numo9_org"}


def test_older_event_never_overwrites() -> None:
    org, _ = owned_org()
    Subscription._base_manager.filter(organisation=org).update(stripe_customer_id="cus_test_0001")
    deliver(
        stripe_event(
            "customer.subscription.deleted", stripe_subscription(status="canceled"), created=T + 10
        )
    )
    deliver(stripe_event("customer.subscription.updated", stripe_subscription(), created=T + 5))
    s = Subscription._base_manager.get(organisation=org)
    assert s.status == "cancelled"
    assert s.stripe_event_created == dt.datetime.fromtimestamp(T + 10, tz=dt.UTC)


def test_same_second_precedence() -> None:
    at = dt.datetime.fromtimestamp(T, tz=dt.UTC)
    s = Subscription(status="past_due", stripe_event_created=at)
    assert is_newer(s, at, "cancelled") and is_newer(s, at, "read_only")
    assert not is_newer(s, at, "active")
    assert not is_newer(s, at - dt.timedelta(seconds=1), "cancelled")
    assert is_newer(Subscription(), at, "active")
    assert sorted(PRECEDENCE, key=PRECEDENCE.__getitem__) == [
        "trialing",
        "active",
        "past_due",
        "read_only",
        "cancelled",
    ]
