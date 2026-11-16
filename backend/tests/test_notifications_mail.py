"""A-07-T03 — Email sending via django-anymail through Celery with retries; message log table.

Acceptance: a failed send is retried — a temporary failure (provider outage, SMTP error) leaves
the message ``retrying`` with the error, the attempt count and the next try time, and a retry
message is sent with the jobs backoff; the next try sends it (``sent``, provider message id kept).
Also: the message is logged before sending and sent only after commit (nothing on rollback);
permanent failures (refused recipients, 4xx API errors) are not retried; retries used up →
``failed``; a redelivered message of a sent email is skipped (never sent twice); metadata carries
the log id for webhooks; subjects are one header line; organisation emails are scoped.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from anymail.exceptions import AnymailAPIError, AnymailRecipientsRefused
from celery.exceptions import Retry
from django.core import mail
from django.db import transaction

from numo9.notifications import mail as outgoing
from numo9.notifications.models import EmailMessage, EmailStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def captured() -> Iterator[list[dict[str, Any]]]:
    """Celery messages the code sends (instead of the broker)."""
    sent: list[dict[str, Any]] = []

    def capture(args: Any = None, kwargs: Any = None, **options: Any) -> None:
        sent.append({"args": args, **options})

    with mock.patch.object(outgoing.send_email, "apply_async", capture):
        yield sent


def api_error(text: str, status: int) -> AnymailAPIError:
    """An error as the provider backend raises it (with the HTTP response)."""
    response = mock.Mock(status_code=status, reason=text, text="{}")
    response.json.return_value = {}
    return AnymailAPIError(text, status_code=status, response=response)


def _queue(org: Organisation | None = None, **kwargs: Any) -> EmailMessage:
    return outgoing.queue_email(
        "dana@refined.ca",
        "Your import\r\nBcc: evil@example.com finished",
        "512 rows imported.",
        html="<p>512 rows imported.</p>",
        organisation=org,
        kind="notifications.job.finished",
        **kwargs,
    )


def _run(message: EmailMessage) -> Any:
    return outgoing.send_email.apply(args=[message.pk])


def _fresh(message: EmailMessage) -> EmailMessage:
    return EmailMessage.platform_messages.get(pk=message.pk)


@pytest.mark.django_db(transaction=True)
def test_logged_then_sent_after_commit_only(captured: list[dict[str, Any]]) -> None:
    with transaction.atomic():
        rolled_back = _queue()
        transaction.set_rollback(True)
    assert captured == []
    assert not EmailMessage.platform_messages.filter(pk=rolled_back.pk).exists()

    with transaction.atomic():
        message = _queue()
        assert captured == []  # not before commit
    assert captured == [{"args": [message.pk], "queue": "high"}]
    assert _fresh(message).status == EmailStatus.QUEUED
    # A subject is one header line: a CR/LF cannot add headers.
    assert message.subject == "Your import Bcc: evil@example.com finished"


def test_sent_by_the_worker(captured: list[dict[str, Any]]) -> None:
    message = _queue(reply_to="books@refined.ca", headers={"X-Numo9-Kind": "test"})
    assert _run(message).get() == "sent"
    row = _fresh(message)
    assert row.status == EmailStatus.SENT and row.attempts == 1 and row.sent_at is not None
    assert row.provider == "locmem" and row.error == ""
    [sent] = mail.outbox
    assert sent.to == ["dana@refined.ca"] and sent.reply_to == ["books@refined.ca"]
    assert sent.alternatives[0][1] == "text/html"  # type: ignore[attr-defined]
    assert sent.extra_headers["X-Numo9-Kind"] == "test"
    assert sent.metadata == {"numo9_message": str(message.public_id)}  # type: ignore[attr-defined]
    assert sent.tags == ["notifications.job.finished"]  # type: ignore[attr-defined]

    # A second delivery of the same Celery message finds it sent: skipped, not sent twice.
    assert _run(message).get() == "skipped"
    assert len(mail.outbox) == 1


def test_failed_send_is_retried_then_sent(captured: list[dict[str, Any]]) -> None:
    message = _queue()
    outage = api_error("Service unavailable", 503)
    with (
        mock.patch.object(outgoing, "backoff_delay", return_value=42.0),
        mock.patch(
            "django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=outage
        ),
        mock.patch.object(outgoing.send_email, "retry", side_effect=Retry("again")) as retry,
    ):
        result = _run(message)
    assert result.state == "RETRY"
    retry.assert_called_once_with(countdown=42.0)
    row = _fresh(message)
    assert row.status == EmailStatus.RETRYING and row.attempts == 1
    assert "Service unavailable" in row.error and row.next_retry_at is not None
    assert mail.outbox == []

    # The retry message arrives: sent, error cleared.
    assert _run(message).get() == "sent"
    row = _fresh(message)
    assert row.status == EmailStatus.SENT and row.attempts == 2 and row.error == ""
    assert row.next_retry_at is None and len(mail.outbox) == 1


def test_smtp_and_network_errors_are_temporary(captured: list[dict[str, Any]]) -> None:
    import smtplib

    message = _queue()
    for error in (smtplib.SMTPServerDisconnected("gone"), ConnectionRefusedError("refused")):
        with (
            mock.patch(
                "django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=error
            ),
            mock.patch.object(outgoing.send_email, "retry", side_effect=Retry("again")),
        ):
            assert _run(message).state == "RETRY"
    assert _fresh(message).status == EmailStatus.RETRYING and _fresh(message).attempts == 2


@pytest.mark.parametrize(
    "error",
    [
        AnymailRecipientsRefused("All recipients refused"),
        api_error("Invalid To address", 422),
    ],
)
def test_permanent_failures_are_not_retried(
    captured: list[dict[str, Any]], error: Exception
) -> None:
    message = _queue()
    with (
        mock.patch(
            "django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=error
        ),
        mock.patch.object(outgoing.send_email, "retry") as retry,
    ):
        assert _run(message).get() == "failed"
    retry.assert_not_called()
    row = _fresh(message)
    assert row.status == EmailStatus.FAILED and row.error and row.next_retry_at is None


def test_retries_used_up_fail_the_message(captured: list[dict[str, Any]]) -> None:
    message = _queue()
    EmailMessage.platform_messages.filter(pk=message.pk).update(
        attempts=5, status=EmailStatus.RETRYING
    )
    with (
        mock.patch(
            "django.core.mail.backends.locmem.EmailBackend.send_messages",
            side_effect=api_error("Timeout", 504),
        ),
        mock.patch.object(outgoing.send_email, "retry") as retry,
    ):
        assert _run(message).get() == "failed"
    retry.assert_not_called()
    assert _fresh(message).attempts == 6


def test_provider_message_id_is_kept(captured: list[dict[str, Any]]) -> None:
    message = _queue()

    def provider_send(self: Any, messages: list[Any]) -> int:
        for item in messages:
            item.anymail_status = mock.Mock(message_id="pm-1234")
        return len(messages)

    with mock.patch("django.core.mail.backends.locmem.EmailBackend.send_messages", provider_send):
        assert _run(message).get() == "sent"
    assert _fresh(message).provider_message_id == "pm-1234"


def test_organisation_emails_are_scoped(org: Organisation, captured: list[dict[str, Any]]) -> None:
    other = Organisation.objects.create(name="Maple Leaf Bakery")
    mine = _queue(org)
    _queue(other)
    _queue(None)  # an account email: no organisation
    with org_context(org):
        assert list(EmailMessage.objects.values_list("pk", flat=True)) == [mine.pk]
    assert EmailMessage.platform_messages.count() == 3


def test_provider_name_from_the_anymail_backend(settings: Any) -> None:
    settings.EMAIL_BACKEND = "anymail.backends.postmark.EmailBackend"
    assert outgoing._provider_name() == "postmark"
