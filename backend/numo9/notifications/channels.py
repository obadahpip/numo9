"""Delivery channels of the notification service (A-07-T02).

A channel turns one notification for one person into a delivery. ``notify()`` asks each channel
the person's preferences allow. Channels register under their name:

- ``in_app`` — a ``Notification`` row (the bell, A-07-T01);
- ``email`` — an email in the person's language: subject = the message title, text = the body
  and a link to the page. Sent after the surrounding transaction commits, so a rolled-back event
  never emails anyone (A-07-T03 sends it through Celery with retries and a message log).

SMS and WhatsApp follow the same interface (A-07-T12).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

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


#: The function that actually sends an email channel message; A-07-T03 replaces it with the
#: queued sender (``numo9.notifications.mail.queue_email``).
EmailSender = Callable[[Delivery, str, str], Any]


def _send_now(delivery: Delivery, subject: str, text: str) -> None:
    transaction.on_commit(
        lambda: send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, [delivery.recipient.email])
    )


class EmailChannel:
    name = EMAIL
    sender: EmailSender = staticmethod(_send_now)

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
