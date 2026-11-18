"""Dormant staff (V-05-T06): the daily job and the dashboard widget's data.

A member who hasn't signed in for the practice's ``dormant_days`` (default 60; never signed in:
counted from joining) is **dormant** from that day on — day 60, not 59 (``directory.is_dormant``).
The job ``numo9.staff.dormant_alerts`` (daily) emails each active practice admin of the practice
once per dormant member and period of inactivity (``DormantAlert``), with a link to the member's
page where *Suspend access* is one click. The practice home's widget (``dormant_staff``) lists
the dormant members with the days since their last sign-in.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job
from numo9.tenancy.models import PracticeMember, PracticeRole

from .directory import is_dormant, last_active
from .models import DormantAlert

JOB = "numo9.staff.dormant_alerts"


def days_inactive(member: PracticeMember, now: dt.datetime) -> int:
    return (timezone.localdate(now) - timezone.localdate(last_active(member))).days


def dormant_staff(practice: Any, now: dt.datetime | None = None) -> list[dict[str, Any]]:
    now = now or timezone.now()
    members = PracticeMember.objects.filter(practice=practice, suspended_at__isnull=True)
    rows = [m for m in members.select_related("user", "practice") if is_dormant(m, now)]
    return [
        {
            "id": m.user.public_id,
            "name": m.user.name,
            "email": m.user.email,
            "role": m.role,
            "last_login": m.user.last_login,
            "days": days_inactive(m, now),
        }
        for m in sorted(rows, key=lambda m: -days_inactive(m, now))
    ]


def _admins(member: PracticeMember) -> list[Any]:
    return [
        row.user
        for row in PracticeMember.objects.select_related("user").filter(
            practice_id=member.practice_id,
            role=PracticeRole.PRACTICE_ADMIN,
            suspended_at__isnull=True,
            user__is_active=True,
        )
        if row.user_id != member.user_id
    ]


def _email(admin: Any, member: PracticeMember, days: int) -> None:
    from numo9.notifications.mail import queue_email

    link = f"{settings.FRONTEND_URL}/p/{member.practice.public_id}/staff/{member.user.public_id}"
    name = member.user.name or member.user.email
    with translation.override(getattr(admin, "locale", "") or "en-ca"):
        subject = _("%(name)s hasn't signed in for %(days)s days") % {"name": name, "days": days}
        text = _(
            "%(name)s (%(email)s) hasn't signed in to %(practice)s for %(days)s days but can "
            "still open the practice's clients. If they no longer need access, suspend it: "
            "%(link)s"
        ) % {
            "name": name,
            "email": member.user.email,
            "practice": member.practice.name,
            "days": days,
            "link": link,
        }
    queue_email(
        admin.email,
        subject,
        text,
        recipient=admin,
        kind="staff.dormant",
        metadata={"practice": str(member.practice.public_id), "member": str(member.user.public_id)},
    )


def run_dormant_alerts(now: dt.datetime | None = None) -> int:
    """Alert the admins about members dormant as of ``now``; answers the alerts sent."""
    now = now or timezone.now()
    sent = 0
    members = PracticeMember.objects.filter(suspended_at__isnull=True).select_related(
        "user", "practice"
    )
    for member in members:
        if not is_dormant(member, now):
            continue
        since = last_active(member)
        if DormantAlert.objects.filter(member=member, inactive_since=since).exists():
            continue
        admins = _admins(member)
        try:
            with transaction.atomic():
                DormantAlert.objects.create(
                    practice=member.practice,
                    member=member,
                    inactive_since=since,
                    alerted_at=now,
                    recipients=len(admins),
                )
                for admin in admins:
                    _email(admin, member, days_inactive(member, now))
        except IntegrityError:
            continue  # another run alerted at the same moment
        sent += 1
    return sent


@platform_job(name=JOB, queue=DEFAULT)
def dormant_alerts_job() -> int:
    return run_dormant_alerts()
