"""Impersonation sessions (U-06-T08…T10): a platform staff member acts as one user of one
organisation, for a reason, for a limited time.

``start()`` creates the ``ImpersonationSession`` row (one per session) after the rules:

- the reason is required (trimmed, at most 500 characters);
- the duration is 1–120 minutes (default 30);
- the user acted as is a member of **that** organisation (a user who owns many organisations is
  only ever seen in the one chosen — edge case "scope to one org"), is not the staff member
  themself and holds no platform role (staff never act as staff);
- a staff member has one open session at a time (an expired one still open is closed first).

``current()`` answers the staff member's open session, closing it as expired when its time is up.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.rbac.resolver import platform_permissions
from numo9.tenancy.models import Organisation, OrganisationMember

from .models import DEFAULT_MINUTES, MAX_MINUTES, ImpersonationEndReason, ImpersonationSession


class ImpersonationRefused(Exception):
    """A session that can't start; ``code`` is the error catalogue's reason."""

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


def _close_expired(actor: Any, now: dt.datetime) -> None:
    for stale in ImpersonationSession.objects.filter(
        actor=actor, ended_at__isnull=True, expires_at__lte=now
    ):
        stale.end(ImpersonationEndReason.EXPIRED, now)


def start(
    actor: Any,
    target_user: Any,
    organisation: Organisation,
    reason: str,
    minutes: int = DEFAULT_MINUTES,
    now: dt.datetime | None = None,
) -> ImpersonationSession:
    now = now or timezone.now()
    reason = (reason or "").strip()
    if not reason:
        raise ImpersonationRefused("reason_required")
    if len(reason) > 500:
        raise ImpersonationRefused("reason_too_long", limit=500)
    if not 1 <= int(minutes) <= MAX_MINUTES:
        raise ImpersonationRefused("bad_duration", max=MAX_MINUTES)
    if target_user.pk == actor.pk:
        raise ImpersonationRefused("not_self")
    if not OrganisationMember.objects.filter(organisation=organisation, user=target_user).exists():
        raise ImpersonationRefused("not_a_member")
    if platform_permissions(target_user):
        raise ImpersonationRefused("platform_user")
    _close_expired(actor, now)
    try:
        with transaction.atomic():
            return ImpersonationSession.objects.create(
                actor=actor,
                target_user=target_user,
                organisation=organisation,
                reason=reason,
                started_at=now,
                expires_at=now + dt.timedelta(minutes=int(minutes)),
            )
    except IntegrityError:
        raise ImpersonationRefused("already_open") from None


def current(actor: Any, now: dt.datetime | None = None) -> ImpersonationSession | None:
    """The actor's open session, or ``None`` (an expired one is closed on the way)."""
    now = now or timezone.now()
    session = (
        ImpersonationSession.objects.select_related("target_user", "organisation")
        .filter(actor=actor, ended_at__isnull=True)
        .first()
    )
    if session is None:
        return None
    if not session.is_open(now):
        session.end(ImpersonationEndReason.EXPIRED, now)
        return None
    return session


def end_on_logout(sender: Any, request: Any = None, user: Any = None, **kwargs: Any) -> None:
    """Signing out ends the staff member's open session (``ended``)."""
    if user is None:
        return
    actor = getattr(request, "audit_impersonator", None) or user
    for session in ImpersonationSession.objects.filter(actor=actor, ended_at__isnull=True):
        session.end(ImpersonationEndReason.ENDED)
