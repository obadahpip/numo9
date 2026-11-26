"""User-activity heatmap (K-09-T19): the organisation's audit log (A-04) counted per day and per
person.

``heatmap(organisation, days=365, user=None, now=None)`` — one ``GROUP BY actor, day`` query over
the organisation's audit events in the window, a day being a calendar day in the
**organisation's** time zone: the days with activity (``date``, ``count``), the people (name,
count, last activity) and the total. Only people's events count (system events have no
person). The counts equal the audit log for the same window.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Count, Max
from django.db.models.functions import TruncDate
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.tenancy.context import org_context

MAX_DAYS = 731


def window(organisation: Any, days: int, now: dt.datetime) -> tuple[dt.datetime, ZoneInfo]:
    zone = ZoneInfo(organisation.time_zone or "America/Toronto")
    first = now.astimezone(zone).date() - dt.timedelta(days=days - 1)
    return dt.datetime.combine(first, dt.time.min, tzinfo=zone), zone


def heatmap(
    organisation: Any,
    *,
    days: int = 365,
    user: Any = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    days = max(1, min(int(days), MAX_DAYS))
    now = now or timezone.now()
    since, zone = window(organisation, days, now)
    with org_context(organisation):
        events = AuditEvent.objects.filter(
            organisation=organisation,
            actor_user__isnull=False,
            created_at__gte=since,
            created_at__lte=now,
        )
        if user is not None:
            events = events.filter(actor_user=user)
        rows = list(
            events.annotate(day=TruncDate("created_at", tzinfo=zone))
            .values("day", "actor_user", "actor_user__name", "actor_user__email")
            .annotate(count=Count("id"), last=Max("created_at"))
            .order_by("day")
        )
    per_day: dict[dt.date, int] = defaultdict(int)
    people: dict[int, dict[str, Any]] = {}
    for row in rows:
        per_day[row["day"]] += row["count"]
        person = people.setdefault(
            row["actor_user"],
            {
                "name": row["actor_user__name"] or row["actor_user__email"],
                "count": 0,
                "last": None,
            },
        )
        person["count"] += row["count"]
        if person["last"] is None or row["last"] > person["last"]:
            person["last"] = row["last"]
    from numo9.accounts.models import User

    ids = {u.pk: str(u.public_id) for u in User.objects.filter(pk__in=list(people))}
    return {
        "from": since.date().isoformat(),
        "to": now.astimezone(zone).date().isoformat(),
        "time_zone": str(zone),
        "total": sum(per_day.values()),
        "days": [{"date": d.isoformat(), "count": n} for d, n in sorted(per_day.items())],
        "people": sorted(
            (
                {
                    "id": ids.get(pk, ""),
                    "name": p["name"],
                    "count": p["count"],
                    "last": p["last"].astimezone(zone).isoformat() if p["last"] else None,
                }
                for pk, p in people.items()
            ),
            key=lambda p: (-int(p["count"]), str(p["name"])),
        ),
    }
