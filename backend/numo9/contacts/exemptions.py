"""Exemption certificate expiry reminders (B-01-T08).

A certificate (``ExemptionCertificate``) that expires stops exempting the contact the day after
its expiry date, so the organisation hears about it twice: ``EXEMPTION_REMINDER_DAYS`` (30) days
before, and once it has expired. The daily platform job ``numo9.contacts.exemption_reminders``
(``tasks.py``, daily by beat) finds every certificate due a reminder — each organisation's
"today" in its own time zone — and calls the **reminder hook**:

    def hook(certificate: ExemptionCertificate, state: str, days_left: int) -> None: ...

``state`` is ``expiring`` or ``expired``. The hook is ``settings.NUMO9_EXEMPTION_REMINDER_HOOK``
(a dotted path); until notifications ship (A-07) the default writes a structured log line. Each
reminder is sent once per expiry date (``reminded_state`` / ``reminded_for``): running the job
twice the same day sends nothing new, and renewing the certificate (a new expiry date) starts
again. A certificate already expired when it is entered gets only the "expired" reminder.

The job reads across organisations with the base manager (a platform job has no organisation);
each hook call runs inside the certificate's organisation context, so the hook can use the
organisation-scoped managers.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import structlog
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.module_loading import import_string

from numo9.tenancy.context import org_context

from .models import (
    EXEMPTION_REMINDER_DAYS,
    ExemptionCertificate,
    ExemptionState,
    organisation_today,
)

if TYPE_CHECKING:
    ReminderHook = Callable[[ExemptionCertificate, str, int], None]

DEFAULT_HOOK = "numo9.contacts.exemptions.log_reminder"

log = structlog.get_logger("numo9.contacts.exemptions")


def log_reminder(certificate: ExemptionCertificate, state: str, days_left: int) -> None:
    """Default hook until notifications (A-07): a structured log line, no personal data."""
    log.info(
        "contacts.exemption.reminder",
        organisation=str(certificate.organisation.public_id),
        contact=str(certificate.contact.public_id),
        certificate=str(certificate.public_id),
        state=state,
        days_left=days_left,
        expires_on=certificate.expires_on.isoformat() if certificate.expires_on else None,
    )


def get_hook() -> ReminderHook:
    path = getattr(settings, "NUMO9_EXEMPTION_REMINDER_HOOK", DEFAULT_HOOK) or DEFAULT_HOOK
    hook: ReminderHook = import_string(path)
    return hook


def reminder_due(certificate: ExemptionCertificate, today: date) -> str | None:
    """The reminder ``certificate`` is due on ``today`` (``expiring`` / ``expired``), or None."""
    state = certificate.state(today)
    if state == ExemptionState.VALID:
        return None
    if certificate.reminded_for == certificate.expires_on and (
        certificate.reminded_state == state or certificate.reminded_state == ExemptionState.EXPIRED
    ):
        return None
    return state


def candidates(utc_today: date) -> models.QuerySet[ExemptionCertificate]:
    """Certificates that may be due a reminder somewhere in the world today (a day of margin for
    time zones); ``reminder_due`` decides per organisation."""
    horizon = utc_today + timedelta(days=EXEMPTION_REMINDER_DAYS + 1)
    return (
        ExemptionCertificate._base_manager.filter(
            deleted_at__isnull=True,
            contact__deleted_at__isnull=True,
            expires_on__isnull=False,
            expires_on__lte=horizon,
        )
        .exclude(reminded_state=ExemptionState.EXPIRED, reminded_for=models.F("expires_on"))
        .select_related("organisation", "contact")
        .order_by("organisation_id", "expires_on", "id")
    )


def send_reminders(now: Any = None) -> dict[str, int]:
    """Send every reminder due now; returns counts per state. Safe to run again."""
    moment = now or timezone.now()
    hook = get_hook()
    sent = {ExemptionState.EXPIRING.value: 0, ExemptionState.EXPIRED.value: 0}
    for certificate in candidates(moment.date()):
        today = organisation_today(certificate.organisation, now=moment)
        state = reminder_due(certificate, today)
        if state is None:
            continue
        days_left = certificate.days_left(today)
        with org_context(certificate.organisation):
            hook(certificate, state, days_left if days_left is not None else 0)
        # Bookkeeping, not a change anyone made: no audit event.
        ExemptionCertificate._base_manager.filter(pk=certificate.pk).update(
            reminded_state=state, reminded_for=certificate.expires_on
        )
        sent[state] += 1
    return sent
