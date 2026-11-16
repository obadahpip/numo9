"""A-07-T02 — Notification service ``notify(event, recipients, channels)`` with category
preferences.

Acceptance: preferences are respected — a person who turned a category's email off gets the
in-app notification only, one who turned the app off gets the email only, both off = nothing;
the defaults apply when nobody chose; security is locked (always both channels, cannot be
changed, API 409); mandatory events ignore preferences; ``channels=`` narrows; preferences are
per organisation; emails go in the recipient's language after commit (none on rollback);
duplicates skipped; unknown events refused; the preferences API lists and changes categories.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail
from django.db import transaction
from django.test import Client

from numo9.accounts.models import User
from numo9.notifications import services
from numo9.notifications.events import UnknownEvent, register_event
from numo9.notifications.models import Notification, NotificationPreference
from numo9.notifications.texts import register_text
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("mail_worker")]

register_text("notifications.test.alert", "Alert about %(what)s", "Something about %(what)s.")
register_event("test.jobs_alert", "jobs", title_key="notifications.test.alert")
register_event("test.security_alert", "security", title_key="notifications.test.alert")
register_event("test.billing_must", "billing", title_key="notifications.test.alert", mandatory=True)


def _user(email: str, locale: str = "en-ca") -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=email, locale=locale)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def other_org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Bakery")


@pytest.fixture
def dana(org: Organisation) -> User:
    user = _user("dana@refined.ca")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    return user


def _in_app(org: Organisation, user: User) -> int:
    with org_context(org):
        return Notification.objects.filter(recipient=user).count()


def send(org: Organisation, event: str, people: list[User], **kwargs: Any) -> services.Sent:
    with transaction.atomic():
        sent = services.notify(event, people, organisation=org, params={"what": "x"}, **kwargs)
    return sent


@pytest.mark.django_db(transaction=True)
def test_defaults_then_preferences_are_respected(org: Organisation, dana: User) -> None:
    # Default for jobs: in the app only.
    sent = send(org, "test.jobs_alert", [dana])
    assert sent.to(dana) == ["in_app"]
    assert _in_app(org, dana) == 1 and len(mail.outbox) == 0

    # Email on, app off.
    with org_context(org):
        services.set_preference(dana, "jobs", in_app=False, email=True)
    sent = send(org, "test.jobs_alert", [dana], link="/o/x/jobs")
    assert sent.to(dana) == ["email"]
    assert _in_app(org, dana) == 1  # unchanged
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Alert about x"
    assert mail.outbox[0].to == ["dana@refined.ca"]
    assert "Something about x." in mail.outbox[0].body
    assert mail.outbox[0].body.rstrip().endswith("/o/x/jobs")

    # Both off: nothing.
    with org_context(org):
        services.set_preference(dana, "jobs", email=False)
    assert len(send(org, "test.jobs_alert", [dana])) == 0
    assert _in_app(org, dana) == 1 and len(mail.outbox) == 1


@pytest.mark.django_db(transaction=True)
def test_security_is_locked_and_mandatory_events_ignore_preferences(
    org: Organisation, dana: User
) -> None:
    with org_context(org), pytest.raises(services.LockedCategory):
        services.set_preference(dana, "security", email=False)
    # Even a stray row does not switch security off.
    with org_context(org):
        NotificationPreference.objects.create(
            organisation=org, user=dana, category="security", in_app=False, email=False
        )
    assert send(org, "test.security_alert", [dana]).to(dana) == ["in_app", "email"]

    with org_context(org):
        services.set_preference(dana, "billing", in_app=False, email=False)
    assert send(org, "test.billing_must", [dana]).to(dana) == ["in_app", "email"]


@pytest.mark.django_db(transaction=True)
def test_channels_narrow_and_duplicates_are_skipped(org: Organisation, dana: User) -> None:
    sent = send(org, "test.security_alert", [dana, dana, None], channels=["in_app"])  # type: ignore[list-item]
    assert sent.to(dana) == ["in_app"]
    assert len(sent) == 1 and len(mail.outbox) == 0


@pytest.mark.django_db(transaction=True)
def test_preferences_are_per_organisation(
    org: Organisation, other_org: Organisation, dana: User
) -> None:
    OrganisationMember.objects.create(organisation=other_org, user=dana, role="employee")
    with org_context(org):
        services.set_preference(dana, "jobs", in_app=False)
    assert send(org, "test.jobs_alert", [dana]).to(dana) == []
    assert send(other_org, "test.jobs_alert", [dana]).to(dana) == ["in_app"]
    assert _in_app(other_org, dana) == 1


@pytest.mark.django_db(transaction=True)
def test_email_in_recipient_language_and_not_sent_on_rollback(org: Organisation) -> None:
    francine = _user("francine@refined.ca", locale="fr-ca")
    OrganisationMember.objects.create(organisation=org, user=francine, role="owner")
    with transaction.atomic():
        services.notify(
            "jobs.failed",
            [francine],
            ["email"],
            organisation=org,
            params={"job": "Importer", "error": "Le fichier est vide."},
        )
        transaction.set_rollback(True)
    # Jobs email is off by default; turn it on and try again.
    with org_context(org):
        services.set_preference(francine, "jobs", email=True)
    with transaction.atomic():
        services.notify(
            "jobs.failed",
            [francine],
            ["email"],
            organisation=org,
            params={"job": "Importer", "error": "Le fichier est vide."},
        )
        transaction.set_rollback(True)
    assert mail.outbox == []
    with transaction.atomic():
        services.notify(
            "jobs.failed",
            [francine],
            ["email"],
            organisation=org,
            params={"job": "Importer", "error": "Le fichier est vide."},
        )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Importer n’a pas pu se terminer"
    assert mail.outbox[0].body.startswith("Le fichier est vide.")


def test_unknown_event_and_missing_organisation_refused(dana: User) -> None:
    with pytest.raises(UnknownEvent):
        services.notify("nobody.registered", [dana], organisation=Organisation(name="x"))
    with pytest.raises(ValueError):
        services.notify("test.jobs_alert", [dana])


def test_preferences_api(org: Organisation, dana: User) -> None:
    browser = Client()
    browser.force_login(dana)
    base = f"/api/v1/o/{org.public_id}/notifications/preferences"
    listed = browser.get(base).json()["results"]
    by_category = {row["category"]: row for row in listed}
    assert set(by_category) == {
        "system",
        "security",
        "jobs",
        "documents",
        "approvals",
        "reminders",
        "billing",
    }
    assert by_category["security"]["locked"] is True
    assert by_category["jobs"] == {
        "category": "jobs",
        "category_label": "Background jobs",
        "in_app": True,
        "email": False,
        "locked": False,
        "is_default": True,
    }

    changed = browser.patch(
        base, {"category": "jobs", "email": True}, content_type="application/json"
    )
    assert changed.status_code == 200
    assert changed.json()["email"] is True and changed.json()["is_default"] is False
    refused = browser.patch(
        base, {"category": "security", "email": False}, content_type="application/json"
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "notifications.category_locked"
    bad = browser.patch(base, {"category": "nonsense"}, content_type="application/json")
    assert bad.status_code == 400

    # Another organisation's preferences are not reachable.
    stranger = Organisation.objects.create(name="Elsewhere Ltd.")
    other = f"/api/v1/o/{stranger.public_id}/notifications/preferences"
    assert browser.get(other).status_code in (403, 404)
