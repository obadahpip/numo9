"""Outgoing email through Celery with retries and the message log (A-07-T03).

Every email the platform sends goes through ``queue_email`` — never ``send_mail`` in a request:

    queue_email("dana@refined.ca", subject, text, html=html, organisation=org,
                kind="notifications.job.failed", recipient=user)

1. an ``EmailMessage`` row is written (``queued``) — the message log;
2. once the surrounding transaction commits (a rolled-back request emails nobody), the Celery
   task ``numo9.notifications.send_email`` is sent on the ``high`` queue;
3. the task locks the row (``SELECT … FOR UPDATE SKIP LOCKED``: two deliveries of the same
   message never send twice), sends it through Django's email backend — django-anymail's
   backend for the provider in staging/prod (``DJANGO_EMAIL_BACKEND=anymail.backends.<esp>.
   EmailBackend``, provider chosen in SP-03), Mailpit over SMTP in dev — and stores the
   provider's message id, the provider and the time: ``sent``;
4. a **temporary** failure (provider API error or outage, SMTP/network error) is retried with
   the jobs backoff (``numo9.jobs.retry.backoff_delay``: 30 s base, exponential with jitter, up to
   ``max_retries`` = 5); the row is ``retrying`` with the error and ``next_retry_at``. A
   **permanent** failure (the provider refuses the recipients, an invalid message) or the last
   retry used up → ``failed`` with the error. A row already ``sent`` (a redelivered message) is
   left alone.

Each message carries its ``public_id`` as provider metadata (``numo9_message``) and the message
type as a tag, so delivery webhooks (A-07-T08) find it again.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import timedelta
from typing import Any

from anymail.exceptions import AnymailAPIError, AnymailError, AnymailRecipientsRefused
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.utils import timezone

from numo9.jobs.queues import HIGH
from numo9.jobs.retry import backoff_delay
from numo9.security.scrubbing import scrub_text
from numo9.tenancy.models import Organisation

from .models import EMAIL_SENDABLE, EmailMessage, EmailStatus

logger = logging.getLogger("numo9.notifications.mail")

TASK_NAME = "numo9.notifications.send_email"
ERROR_MAX = 2000


class PermanentEmailError(Exception):
    """Retrying cannot deliver this message (refused recipients, invalid message)."""


def _provider_name() -> str:
    backend = str(settings.EMAIL_BACKEND)
    if backend.startswith("anymail.backends."):
        return backend.split(".")[2]
    return backend.rsplit(".", 2)[-2] if "." in backend else backend


def queue_email(
    to: str,
    subject: str,
    text: str,
    *,
    html: str = "",
    organisation: Organisation | None = None,
    recipient: Any = None,
    kind: str = "",
    language: str = "",
    from_email: str | None = None,
    reply_to: str = "",
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EmailMessage:
    """Log one email and send it through the worker once the transaction commits."""
    message = EmailMessage(
        organisation=organisation,
        to_email=to,
        recipient=recipient,
        kind=kind,
        language=language,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        reply_to=reply_to,
        subject=" ".join(subject.split())[:998],  # one header line, never a header injection
        text_body=text,
        html_body=html,
        headers=dict(headers or {}),
        metadata=dict(metadata or {}),
    )
    message.save()
    message_id = message.pk
    transaction.on_commit(lambda: send_email.apply_async(args=[message_id], queue=HIGH))
    return message


def build_message(message: EmailMessage) -> EmailMultiAlternatives:
    email = EmailMultiAlternatives(
        subject=message.subject,
        body=message.text_body,
        from_email=message.from_email,
        to=[message.to_email],
        reply_to=[message.reply_to] if message.reply_to else None,
        headers=dict(message.headers),
        connection=get_connection(),
    )
    if message.html_body:
        email.attach_alternative(message.html_body, "text/html")
    # django-anymail: metadata and tags travel with the message and come back in webhooks.
    email.metadata = {"numo9_message": str(message.public_id), **message.metadata}  # type: ignore[attr-defined]
    if message.kind:
        email.tags = [message.kind[:100]]  # type: ignore[attr-defined]
    return email


def _deliver(message: EmailMessage) -> str:
    """Send one message; return the provider's message id ('' when the backend has none)."""
    email = build_message(message)
    try:
        email.send(fail_silently=False)
    except AnymailRecipientsRefused as exc:
        raise PermanentEmailError(str(exc)) from exc
    except AnymailAPIError as exc:
        status = getattr(exc, "status_code", None)
        if status is not None and 400 <= int(status) < 500 and int(status) not in (408, 429):
            raise PermanentEmailError(str(exc)) from exc
        raise
    except AnymailError as exc:  # invalid message, unsupported feature…: never fixes itself
        raise PermanentEmailError(str(exc)) from exc
    status = getattr(email, "anymail_status", None)
    return str(getattr(status, "message_id", "") or "")


TEMPORARY = (AnymailAPIError, smtplib.SMTPException, OSError, ConnectionError)


def _claim(message_id: int) -> EmailMessage | None:
    """Lock the row for this try; None when another worker holds it or it is done."""
    row = (
        EmailMessage.platform_messages.select_for_update(skip_locked=True)
        .filter(pk=message_id)
        .first()
    )
    if row is None or row.status not in EMAIL_SENDABLE:
        return None
    return row


def _error(exc: BaseException) -> str:
    return scrub_text(f"{type(exc).__name__}: {exc}")[:ERROR_MAX]


@shared_task(bind=True, name=TASK_NAME, queue=HIGH, max_retries=None, acks_late=True)  # type: ignore[untyped-decorator]
def send_email(self: Any, message_id: int) -> str:
    """Send a logged email (see the module docstring). Returns the row's final status."""
    with transaction.atomic():
        message = _claim(message_id)
        if message is None:
            return "skipped"
        now = timezone.now()
        message.attempts += 1
        message.last_attempt_at = now
        message.provider = _provider_name()
        try:
            provider_id = _deliver(message)
        except PermanentEmailError as exc:
            message.status, message.error, message.next_retry_at = (
                EmailStatus.FAILED,
                _error(exc),
                None,
            )
            message.save()
            logger.warning("email.failed", extra={"email": message.pk, "permanent": True})
            return message.status
        except TEMPORARY as exc:
            message.error = _error(exc)
            if message.attempts > message.max_retries:
                message.status, message.next_retry_at = EmailStatus.FAILED, None
                message.save()
                logger.warning("email.failed", extra={"email": message.pk, "retries_used_up": True})
                return message.status
            delay = backoff_delay(message.attempts)
            message.status = EmailStatus.RETRYING
            message.next_retry_at = now + timedelta(seconds=delay)
            message.save()
            logger.info("email.retrying", extra={"email": message.pk, "in_seconds": round(delay)})
            countdown = delay
        else:
            message.status = EmailStatus.SENT
            message.provider_message_id = provider_id
            message.sent_at, message.error, message.next_retry_at = now, "", None
            message.save()
            return message.status
    # Outside the transaction: the row says "retrying" before the retry message exists.
    raise self.retry(countdown=countdown)
