"""U-05-T13 — trial funnel events (trial_started, reminder_sent, converted, expired) for the U-06
metrics.

Acceptance: events stored — one per step and organisation (reminders: one per milestone), at the
moment the step happens, with the package; a re-run job or re-delivered payment never adds a
second; demo organisations never recorded; the console's metrics count them over the window.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from django.utils import timezone

from numo9.entitlements.funnel import funnel_counts, record_step
from numo9.entitlements.models import FunnelStep, Subscription, TrialFunnelEvent
from numo9.entitlements.trials import run_trial_expiry, run_trial_reminders, start_trial
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.billing_helpers import FakeGateway, deliver, sold_package, stripe_event, stripe_invoice
from tests.test_platform_lists import staff
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
UTC = dt.UTC
START = dt.datetime(2026, 10, 15, 18, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def packages() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("growth")
    yield


def _trial(name: str = "Refined Interiors Inc.", email: str = "sam@refined.ca") -> Subscription:
    org = Organisation.objects.create(name=name, time_zone="America/Toronto")
    OrganisationMember.objects.create(
        organisation=org, user=user(email), role=OrganisationRole.OWNER
    )
    return start_trial(org, now=START)


def steps(org: Organisation) -> list[tuple[str, int]]:
    return list(
        TrialFunnelEvent.objects.filter(organisation=org)
        .order_by("at", "id")
        .values_list("step", "milestone")
    )


def test_a_trial_that_runs_out_records_started_reminders_expired() -> None:
    subscription = _trial()
    org = subscription.organisation
    now = START
    while now < dt.datetime(2026, 11, 16, tzinfo=UTC):
        run_trial_expiry(now)
        run_trial_reminders(now)
        now += dt.timedelta(hours=6)
    run_trial_expiry(now)  # a re-run adds nothing
    run_trial_reminders(now)
    assert steps(org) == [
        ("trial_started", -1),
        ("reminder_sent", 7),
        ("reminder_sent", 3),
        ("reminder_sent", 1),
        ("expired", -1),
        ("reminder_sent", 0),
    ]
    started = TrialFunnelEvent.objects.get(organisation=org, step="trial_started")
    assert started.at == START
    expired = TrialFunnelEvent.objects.get(organisation=org, step="expired")
    assert expired.at > subscription.current_period_end  # type: ignore[operator]


def test_first_payment_records_converted_once() -> None:
    subscription = _trial()
    org = subscription.organisation
    Subscription._base_manager.filter(pk=subscription.pk).update(
        stripe_customer_id="cus_test_0001", stripe_subscription_id="sub_1"
    )
    t0 = int(timezone.now().timestamp())
    deliver(stripe_event("customer.subscription.updated", _active(), created=t0))
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=t0 + 1))
    deliver(stripe_event("customer.subscription.updated", _active(), created=t0 + 2))
    assert [s for s, _m in steps(org)].count("converted") == 1


def _active() -> dict[str, object]:
    from tests.billing_helpers import stripe_subscription

    return stripe_subscription()


def test_demo_organisations_are_never_recorded() -> None:
    demo = Organisation.objects.create(name="Demo", is_demo=True, demo_seed_version=1)
    assert record_step(demo, FunnelStep.TRIAL_STARTED, at=START) is None
    assert not TrialFunnelEvent.objects.exists()


def test_metrics_count_the_window() -> None:
    now = timezone.now()
    for n in range(3):
        _trial(f"Org {n}", f"o{n}@x.ca")
    TrialFunnelEvent.objects.update(at=now - dt.timedelta(days=2))
    old = TrialFunnelEvent.objects.first()
    assert old is not None
    TrialFunnelEvent.objects.filter(pk=old.pk).update(at=now - dt.timedelta(days=40))
    assert funnel_counts(now - dt.timedelta(days=30), now)["trial_started"] == 2
    funnel = staff().get("/api/v1/platform/metrics").json()["funnel"]
    assert funnel == {
        "window_days": 30,
        "trial_started": 2,
        "reminder_sent": 0,
        "converted": 0,
        "expired": 0,
    }
