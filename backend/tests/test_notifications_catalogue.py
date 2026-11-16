"""A-07-T11 — System message catalogue (verification, invite, trial reminders, dunning, new
device) seeded.

Acceptance: all templates render — every system message in English and French (subject, text,
compiled HTML) against snapshots, with no French fallback, no unrendered template syntax and the
link present. Also: missing context refused (never an email with a blank), variants (trial
ended, dunning day 7), in-app texts and events registered (sign-in and payment alerts
mandatory).
"""

from __future__ import annotations

import pytest

from numo9.notifications.catalogue import SYSTEM_MESSAGES, MissingContext, render_system
from numo9.notifications.events import get_event
from numo9.notifications.templating import EmailBrand
from numo9.notifications.texts import is_registered, render
from numo9.tenancy.models import Organisation
from tests.email_snapshots import assert_snapshot

pytestmark = pytest.mark.django_db

BRAND = EmailBrand(name="Refined Interiors Inc.", colour="#1F4E79", source="organisation")


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def test_catalogue_is_seeded() -> None:
    assert set(SYSTEM_MESSAGES) == {
        "verify_email", "invitation", "trial_reminder", "dunning", "new_device"
    }  # fmt: skip


@pytest.mark.parametrize("language", ["en-ca", "fr-ca"])
@pytest.mark.parametrize("name", sorted(SYSTEM_MESSAGES))
def test_every_template_renders(org: Organisation, name: str, language: str) -> None:
    message = SYSTEM_MESSAGES[name]
    email = render_system(name, message.sample, language=language, organisation=org)
    assert email.fallback is False and email.language == language
    for part in (email.subject, email.text, email.html):
        assert "{{" not in part and "{%" not in part and "<mj-" not in part
    assert message.sample["link"] in email.text and message.sample["link"] in email.html
    assert email.subject and "\n" not in email.subject
    assert_snapshot(f"{name}.{language}.subject.txt", email.subject + "\n")
    assert_snapshot(f"{name}.{language}.txt", email.text)
    assert_snapshot(f"{name}.{language}.html", email.html)


def test_missing_context_is_refused(org: Organisation) -> None:
    with pytest.raises(MissingContext, match="invitation: role, expires"):
        render_system(
            "invitation",
            {"inviter": "Priya", "target": "Refined", "email": "s@n.ca", "link": "https://x"},
        )


def test_variants(org: Organisation) -> None:
    sample = SYSTEM_MESSAGES["trial_reminder"].sample
    ended = render_system("trial_reminder", {**sample, "days_left": 0}, organisation=org)
    assert ended.subject == "Your Numo9 trial ended" and "read-only" in ended.text
    one = render_system("trial_reminder", {**sample, "days_left": 1}, organisation=org)
    assert one.subject == "1 day left in your Numo9 trial"
    dunning = SYSTEM_MESSAGES["dunning"].sample
    day7 = render_system("dunning", {**dunning, "day": 7}, language="fr-ca", organisation=org)
    assert day7.subject == "Refined Interiors Inc. est maintenant en lecture seule"


def test_in_app_side_registered() -> None:
    for key in (
        "notifications.security.new_device",
        "notifications.billing.payment_failed",
        "notifications.billing.read_only",
        "notifications.trial.ending",
    ):
        assert is_registered(key)
    assert get_event("security.new_device").mandatory
    assert get_event("billing.payment_failed").mandatory
    assert not get_event("trial.ending").mandatory
    title, body = render(
        "notifications.security.new_device",
        {"device": "Chrome on Windows", "when": "today", "ip": "203.0.113.24"},
    )
    assert title == "New sign-in on Chrome on Windows" and "203.0.113.24" in body
