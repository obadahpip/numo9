"""Staff activity from the audit log (V-05-T07): daily counts per person, materialised.

``aggregate(since, until, users=None)`` recomputes ``StaffActivityDaily`` for those days from
``audit_event`` — one ``GROUP BY actor_user, day`` query; a day is a Toronto calendar day
(``ACTIVITY_TIME_ZONE``); every event the person made counts (``actor_user`` = them, as
themselves or signed in by Numo9 support), whatever the organisation or practice. Days whose
count fell to zero are deleted, so the table always equals the audit log for the period. The
daily job ``numo9.staff.aggregate_activity`` recomputes yesterday and today (events of the day
keep arriving); ``manage.py``-free backfill: ``aggregate(since=…)``.

``activity_of(user, days=365)`` answers the heatmap's days (non-zero only) and the total.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .models import StaffActivityDaily

ACTIVITY_TIME_ZONE = ZoneInfo("America/Toronto")
JOB = "numo9.staff.aggregate_activity"


def local_today(now: dt.datetime | None = None) -> dt.date:
    return (now or timezone.now()).astimezone(ACTIVITY_TIME_ZONE).date()


def _bounds(since: dt.date, until: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(since, dt.time.min, tzinfo=ACTIVITY_TIME_ZONE)
    end = dt.datetime.combine(until + dt.timedelta(days=1), dt.time.min, tzinfo=ACTIVITY_TIME_ZONE)
    return start, end


def audit_counts(
    since: dt.date, until: dt.date, users: list[int] | None = None
) -> dict[tuple[int, dt.date], int]:
    """``{(user id, day): events}`` straight from the audit log."""
    start, end = _bounds(since, until)
    rows = AuditEvent.platform_events.filter(
        actor_user__isnull=False, created_at__gte=start, created_at__lt=end
    )
    if users is not None:
        rows = rows.filter(actor_user_id__in=users)
    grouped = (
        rows.annotate(day=TruncDate("created_at", tzinfo=ACTIVITY_TIME_ZONE))
        .values("actor_user_id", "day")
        .annotate(n=Count("id"))
        .order_by()
    )
    return {(row["actor_user_id"], row["day"]): int(row["n"]) for row in grouped}


def aggregate(since: dt.date, until: dt.date | None = None, users: list[int] | None = None) -> int:
    """Recompute the days ``since``…``until`` (inclusive); answers the rows written."""
    until = until or local_today()
    counts = audit_counts(since, until, users)
    with transaction.atomic():
        stale = StaffActivityDaily.objects.filter(date__gte=since, date__lte=until)
        if users is not None:
            stale = stale.filter(user_id__in=users)
        stale.exclude(
            pk__in=[row.pk for row in stale if (row.user_id, row.date) in counts]
        ).delete()
        for (user_id, day), count in counts.items():
            StaffActivityDaily.objects.update_or_create(
                user_id=user_id, date=day, defaults={"count": count}
            )
    return len(counts)


def activity_of(user: Any, days: int = 365, today: dt.date | None = None) -> dict[str, Any]:
    today = today or local_today()
    since = today - dt.timedelta(days=days - 1)
    rows = StaffActivityDaily.objects.filter(user=user, date__gte=since, date__lte=today).order_by(
        "date"
    )
    points = [{"date": row.date, "count": row.count} for row in rows]
    return {
        "from": since,
        "to": today,
        "total": sum(point["count"] for point in points),
        "days": points,
    }


@platform_job(name=JOB, queue=DEFAULT)
def aggregate_activity_job() -> int:
    today = local_today()
    return aggregate(today - dt.timedelta(days=1), today)
