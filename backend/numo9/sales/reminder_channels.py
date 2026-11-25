"""Invoice reminders — the channels (D-07-T02): how one reminder reaches a customer.

``ReminderChannel`` is what a channel implements: ``name`` and ``send(message) ->
ReminderResult``. ``ReminderMessage`` carries the invoice, the customer, the step's template,
the language and the values the template reads (invoice number, amount still owing, due date,
days before or after it, the link to the invoice).

- ``email`` — ``EmailReminderChannel``: renders the step's template (A-07 templating: subject,
  text and HTML, in the customer's language) and queues one email per person of the customer
  marked "include in emails" (``queue_email``: logged, sent by the worker once the surrounding
  transaction commits, kind ``sales.invoice_reminder``). Bounced addresses are suppressed by the
  mail service and come back as failed messages. No address → ``skipped`` (``no_email``).
- ``sms`` and ``whatsapp`` — ``StubTextChannel``: no provider is connected yet, so a reminder is
  **recorded, never sent**: the text it would send and to which numbers (E.164) come back as
  ``would_send``; no valid number → ``skipped`` (``no_phone``). A real adapter registers under
  the same name (``register_reminder_channel``) once a provider is chosen.

The reminder job (D-07-T04) keeps each ``ReminderResult`` in the invoice's reminder log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from numo9.notifications.messaging import compose, e164

from .models import ReminderChannelKind

logger = logging.getLogger("numo9.sales.reminders")

EMAIL_KIND = "sales.invoice_reminder"


@dataclass(frozen=True)
class ReminderMessage:
    invoice: Any
    contact: Any
    template: str
    language: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReminderResult:
    channel: str
    status: str  # sent | would_send | skipped
    recipients: tuple[str, ...] = ()
    reason: str = ""
    message_ids: tuple[str, ...] = ()
    text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "status": self.status,
            "recipients": list(self.recipients),
            "reason": self.reason,
            "message_ids": list(self.message_ids),
            **({"text": self.text} if self.text else {}),
        }


class ReminderChannel(Protocol):
    @property
    def name(self) -> str: ...

    def send(self, message: ReminderMessage) -> ReminderResult: ...


def email_recipients(contact: Any) -> list[str]:
    """The customer's people marked "include in emails" with a deliverable address."""
    people = contact.people.filter(include_in_emails=True).exclude(email="")
    people = people.exclude(email_status__in=("bounced", "complained"))
    return list(dict.fromkeys(people.order_by("-is_primary", "pk").values_list("email", flat=True)))


def phone_recipients(contact: Any) -> list[str]:
    """The customer's people's telephone numbers that are valid, in E.164."""
    numbers = (e164(p) for p in contact.people.exclude(phone="").values_list("phone", flat=True))
    return list(dict.fromkeys(n for n in numbers if n))


class EmailReminderChannel:
    name = ReminderChannelKind.EMAIL.value

    def send(self, message: ReminderMessage) -> ReminderResult:
        from numo9.notifications.mail import queue_email
        from numo9.notifications.templating import render_email

        recipients = email_recipients(message.contact)
        if not recipients:
            return ReminderResult(self.name, "skipped", reason="no_email")
        organisation = message.invoice.organisation
        email = render_email(
            message.template,
            message.context,
            language=message.language,
            organisation=organisation,
        )
        queued = [
            queue_email(
                address,
                email.subject,
                email.text,
                html=email.html,
                organisation=organisation,
                kind=EMAIL_KIND,
                language=email.language,
                metadata={"invoice": str(message.invoice.public_id)},
            )
            for address in recipients
        ]
        return ReminderResult(
            self.name,
            "sent",
            tuple(recipients),
            message_ids=tuple(str(m.public_id) for m in queued),
        )


class StubTextChannel:
    """A text channel with no provider: records what it would send (module docstring)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def send(self, message: ReminderMessage) -> ReminderResult:
        numbers = phone_recipients(message.contact)
        if not numbers:
            return ReminderResult(self.name, "skipped", reason="no_phone")
        context = message.context
        title = str(context.get("subject") or context.get("title") or "")
        body = str(context.get("text") or "")
        text = compose(title, body, str(context.get("link") or ""))
        logger.info(
            "reminder.would_send",
            extra={"channel": self.name, "invoice": str(message.invoice.public_id)},
        )
        return ReminderResult(
            self.name, "would_send", tuple(numbers), reason="no_provider", text=text
        )


_channels: dict[str, ReminderChannel] = {}


def register_reminder_channel(channel: ReminderChannel) -> ReminderChannel:
    _channels[channel.name] = channel
    return channel


def reminder_channel(name: str) -> ReminderChannel:
    try:
        return _channels[name]
    except KeyError:
        raise LookupError(f"No reminder channel {name!r}.") from None


EMAIL = register_reminder_channel(EmailReminderChannel())
SMS = register_reminder_channel(StubTextChannel(ReminderChannelKind.SMS.value))
WHATSAPP = register_reminder_channel(StubTextChannel(ReminderChannelKind.WHATSAPP.value))
