"""A-07-T12 — SMS / WhatsApp channel interface (no provider).

Acceptance: interface + null provider — ``sms`` and ``whatsapp`` are notify() channels; with no
provider configured (the default) a delivery sends nothing and says so (``not_sent``,
``no_provider``); a provider registered and selected receives the E.164 number and the composed
text. Also: only events that list the channel use it; recipients without a valid telephone
number are skipped; the text keeps the link whole within 320 characters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.notifications import messaging, services
from numo9.notifications.channels import channel_names
from numo9.notifications.events import register_event
from numo9.notifications.texts import register_text
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db

register_text("notifications.test.text", "Invoice INV-%(number)s is due", "Pay %(amount)s today.")
register_event("test.text", "reminders", title_key="notifications.test.text", channels=("sms",))
register_event(
    "test.both", "reminders", title_key="notifications.test.text", channels=("in_app", "whatsapp")
)
register_event(
    "test.app_only", "reminders", title_key="notifications.test.text", channels=("in_app",)
)


_count = 0


def Person(phone: str) -> User:  # noqa: N802 — reads like the recipient it builds
    """A user with a telephone number (people get one with their profile; contacts have one)."""
    global _count
    _count += 1
    user = User.objects.create_user(email=f"p{_count}@refined.ca", password="x" * 12, name="P")
    user.phone = phone  # type: ignore[attr-defined]
    return user


@dataclass
class FakeProvider:
    name: str = "fake-sms"
    sent: list[tuple[str, str]] = field(default_factory=list)

    def send(self, to: str, text: str) -> str | None:
        self.sent.append((to, text))
        return f"msg-{len(self.sent)}"


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


PARAMS: dict[str, Any] = {"number": "0042", "amount": "$1,250.00"}


def test_channels_registered() -> None:
    assert {"in_app", "email", "sms", "whatsapp"} <= set(channel_names())


def test_null_provider_sends_nothing(org: Organisation) -> None:
    sent = services.notify(
        "test.text", [Person("514 555 0123")], organisation=org, params=PARAMS, link="/o/x/i/42"
    )
    [(_, channel, result)] = sent.deliveries
    assert channel == "sms"
    assert result == messaging.TextResult("not_sent", reason="no_provider")


def test_registered_provider_receives_e164_and_text(org: Organisation, settings: Any) -> None:
    provider = FakeProvider()
    messaging.register_text_provider(provider)
    settings.NUMO9_SMS_PROVIDER = "fake-sms"
    sent = services.notify(
        "test.text", [Person("(514) 555-0123")], organisation=org, params=PARAMS, link="/o/x/i/42"
    )
    assert sent.deliveries[0][2] == messaging.TextResult("sent", provider_id="msg-1")
    [(to, text)] = provider.sent
    assert to == "+15145550123"
    assert text == "Invoice INV-0042 is due. Pay $1,250.00 today. http://localhost:3000/o/x/i/42"


def test_only_events_listing_the_channel_and_valid_numbers(org: Organisation) -> None:
    assert (
        services.notify(
            "test.app_only", [Person("514 555 0123")], ["sms"], organisation=org
        ).deliveries
        == []
    )
    [(_, channel, result)] = services.notify(
        "test.both", [Person("not a number")], ["whatsapp"], organisation=org, params=PARAMS
    ).deliveries
    assert (channel, result.status, result.reason) == ("whatsapp", "skipped", "no_phone")


def test_compose_keeps_the_link() -> None:
    link = "https://app.numo9.ca/o/7f3c2a10/invoices/42"
    text = messaging.compose("T" * 200, "B" * 400, link)
    assert len(text) == messaging.MAX_LENGTH and text.endswith(" " + link)
    assert "…" in text
    assert messaging.compose("Short", "", "") == "Short"
    assert messaging.e164("+33 1 23 45 67 89") == "+33123456789"
    assert messaging.e164("555") is None
