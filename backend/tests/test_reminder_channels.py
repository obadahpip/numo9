"""D-07-T02 — reminder channels: email sends (rendered in the customer's language, one email per
person marked for emails); the SMS and WhatsApp stubs record what they would send."""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail

from numo9.notifications.models import EmailMessage
from numo9.sales.reminder_channels import (
    EMAIL_KIND,
    ReminderMessage,
    StubTextChannel,
    reminder_channel,
)
from numo9.tenancy.context import org_context
from tests.reminder_helpers import invoice, reminder_books

pytestmark = pytest.mark.django_db
CONTEXT = {"title": "Invoice INV-0001 is due soon", "body": "100.00 is due on 1 July 2026."}


@pytest.fixture
def books() -> dict[str, Any]:
    return reminder_books()


def message(books: dict[str, Any], language: str = "en-ca", **context: Any) -> ReminderMessage:
    inv = invoice(books)
    return ReminderMessage(
        invoice=inv,
        contact=inv.contact,
        template="notification",
        language=language,
        context={**CONTEXT, **context},
    )


def deliver_all() -> None:
    from numo9.notifications import mail as outgoing

    for row in EmailMessage.platform_messages.filter(status="queued").order_by("pk"):
        outgoing.send_email.apply(args=[row.pk])


def test_email_sends_to_the_people_marked_for_emails(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        result = reminder_channel("email").send(message(books))
    deliver_all()
    assert result.status == "sent" and result.recipients == ("ap@oncustomer.ca",)
    assert len(result.message_ids) == 1
    (sent,) = mail.outbox
    assert sent.to == ["ap@oncustomer.ca"]
    assert sent.subject == "Invoice INV-0001 is due soon"
    with org_context(books["org"]):
        logged = EmailMessage.objects.get(public_id=result.message_ids[0])
        assert logged.kind == EMAIL_KIND and logged.metadata["invoice"]


def test_email_in_french(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        result = reminder_channel("email").send(message(books, "fr-ca"))
    deliver_all()
    assert result.status == "sent"
    assert mail.outbox[0].subject == "Invoice INV-0001 is due soon"
    with org_context(books["org"]):
        assert EmailMessage.objects.get(public_id=result.message_ids[0]).language == "fr-ca"


def test_email_without_an_address_is_skipped(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        msg = message(books)
        msg.contact.people.update(include_in_emails=False)
        result = reminder_channel("email").send(msg)
    assert (result.status, result.reason) == ("skipped", "no_email")
    assert mail.outbox == []


def test_bounced_address_is_not_used(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        msg = message(books)
        msg.contact.people.filter(first_name="Ana").update(email_status="bounced")
        result = reminder_channel("email").send(msg)
    assert (result.status, result.reason) == ("skipped", "no_email")


@pytest.mark.parametrize("name", ["sms", "whatsapp"])
def test_text_stubs_record_would_send(books: dict[str, Any], name: str) -> None:
    channel = reminder_channel(name)
    assert isinstance(channel, StubTextChannel)
    with org_context(books["org"]):
        result = channel.send(message(books, link="https://app.numo9.ca/i/abc"))
    assert result.status == "would_send" and result.reason == "no_provider"
    assert result.recipients == ("+14165550199",)
    assert result.text.endswith("https://app.numo9.ca/i/abc")
    assert mail.outbox == []
    assert result.as_dict()["text"] == result.text


def test_text_stub_without_a_number_is_skipped(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        msg = message(books)
        msg.contact.people.update(phone="")
        result = reminder_channel("sms").send(msg)
    assert (result.status, result.reason) == ("skipped", "no_phone")


def test_unknown_channel() -> None:
    with pytest.raises(LookupError):
        reminder_channel("fax")
