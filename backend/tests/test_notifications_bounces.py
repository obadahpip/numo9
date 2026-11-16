"""A-07-T08 — Bounce / complaint webhook → flag the contact's email status / the user's email.

Acceptance: a bounce is flagged on the contact — the provider's bounce webhook (Postmark's real
payload through django-anymail's tracking view, basic auth) marks the logged message ``bounced``,
the contact person with that address in the message's organisation ``email_status = bounced``,
and the address is not emailed for 30 days. Also: complaints, users' addresses, lookup by
provider message id, another organisation's contact with the same address untouched, unknown
events ignored, webhook without the secret refused, suppression expiry.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from typing import Any

import pytest
from anymail.signals import AnymailTrackingEvent, tracking
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.contacts.models import ContactPerson
from numo9.notifications import mail as outgoing
from numo9.notifications.bounces import suppressed_until
from numo9.notifications.models import EmailMessage, EmailSuppression
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db

ADDRESS = "ap@mapleleaf.ca"


@pytest.fixture(autouse=True)
def _webhook_secret(settings: Any) -> None:
    settings.ANYMAIL = {"WEBHOOK_SECRET": "numo9:hook-secret"}


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def _person(org: Organisation, email: str = ADDRESS) -> ContactPerson:
    with org_context(org):
        customer = contact(org, "Maple Leaf Bakery")
        person = ContactPerson(organisation=org, contact=customer, first_name="Sam", email=email)
        person.save()
        return person


def _sent(org: Organisation | None, to: str = ADDRESS) -> EmailMessage:
    message = outgoing.queue_email(to, "Invoice INV-0042", "Your invoice.", organisation=org)
    EmailMessage.platform_messages.filter(pk=message.pk).update(
        status="sent", provider_message_id="883953f4-6105-42a2-a16a-77a8eac79483"
    )
    return message


def _postmark(payload: dict[str, Any], auth: str = "numo9:hook-secret") -> Any:
    token = base64.b64encode(auth.encode()).decode()
    return Client().post(
        "/webhooks/email/postmark/tracking/",
        payload,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Basic {token}",
    )


def _bounce(message: EmailMessage, **extra: Any) -> dict[str, Any]:
    return {
        "RecordType": "Bounce",
        "ID": 4323372036854775807,
        "Type": "HardBounce",
        "TypeCode": 1,
        "Name": "Hard bounce",
        "Tag": "invoice",
        "MessageID": "883953f4-6105-42a2-a16a-77a8eac79483",
        "Metadata": {"numo9_message": str(message.public_id)},
        "Description": "The server was unable to deliver your message (ex: unknown user).",
        "Details": "smtp;550 5.1.1 The email account that you tried to reach does not exist.",
        "Email": ADDRESS,
        "From": "billing@refined.ca",
        "BouncedAt": "2026-11-16T10:12:41Z",
        "Inactive": True,
        "CanActivate": True,
        "Subject": "Invoice INV-0042",
        **extra,
    }


def test_bounce_flagged_on_the_contact_and_not_retried_for_30_days(
    org: Organisation, mail_worker: list[Any]
) -> None:
    person = _person(org)
    elsewhere = Organisation.objects.create(name="Other Co.")
    same_address_elsewhere = _person(elsewhere)
    message = _sent(org)
    response = _postmark(_bounce(message))
    assert response.status_code == 200

    row = EmailMessage.platform_messages.get(pk=message.pk)
    assert row.status == "bounced" and row.event_at is not None
    assert "unknown user" in row.error
    with org_context(org):
        person.refresh_from_db()
    assert person.email_status == "bounced" and person.email_status_at is not None
    with org_context(elsewhere):
        same_address_elsewhere.refresh_from_db()
    assert same_address_elsewhere.email_status == ""  # another organisation's contact

    # Not retried for 30 days: a new email to the address is logged but not sent.
    assert suppressed_until(ADDRESS) is not None
    again = outgoing.queue_email(ADDRESS, "Reminder", "Due soon.", organisation=org)
    assert again.status == "failed" and again.error.startswith("Suppressed until")
    assert mail_worker == []
    EmailSuppression.objects.update(until=timezone.now() - timedelta(seconds=1))
    assert suppressed_until(ADDRESS) is None
    assert outgoing.queue_email(ADDRESS, "Reminder", "Due soon.").status == "queued"


def test_complaint_flags_the_user(org: Organisation) -> None:
    user = User.objects.create_user(email=ADDRESS, password="x" * 12, name="Sam")
    message = _sent(None)
    response = _postmark(
        {
            "RecordType": "SpamComplaint",
            "ID": 42,
            "Type": "SpamComplaint",
            "TypeCode": 512,
            "MessageID": "883953f4-6105-42a2-a16a-77a8eac79483",
            "Email": ADDRESS,
            "BouncedAt": "2026-11-16T10:12:41Z",
            "Metadata": {},
            "Description": "The subscriber explicitly marked this message as spam.",
            "Details": "Test spam complaint details",
        }
    )
    assert response.status_code == 200
    # Found by the provider's message id (no metadata in this event).
    assert EmailMessage.platform_messages.get(pk=message.pk).status == "complained"
    user.refresh_from_db()
    assert user.email_status == "complained"
    assert EmailSuppression.objects.get(email=ADDRESS).reason == "complained"


def test_other_events_are_ignored(org: Organisation) -> None:
    message = _sent(org)
    event = AnymailTrackingEvent(event_type="delivered", recipient=ADDRESS, message_id="x")
    tracking.send(sender=object, event=event, esp_name="Postmark")
    assert EmailMessage.platform_messages.get(pk=message.pk).status == "sent"
    assert not EmailSuppression.objects.exists()


def test_unknown_message_still_flags_and_suppresses_the_address() -> None:
    event = AnymailTrackingEvent(
        event_type="bounced", recipient="Nobody@Unknown.ca", message_id="never-sent"
    )
    tracking.send(sender=object, event=event, esp_name="Postmark")
    assert EmailSuppression.objects.get().email == "nobody@unknown.ca"


def test_webhook_needs_the_secret(org: Organisation) -> None:
    message = _sent(org)
    assert _postmark(_bounce(message), auth="numo9:wrong").status_code == 400
    assert EmailMessage.platform_messages.get(pk=message.pk).status == "sent"
