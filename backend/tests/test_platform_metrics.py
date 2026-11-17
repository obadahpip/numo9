"""U-06-T05 — Metrics service: MRR, active, trials, conversion, churn (demo organisations
excluded) and the nightly ``PlatformMetricDaily`` snapshot.

Acceptance: the figures match a hand-calculated fixture —

- Basic monthly 2 900 ¢: two active + one past-due → 8 700 ¢;
- Pro annual 30 000 ¢ (2 500 ¢ a month): one active → 2 500 ¢;  MRR = 11 200 ¢, active = 4;
- a demo organisation with an active Pro subscription counts nowhere;
- trials: two trialing → 2;
- conversion (30 days): 1 converted, 1 ended unpaid in the window (1 more ended 40 days ago) →
  1 / 2 = 0.5;
- churn (30 days): 1 cancelled in the window, 4 active now → 1 / 5 = 0.2.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from numo9.entitlements.models import Subscription, TrialRegistry
from numo9.packages.models import PackagePrice
from numo9.platform import metrics
from numo9.platform.models import PlatformMetricDaily
from numo9.tenancy.models import Organisation
from tests.entitlement_helpers import package, subscribe

pytestmark = pytest.mark.django_db
NOW = dt.datetime(2026, 11, 18, 15, tzinfo=dt.UTC)


def org(name: str, plan: object, status: str, **fields: object) -> Organisation:
    made = Organisation.objects.create(name=name)
    subscribe(made, plan, status, **fields)  # type: ignore[arg-type]
    return made


def changed(organisation: Organisation, **fields: object) -> None:
    Subscription._base_manager.filter(organisation=organisation).update(**fields)


@pytest.fixture
def fixture() -> dict[str, Organisation]:
    basic = package("basic", ["accounting"])
    pro = package("pro", ["accounting"])
    for plan, interval, cents in ((basic, "month", 2900), (pro, "year", 30000)):
        PackagePrice.objects.create(
            package=plan, interval=interval, amount_cents=cents, effective_from=dt.date(2026, 1, 1)
        )
    made = {
        "a1": org("A1", basic, "active"),
        "a2": org("A2", basic, "active"),
        "pd": org("Past due", basic, "past_due"),
        "y1": org("Yearly", pro, "active", interval="year"),
        "t1": org("Trial 1", basic, "trialing"),
        "t2": org("Trial 2", basic, "trialing"),
        "gone": org("Gone", basic, "cancelled"),
        "old": org("Old cancel", basic, "cancelled"),
        "unpaid": org("Unpaid", basic, "read_only", status_reason="trial_ended"),
        "unpaid_old": org("Unpaid old", basic, "read_only", status_reason="trial_ended"),
        "demo": org("Demo", pro, "active", interval="year"),
    }
    changed(made["gone"], status_changed_at=NOW - dt.timedelta(days=3))
    changed(made["old"], status_changed_at=NOW - dt.timedelta(days=60))
    changed(made["unpaid"], current_period_end=NOW - dt.timedelta(days=5))
    changed(made["unpaid_old"], current_period_end=NOW - dt.timedelta(days=40))
    Organisation.objects.filter(pk=made["demo"].pk).update(status="demo")
    TrialRegistry.objects.create(organisation=made["a1"], converted_at=NOW - dt.timedelta(days=2))
    TrialRegistry.objects.create(
        organisation=made["demo"], normalised_email="d@x.ca", converted_at=NOW - dt.timedelta(1)
    )
    return made


def test_figures_match_the_hand_calculation(fixture: dict[str, Organisation]) -> None:
    result = metrics.compute(NOW)
    assert result.mrr_cents == 11200
    assert result.active == 4
    assert result.trials == 2
    assert (result.converted, result.trials_ended) == (1, 2)
    assert result.conversion_rate == Decimal("0.5000")
    assert (result.cancelled, result.active_at_start) == (1, 5)
    assert result.churn_rate == Decimal("0.2000")


def test_demo_organisations_are_excluded_everywhere(fixture: dict[str, Organisation]) -> None:
    for name in ("active", "mrr", "trials"):
        assert fixture["demo"] not in metrics.drill_down(name)
    assert [o.name for o in metrics.drill_down("active")] == ["A1", "A2", "Past due", "Yearly"]
    assert [o.name for o in metrics.drill_down("trials")] == ["Trial 1", "Trial 2"]


def test_rates_are_none_without_a_denominator() -> None:
    result = metrics.compute(NOW)
    assert (result.mrr_cents, result.active, result.trials) == (0, 0, 0)
    assert result.conversion_rate is None and result.churn_rate is None


def test_annual_price_is_normalised_to_a_month_rounding_half_up() -> None:
    plan = package("odd", ["accounting"])
    PackagePrice.objects.create(
        package=plan, interval="year", amount_cents=1006, effective_from=dt.date(2026, 1, 1)
    )
    org("Odd", plan, "active", interval="year")
    assert metrics.compute(NOW).mrr_cents == 84  # 1006 / 12 = 83.83 → 84


def test_nightly_snapshot_writes_one_row_per_day(fixture: dict[str, Organisation]) -> None:
    first = metrics.snapshot(NOW)
    again = metrics.snapshot(NOW + dt.timedelta(hours=1))
    assert first.pk == again.pk and PlatformMetricDaily.objects.count() == 1
    row = PlatformMetricDaily.objects.get()
    assert row.date == timezone.localdate(NOW)
    assert (row.mrr_cents, row.active, row.trials) == (11200, 4, 2)
    assert row.conversion_rate == Decimal("0.5000") and row.churn_rate == Decimal("0.2000")


def test_snapshot_job_is_scheduled_nightly() -> None:
    from django.conf import settings

    entry = settings.CELERY_BEAT_SCHEDULE[metrics.SNAPSHOT_JOB]
    assert entry["task"] == metrics.SNAPSHOT_JOB
