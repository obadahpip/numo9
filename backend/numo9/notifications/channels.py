"""Delivery channels of the notification service (A-07-T02).

A channel turns one notification for one person into a delivery. ``notify()`` asks each channel
the person's preferences allow. Channels register under their name:

- ``in_app`` — a ``Notification`` row (the bell, A-07-T01);
- ``email`` — an email in the person's language: subject = the message title, text = the body
  and a link to the page. Logged and sent by the worker after the surrounding transaction
  commits (``mail.queue_email``, A-07-T03), so a rolled-back event never emails anyone.

SMS and WhatsApp follow the same interface (A-07-T12).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from django.conf import settings

from numo9.tenancy.models import Organisation

from .events import EMAIL, IN_APP, NotificationEvent
from .models import Notification
from .texts import render


@dataclass
class Delivery:
    """What ``notify()`` hands a channel: one event for one person."""

    event: NotificationEvent
    recipient: Any
    organisation: Organisation
    params: dict[str, Any] = field(default_factory=dict)
    link: str = ""

    @property
    def language(self) -> str:
        return str(getattr(self.recipient, "locale", "") or self.organisation.locale or "en-ca")


class Channel(Protocol):
    name: str

    def deliver(self, delivery: Delivery) -> Any: ...


_channels: dict[str, Channel] = {}


def register_channel(channel: Channel) -> Channel:
    _channels[channel.name] = channel
    return channel


def get_channel(name: str) -> Channel | None:
    return _channels.get(name)


def channel_names() -> list[str]:
    return list(_channels)


def absolute_link(link: str) -> str:
    return f"{settings.FRONTEND_URL}{link}" if link.startswith("/") else link


class InAppChannel:
    name = IN_APP

    def deliver(self, delivery: Delivery) -> Notification:
        notification = Notification(
            organisation=delivery.organisation,
            recipient=delivery.recipient,
            category=delivery.event.category,
            title_key=delivery.event.title_key,
            body_params=delivery.params,
            link=delivery.link,
        )
        notification.save()
        return notification


#: The function that sends an email channel message (tests may swap it).
EmailSender = Callable[[Delivery, str, str], Any]


def _queue(delivery: Delivery, subject: str, text: str) -> Any:
    """Log the email and send it through the worker after commit (A-07-T03)."""
    from .mail import queue_email

    return queue_email(
        delivery.recipient.email,
        subject,
        text,
        organisation=delivery.organisation,
        recipient=delivery.recipient,
        kind=delivery.event.title_key,
        language=delivery.language,
    )


class EmailChannel:
    name = EMAIL
    sender: EmailSender = staticmethod(_queue)

    def deliver(self, delivery: Delivery) -> Any:
        if not getattr(delivery.recipient, "email", ""):
            return None
        title, body = render(delivery.event.title_key, delivery.params, delivery.language)
        text = body
        if delivery.link:
            text = (
                f"{body}\n\n{absolute_link(delivery.link)}"
                if body
                else absolute_link(delivery.link)
            )
        return type(self).sender(delivery, title, text)


register_channel(InAppChannel())
register_channel(EmailChannel())
