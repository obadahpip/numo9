"""Platform metrics (U-06-T05): MRR, active organisations, trials, conversion, churn.

Every metric **leaves demo organisations out** (organisation status ``demo`` or a ``demo``
subscription). Definitions (Phase 0 plan U-06 business rules):

- **MRR** — the sum, over subscriptions that are ``active`` or ``past_due`` (still paying, in
  grace), of the price in force today for their package and interval, normalised to a month
  (an annual price ÷ 12, rounded to the cent), in CAD cents;
- **active** — organisations with an ``active`` or ``past_due`` subscription;
- **trials** — organisations whose subscription is ``trialing``;
- **conversion** (a window, default the last 30 days) — trials converted in the window ÷ trials
  that ended in it (converted, or ended unpaid); ``None`` when no trial ended (never 0 ÷ 0);
- **churn** (the window) — subscriptions cancelled in the window ÷ active at its start (active now
  plus those cancelled in the window); ``None`` when nothing was active.

``drill_down(metric)`` answers the organisations a figure counts — the tiles' drill-down, so a
tile's number and its list always agree. ``snapshot(day)`` writes ``PlatformMetricDaily`` (nightly
job ``numo9.platform.snapshot_metrics``).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from numo9.entitlements.models import Subscription, SubscriptionStatus, TrialRegistry
from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job
from numo9.packages.models import BillingInterval
from numo9.packages.prices import current_prices
from numo9.tenancy.models import Organisation, OrganisationStatus

from .models import PlatformMetricDaily

PAYING = (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)
WINDOW_DAYS = 30
SNAPSHOT_JOB = "numo9.platform.snapshot_metrics"


def _live() -> QuerySet[Subscription]:
    """Current subscriptions of non-demo organisations (platform-wide, no tenant context)."""
    return Subscription._base_manager.filter(deleted_at__isnull=True).exclude(
        Q(status=SubscriptionStatus.DEMO) | Q(organisation__status=OrganisationStatus.DEMO)
    )


def monthly_cents(subscription: Subscription, on_date: dt.date) -> int:
    if subscription.package is None:
        return 0
    price = current_prices(subscription.package, on_date).get(subscription.interval)
    if price is None:
        return 0
    if subscription.interval == BillingInterval.YEAR:
        return int((Decimal(price.amount_cents) / 12).quantize(Decimal("1"), ROUND_HALF_UP))
    return int(price.amount_cents)


def _rate(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"), ROUND_HALF_UP)


@dataclass(frozen=True)
class Metrics:
    date: dt.date
    mrr_cents: int
    active: int
    trials: int
    conversion_rate: Decimal | None
    churn_rate: Decimal | None
    converted: int
    trials_ended: int
    cancelled: int
    active_at_start: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "mrr_cents": self.mrr_cents,
            "active": self.active,
            "trials": self.trials,
            "conversion_rate": self.conversion_rate,
            "churn_rate": self.churn_rate,
            "converted": self.converted,
            "trials_ended": self.trials_ended,
            "cancelled": self.cancelled,
            "active_at_start": self.active_at_start,
        }


def compute(now: dt.datetime | None = None, window_days: int = WINDOW_DAYS) -> Metrics:
    now = now or timezone.now()
    today = timezone.localdate(now)
    start = now - dt.timedelta(days=window_days)
    live = _live()
    paying = list(live.filter(status__in=PAYING).select_related("package"))
    mrr = sum(monthly_cents(subscription, today) for subscription in paying)
    trials = live.filter(status=SubscriptionStatus.TRIALING).count()
    registry = TrialRegistry.objects.exclude(organisation__status=OrganisationStatus.DEMO)
    converted = registry.filter(converted_at__gte=start, converted_at__lte=now).count()
    ended_unpaid = live.filter(
        status=SubscriptionStatus.READ_ONLY,
        status_reason="trial_ended",
        current_period_end__gte=start,
        current_period_end__lte=now,
    ).count()
    cancelled = live.filter(
        status=SubscriptionStatus.CANCELLED,
        status_changed_at__gte=start,
        status_changed_at__lte=now,
    ).count()
    active_at_start = len(paying) + cancelled
    return Metrics(
        date=today,
        mrr_cents=mrr,
        active=len(paying),
        trials=trials,
        conversion_rate=_rate(converted, converted + ended_unpaid),
        churn_rate=_rate(cancelled, active_at_start),
        converted=converted,
        trials_ended=converted + ended_unpaid,
        cancelled=cancelled,
        active_at_start=active_at_start,
    )


def drill_down(metric: str) -> QuerySet[Organisation]:
    """The organisations a tile counts: ``active`` (and ``mrr``), ``trials``."""
    live = _live()
    if metric in ("active", "mrr"):
        ids = live.filter(status__in=PAYING).values("organisation_id")
    elif metric == "trials":
        ids = live.filter(status=SubscriptionStatus.TRIALING).values("organisation_id")
    else:
        raise KeyError(metric)
    return Organisation.objects.filter(pk__in=ids).order_by("name", "pk")


def history(current: Metrics, days: int) -> list[dict[str, Any]]:
    """The daily snapshots of the last ``days`` days, oldest first; today is the live figure
    (``current``), so the chart's last point always equals the tiles."""
    since = current.date - dt.timedelta(days=days - 1)
    rows = PlatformMetricDaily.objects.filter(date__gte=since, date__lt=current.date).order_by(
        "date"
    )
    points = [
        {
            "date": row.date,
            "mrr_cents": row.mrr_cents,
            "active": row.active,
            "trials": row.trials,
            "conversion_rate": row.conversion_rate,
            "churn_rate": row.churn_rate,
        }
        for row in rows
    ]
    today = current.as_dict()
    points.append(
        {
            key: today[key]
            for key in ("date", "mrr_cents", "active", "trials", "conversion_rate", "churn_rate")
        }
    )
    return points


def snapshot(now: dt.datetime | None = None) -> PlatformMetricDaily:
    metrics = compute(now)
    row, _created = PlatformMetricDaily.objects.update_or_create(
        date=metrics.date,
        defaults={
            "mrr_cents": metrics.mrr_cents,
            "active": metrics.active,
            "trials": metrics.trials,
            "conversion_rate": metrics.conversion_rate,
            "churn_rate": metrics.churn_rate,
        },
    )
    return row


@platform_job(name=SNAPSHOT_JOB, queue=DEFAULT)
def snapshot_metrics_job() -> str:
    return str(snapshot().date)
