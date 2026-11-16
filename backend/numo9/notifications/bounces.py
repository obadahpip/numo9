"""Bounces and complaints from the email provider (A-07-T08).

The provider posts delivery events to django-anymail's tracking webhook
(``/webhooks/email/<provider>/tracking/``, HTTP basic auth with ``ANYMAIL_WEBHOOK_SECRET``);
anymail normalises them and sends the ``tracking`` signal, handled here:

- ``bounced`` / ``rejected`` (the provider refused because the address bounced before) →
  ``bounced``; ``complained`` (marked as spam) → ``complained``; other events (delivered,
  opened…) are ignored — the app sends transactional email only and does not track opens;
- the logged message (``EmailMessage``, found by the ``numo9_message`` metadata or else the
  provider's message id) gets that status and the event time;
- the address is **flagged**: ``ContactPerson.email_status`` of the people with that address in
  the message's organisation (B-01: "email bounced" on the contact), and ``User.email_status`` of
  the user with that address;
- the address is **suppressed for 30 days** (``EmailSuppression``): emails queued to it are
  logged ``failed`` ("suppressed") and not sent.

Events for addresses or messages Numo9 doesn't know are ignored (the webhook still answers 200,
so the provider doesn't retry).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from anymail.signals import AnymailTrackingEvent, tracking
from django.dispatch import receiver
from django.utils import timezone

from numo9.accounts.models import User

from .models import EmailMessage, EmailStatus, EmailSuppression

logger = logging.getLogger("numo9.notifications.bounces")

SUPPRESSION = timedelta(days=30)
STATUS_FOR = {
    "bounced": EmailStatus.BOUNCED,
    "rejected": EmailStatus.BOUNCED,
    "complained": EmailStatus.COMPLAINED,
}


def _message_for(event: AnymailTrackingEvent) -> EmailMessage | None:
    metadata = event.metadata or {}
    public_id = metadata.get("numo9_message")
    rows = EmailMessage.platform_messages
    if public_id:
        found = rows.filter(public_id=public_id).first()
        if found is not None:
            return found
    if event.message_id:
        return rows.filter(provider_message_id=str(event.message_id)).first()
    return None


def suppressed_until(address: str) -> Any:
    row = EmailSuppression.objects.filter(email=address.strip().lower(), until__gt=timezone.now())
    return row.values_list("until", flat=True).first()


def record_problem(
    address: str, status: str, *, organisation: Any = None, detail: str = ""
) -> None:
    """Flag ``address`` (contacts of ``organisation``, the user) and suppress it 30 days."""
    from numo9.contacts.models import ContactPerson

    address = address.strip().lower()
    now = timezone.now()
    reason = "complained" if status == EmailStatus.COMPLAINED else "bounced"
    EmailSuppression.objects.update_or_create(
        email=address,
        defaults={"reason": reason, "until": now + SUPPRESSION, "detail": detail[:500]},
    )
    User.objects.filter(email=address).update(email_status=reason, email_status_at=now)
    if organisation is not None:
        ContactPerson.objects.unscoped(reason="email bounce webhook (A-07-T08)").filter(
            organisation=organisation, email=address, deleted_at__isnull=True
        ).update(email_status=reason, email_status_at=now)


@receiver(tracking)
def on_delivery_event(
    sender: Any, event: AnymailTrackingEvent, esp_name: str, **kwargs: Any
) -> None:
    status = STATUS_FOR.get(event.event_type)
    if status is None:
        return
    message = _message_for(event)
    address = (event.recipient or (message.to_email if message else "") or "").strip().lower()
    if not address:
        return
    detail = str(event.description or event.mta_response or "")
    if message is not None:
        message.status = status
        message.event_at = event.timestamp or timezone.now()
        message.error = detail[:2000]
        message.save(update_fields=["status", "event_at", "error", "updated_at"])
    record_problem(
        address, status, organisation=message.organisation if message else None, detail=detail
    )
    logger.info("email.delivery_problem", extra={"esp": esp_name, "status": status})
