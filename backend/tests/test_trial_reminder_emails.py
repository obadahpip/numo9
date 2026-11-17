"""U-05-T12 — Email templates EN (FR keys) for the 4 trial reminders.

Acceptance: the templates render with the organisation's name and the date — 7, 3 and 1 days
before the end and when it ended, in English and French, each equal to its snapshot
(``tests/snapshots/email/trial_reminder.day<N>.<lang>.*``); plain words about what happens to the
data (nothing is deleted; still visible and exportable); no template syntax left.
"""

from __future__ import annotations

import pytest

from numo9.notifications.catalogue import render_system
from numo9.tenancy.models import Organisation
from tests.email_snapshots import assert_snapshot

pytestmark = pytest.mark.django_db
LINK = "https://app.numo9.ca/o/x/settings/subscription"


@pytest.mark.parametrize("language", ["en-ca", "fr-ca"])
@pytest.mark.parametrize("days", [7, 3, 1, 0])
def test_reminder_renders_with_name_and_date(days: int, language: str) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    email = render_system(
        "trial_reminder",
        {"days_left": days, "ends_on": "2026-11-13", "link": LINK},
        language=language,
        organisation=org,
    )
    assert email.language == language and email.fallback is False
    for part in (email.text, email.html):
        assert "{{" not in part and "{%" not in part
        assert "Refined Interiors Inc." in part
        assert LINK in part
    if days:
        assert "2026-11-13" in email.text and "2026-11-13" in email.subject + email.text
    nothing_deleted = "nothing" if language == "en-ca" else "rien n"
    assert nothing_deleted in email.text
    assert_snapshot(f"trial_reminder.day{days}.{language}.subject.txt", email.subject + "\n")
    assert_snapshot(f"trial_reminder.day{days}.{language}.txt", email.text)
    assert_snapshot(f"trial_reminder.day{days}.{language}.html", email.html)
