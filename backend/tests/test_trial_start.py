"""U-05-T04 — ``start_trial(org)``: Subscription(trialing, trial_end = local 23:59:59 day 30).

Acceptance: trial_end is stored in UTC from the organisation's time zone (zoneinfo, DST
fixtures): a Toronto trial started on 15 Oct 2026 (EDT) ends 13 Nov 2026 23:59:59 EST — across the
DST change on 1 Nov — i.e. 04:59:59 UTC on 14 Nov; a Regina trial (no DST) on the same instant
ends one hour later; the start day counts as day 1; a configured length and package are used; an
organisation that already has a subscription keeps it; the days left count on the local calendar.
"""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.entitlements.models import Subscription, SubscriptionStatus, TrialConfig
from numo9.entitlements.trials import start_trial, trial_days_left, trial_end
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationStatus
from tests.entitlement_helpers import package

pytestmark = pytest.mark.django_db
UTC = dt.UTC


def at(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0
) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, second, tzinfo=UTC)


@pytest.mark.parametrize(
    ("zone", "start", "end"),
    [
        # 15 Oct 2026 14:00 EDT; day 30 = 13 Nov (EST after 1 Nov): 23:59:59 EST = 04:59:59Z
        ("America/Toronto", at(2026, 10, 15, 18, 0), at(2026, 11, 14, 4, 59, 59)),
        ("America/Regina", at(2026, 10, 15, 18, 0), at(2026, 11, 14, 5, 59, 59)),  # no DST
        # 01:30 UTC on 16 Oct is still 15 Oct in Toronto (21:30 EDT): day 1 = 15 Oct
        ("America/Toronto", at(2026, 10, 16, 1, 30), at(2026, 11, 14, 4, 59, 59)),
        # Spring forward (8 Mar 2026) inside the trial: ends 23:59:59 EDT = 03:59:59Z
        ("America/Toronto", at(2026, 2, 20, 15, 0), at(2026, 3, 22, 3, 59, 59)),
        ("America/St_Johns", at(2026, 10, 15, 18, 0), at(2026, 11, 14, 3, 29, 59)),
    ],
)
def test_trial_end_is_local_midnight_minus_one_second_in_utc(
    zone: str, start: dt.datetime, end: dt.datetime
) -> None:
    assert trial_end(start, 30, zone) == end


def test_start_trial_creates_the_trialing_subscription() -> None:
    growth = package("growth", ["accounting", "payroll"])
    config = TrialConfig.current()
    config.package, config.days = growth, 14
    config.save()
    org = Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")
    subscription = start_trial(org, now=at(2026, 10, 15, 18, 0))
    assert subscription.status == SubscriptionStatus.TRIALING and subscription.package == growth
    assert subscription.current_period_end == at(2026, 10, 29, 3, 59, 59)  # day 14, EDT
    org.refresh_from_db()
    assert org.status == OrganisationStatus.TRIAL  # mirrored from the subscription
    assert trial_days_left(subscription, now=at(2026, 10, 15, 18, 0)) == 13
    assert trial_days_left(subscription, now=at(2026, 10, 29, 3, 0)) == 0  # last local day
    assert trial_days_left(subscription, now=at(2026, 10, 29, 4, 30)) == -1  # 30 Oct local


def test_existing_subscription_is_kept() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    first = start_trial(org)
    second = start_trial(org)
    assert first.pk == second.pk
    with org_context(org):
        assert Subscription.objects.count() == 1
