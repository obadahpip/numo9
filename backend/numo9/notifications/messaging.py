"""SMS and WhatsApp channels — the interface, with no provider yet (A-07-T12).

Text messages are a later option (reminders by SMS, WhatsApp to clients). The channels exist
now so events can name them and the delivery path is tested; **no provider is connected**, so
nothing leaves the platform until one is chosen and its adapter registered.

- ``TextProvider`` — what an adapter implements: ``send(to, text) -> provider message id``,
  ``to`` in E.164 (``+15145550123``). ``NullTextProvider`` is the default: it sends nothing and
  answers ``None``.
- ``TextChannel`` (``sms``, ``whatsapp``) — a ``notify()`` channel: the message is the title, the
  body and the link, cut to ``MAX_LENGTH`` (one SMS = 160 GSM characters is too short for a link;
  320 = two segments). Only events that list the channel use it; a recipient without a valid
  telephone number is skipped. Returns ``TextResult(status, provider_id, reason)``.
- ``NUMO9_SMS_PROVIDER`` / ``NUMO9_WHATSAPP_PROVIDER`` select the adapter (default ``null``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import phonenumbers
from django.conf import settings

from .channels import Delivery, absolute_link, register_channel
from .texts import render

logger = logging.getLogger("numo9.notifications.messaging")

MAX_LENGTH = 320


class TextProvider(Protocol):
    name: str

    def send(self, to: str, text: str) -> str | None: ...


class NullTextProvider:
    """No provider: nothing is sent (see the module docstring)."""

    name = "null"

    def send(self, to: str, text: str) -> str | None:
        return None


@dataclass(frozen=True)
class TextResult:
    status: str  # sent | not_sent | skipped
    provider_id: str = ""
    reason: str = ""


_providers: dict[str, TextProvider] = {"null": NullTextProvider()}


def register_text_provider(provider: TextProvider) -> TextProvider:
    _providers[provider.name] = provider
    return provider


def e164(number: str, region: str = "CA") -> str | None:
    try:
        parsed = phonenumbers.parse(number or "", region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def compose(title: str, body: str, link: str) -> str:
    """Title, body and link in at most MAX_LENGTH characters; the link is never cut."""
    tail = f" {link}" if link else ""
    room = MAX_LENGTH - len(tail)
    text = f"{title}. {body}".strip() if body else title
    if len(text) > room:
        text = text[: max(0, room - 1)].rstrip() + "…"
    return f"{text}{tail}"


class TextChannel:
    def __init__(self, name: str, setting: str) -> None:
        self.name = name
        self.setting = setting

    def provider(self) -> TextProvider:
        return _providers.get(str(getattr(settings, self.setting, "null")), _providers["null"])

    def deliver(self, delivery: Delivery) -> TextResult:
        number = e164(str(getattr(delivery.recipient, "phone", "") or ""))
        if number is None:
            return TextResult("skipped", reason="no_phone")
        title, body = render(delivery.event.title_key, delivery.params, delivery.language)
        link = absolute_link(delivery.link) if delivery.link else ""
        provider = self.provider()
        provider_id = provider.send(number, compose(title, body, link))
        if provider_id is None:
            logger.info("text.not_sent", extra={"channel": self.name, "provider": provider.name})
            return TextResult("not_sent", reason="no_provider")
        return TextResult("sent", provider_id=provider_id)


SMS = register_channel(TextChannel("sms", "NUMO9_SMS_PROVIDER"))
WHATSAPP = register_channel(TextChannel("whatsapp", "NUMO9_WHATSAPP_PROVIDER"))
