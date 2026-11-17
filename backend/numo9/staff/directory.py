"""The practice's staff list (V-05-T02): who works for the practice and how.

One line per member — name, email, practice role, the organisations they can open in the
practice's directory (direct assignments, groups, or every client for practice-wide roles), last
sign-in and status — plus one line per **pending** invitation (accepted invitations are members;
expired and revoked ones are not listed):

- ``active`` — signed in within the practice's dormant threshold (``Practice.dormant_days``,
  default 60);
- ``dormant`` — no sign-in for that many days or more (never signed in: counted from when they
  joined) — day 60 is dormant, day 59 is not;
- ``suspended`` — access suspended (V-05-T05): history kept, nothing reachable;
- ``pending`` — invited, not accepted yet (the invitation's expiry shown).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.utils import timezone

from numo9.tenancy.models import (
    Invitation,
    InvitationKind,
    Practice,
    PracticeMember,
    PracticeRole,
)
from numo9.workspace.search import directory_scope


def last_active(member: PracticeMember) -> dt.datetime:
    """The moment dormancy counts from: the last sign-in, else when they joined."""
    return member.user.last_login or member.created_at


def is_dormant(member: PracticeMember, now: dt.datetime | None = None) -> bool:
    now = now or timezone.now()
    days = (timezone.localdate(now) - timezone.localdate(last_active(member))).days
    return member.suspended_at is None and days >= member.practice.dormant_days


def status_of(member: PracticeMember, now: dt.datetime | None = None) -> str:
    if member.suspended_at is not None:
        return "suspended"
    return "dormant" if is_dormant(member, now) else "active"


def member_line(member: PracticeMember, now: dt.datetime | None = None) -> dict[str, Any]:
    user = member.user
    count = 0 if member.suspended_at is not None else directory_scope(user, member.practice).count()
    return {
        "id": user.public_id,
        "name": user.name,
        "email": user.email,
        "role": member.role,
        "role_label": PracticeRole(member.role).label,
        "status": status_of(member, now),
        "organisation_count": count,
        "last_login": user.last_login,
        "joined_at": member.created_at,
        "suspended_at": member.suspended_at,
        "dormant": is_dormant(member, now),
        "invitation_expires_at": None,
    }


def staff_lines(practice: Practice, now: dt.datetime | None = None) -> list[dict[str, Any]]:
    now = now or timezone.now()
    members = (
        PracticeMember.objects.filter(practice=practice)
        .select_related("user", "practice")
        .order_by("user__name", "user__email")
    )
    lines = [member_line(member, now) for member in members]
    pending = Invitation.objects.filter(
        practice=practice,
        kind=InvitationKind.PRACTICE_STAFF,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=now,
    ).order_by("email")
    for invite in pending:
        lines.append(
            {
                "id": invite.public_id,
                "name": "",
                "email": invite.email,
                "role": invite.role,
                "role_label": str(PracticeRole(invite.role).label)
                if invite.role in PracticeRole.values
                else invite.role,
                "status": "pending",
                "organisation_count": 0,
                "last_login": None,
                "joined_at": None,
                "suspended_at": None,
                "dormant": False,
                "invitation_expires_at": invite.expires_at,
            }
        )
    return lines
