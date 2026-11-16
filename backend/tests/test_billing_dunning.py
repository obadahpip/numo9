"""U-04-T09 — Dunning scheduler. Acceptance (fixture clock): read-only exactly at grace end.

A renewal fails at T: past due, grace until T + 7 days, day-0 reminder at once. With the clock
set: nothing new before day 3; day 3 and day 5 reminders (email in the owner's language + in-app
notification); at T + 7 days − 1 second still past due; at T + 7 days exactly read-only
(reason ``payment_failed``) with the day-7 notice; every step once — running the job again, or a
re-delivered failure event, sends nothing; a job that missed days takes only the latest due step;
a payment in between stops the dunning; a new failure later starts a new cycle; the entitlement
engine answers read-only from the grace end even before the job runs.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest

from numo9.billing.dunning import due_day, run_dunning
from numo9.billing.models import DunningReminder
from numo9.entitlements.cache import entitlements_for
from numo9.entitlements.models import Subscription
from numo9.notifications.models import EmailMessage, Notification
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.billing_helpers import (
    FakeGateway,
    deliver,
    owned_org,
    sold_package,
    stripe_event,
    stripe_invoice,
)

pytestmark = pytest.mark.django_db
T = 1_790_000_000
FAILED = dt.datetime.fromtimestamp(T, tz=dt.UTC)
DAY = dt.timedelta(days=1)


@pytest.fixture(autouse=True)
def packages() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("growth")
    yield


@pytest.fixture
def org() -> Organisation:
    organisation: Organisation = owned_org()[0]
    Subscription._base_manager.filter(organisation=organisation).update(
        stripe_customer_id="cus_test_0001", stripe_subscription_id="sub_1", status="active"
    )
    deliver(stripe_event("invoice.payment_failed", stripe_invoice(status="open"), created=T))
    return organisation


def sub(org: Organisation) -> Subscription:
    return Subscription._base_manager.get(organisation=org)


def emails(org: Organisation) -> list[str]:
    return list(
        EmailMessage.platform_messages.filter(kind__startswith="dunning")
        .order_by("pk")
        .values_list("kind", flat=True)
    )


def steps(org: Organisation) -> list[int]:
    with org_context(org):
        return list(DunningReminder.objects.order_by("day").values_list("day", flat=True))


def test_schedule_and_read_only_exactly_at_grace_end(org: Organisation) -> None:
    s = sub(org)
    assert s.status == "past_due" and s.grace_until == FAILED + 7 * DAY
    assert steps(org) == [0] and emails(org) == ["dunning.day0"]
    assert run_dunning(FAILED + 2 * DAY) == {"reminders": 0, "read_only": 0}
    assert run_dunning(FAILED + 3 * DAY) == {"reminders": 1, "read_only": 0}
    assert run_dunning(FAILED + 3 * DAY + dt.timedelta(hours=1)) == {"reminders": 0, "read_only": 0}
    assert run_dunning(FAILED + 5 * DAY) == {"reminders": 1, "read_only": 0}
    run_dunning(FAILED + 7 * DAY - dt.timedelta(seconds=1))
    assert sub(org).status == "past_due"
    assert run_dunning(FAILED + 7 * DAY) == {"reminders": 0, "read_only": 1}
    s = sub(org)
    assert (s.status, s.status_reason) == ("read_only", "payment_failed")
    assert s.status_changed_at is not None
    assert steps(org) == [0, 3, 5, 7]
    assert emails(org) == ["dunning.day0", "dunning.day3", "dunning.day5", "dunning.day7"]
    with org_context(org):
        keys = list(Notification.objects.order_by("pk").values_list("title_key", flat=True))
    assert keys == ["notifications.billing.payment_failed"] * 3 + [
        "notifications.billing.read_only"
    ]
    assert run_dunning(FAILED + 8 * DAY) == {"reminders": 0, "read_only": 0}
    org.refresh_from_db()
    assert org.status == "read_only"


def test_redelivered_failure_sends_nothing(org: Organisation) -> None:
    deliver(stripe_event("invoice.payment_failed", stripe_invoice(status="open"), created=T + 60))
    assert steps(org) == [0] and len(emails(org)) == 1


def test_missed_days_take_only_the_latest_step(org: Organisation) -> None:
    assert run_dunning(FAILED + 6 * DAY) == {"reminders": 1, "read_only": 0}
    assert steps(org) == [0, 5]


def test_payment_stops_the_dunning(org: Organisation) -> None:
    run_dunning(FAILED + 3 * DAY)
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=T + 4 * 86400))
    assert sub(org).status == "active"
    assert run_dunning(FAILED + 7 * DAY) == {"reminders": 0, "read_only": 0}
    assert sub(org).status == "active" and steps(org) == [0, 3]


def test_a_later_failure_starts_a_new_cycle(org: Organisation) -> None:
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=T + 86400))
    later = T + 40 * 86400
    deliver(
        stripe_event("invoice.payment_failed", stripe_invoice("in_2", status="open"), created=later)
    )
    assert sub(org).grace_until == dt.datetime.fromtimestamp(later, tz=dt.UTC) + 7 * DAY
    assert steps(org) == [0, 0]


def test_due_day() -> None:
    s = Subscription(grace_until=FAILED + 7 * DAY)
    assert [due_day(s, FAILED + d * DAY) for d in (0, 1, 3, 4, 5, 6)] == [0, 0, 3, 3, 5, 5]
    assert due_day(s, FAILED - DAY) is None and due_day(s, FAILED + 7 * DAY) == 7
    assert due_day(Subscription(), FAILED) is None


def test_entitlements_are_read_only_from_grace_end(org: Organisation) -> None:
    Subscription._base_manager.filter(organisation=org).update(
        grace_until=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)
    )
    org.refresh_from_db()
    assert entitlements_for(org).mode == "read_only"
