"""A-07-T01 — Notification model (recipient, org, category, title key, body params, link, read_at)
+ API list / mark-read.

Acceptance: the unread count is correct — it counts only the person's own unread notifications in
the active organisation (not other people's, not other organisations', not soft-deleted ones) and
follows mark-read, read-all and read-all by category. Also: the model's rules (category, message
key, in-app link only, database checks), messages rendered in the reader's language at read time
with missing parameters tolerated, newest first with cursor pages, filters, someone else's
notification is a 404, read-time kept on a second read, members without the permission can't
reach other organisations.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.notifications import services
from numo9.notifications.models import Notification, NotificationCategory
from numo9.notifications.texts import register_text, render
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db


def _user(email: str, locale: str = "en-ca") -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=email, locale=locale)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def dana(org: Organisation) -> User:
    user = _user("dana@refined.ca")
    OrganisationMember.objects.create(organisation=org, user=user, role="employee")
    return user


@pytest.fixture
def client(dana: User) -> Client:
    browser = Client()
    browser.force_login(dana)
    return browser


def notify(
    org: Organisation,
    user: User,
    key: str = "notifications.job.finished",
    *,
    category: str = NotificationCategory.JOBS,
    read: bool = False,
    minutes_ago: int = 0,
    **params: Any,
) -> Notification:
    with org_context(org):
        item = Notification(
            organisation=org,
            recipient=user,
            category=category,
            title_key=key,
            body_params=params or {"job": "Import contacts", "summary": "512 rows imported."},
            link="/o/x/contacts",
            read_at=timezone.now() if read else None,
        )
        item.save()
        if minutes_ago:
            Notification.objects.filter(pk=item.pk).update(
                created_at=timezone.now() - dt.timedelta(minutes=minutes_ago)
            )
            item.refresh_from_db()
        return item


def url(org: Organisation, tail: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/notifications{tail}"


def count(client: Client, org: Organisation) -> int:
    response = client.get(url(org, "/unread-count"))
    assert response.status_code == 200, response.content
    return int(response.json()["unread_count"])


# ---- unread count (acceptance) -------------------------------------------------------------------


def test_unread_count_is_correct(org: Organisation, dana: User, client: Client) -> None:
    other_person = _user("sam@refined.ca")
    OrganisationMember.objects.create(organisation=org, user=other_person, role="employee")
    other_org = Organisation.objects.create(name="Birch Garage")
    OrganisationMember.objects.create(organisation=other_org, user=dana, role="employee")

    mine = [notify(org, dana, minutes_ago=n) for n in (1, 2, 3)]
    notify(org, dana, read=True)  # already read
    notify(org, other_person)  # someone else's
    notify(other_org, dana)  # another organisation's
    removed = notify(org, dana)
    with org_context(org):
        removed.soft_delete()

    assert count(client, org) == 3
    assert client.get(url(org)).json()["unread_count"] == 3
    assert count(client, other_org) == 1

    response = client.post(url(org, f"/{mine[0].public_id}/read"))
    assert response.status_code == 200
    assert response.json()["read"] is True
    assert count(client, org) == 2

    response = client.post(url(org, "/read-all"), {}, content_type="application/json")
    assert response.json() == {"marked": 2, "unread_count": 0}
    assert count(client, org) == 0
    assert count(client, other_org) == 1  # the other organisation is untouched
    with org_context(org):
        assert services.unread_count(other_person) == 1  # and so is the other person


def test_read_all_by_category(org: Organisation, dana: User, client: Client) -> None:
    notify(org, dana, category=NotificationCategory.JOBS)
    notify(org, dana, category=NotificationCategory.JOBS)
    notify(org, dana, "notifications.document.quarantined", category="documents", file="a.pdf")
    response = client.post(
        url(org, "/read-all"), {"category": "jobs"}, content_type="application/json"
    )
    assert response.json() == {"marked": 2, "unread_count": 1}
    bad = client.post(url(org, "/read-all"), {"category": "x"}, content_type="application/json")
    assert bad.status_code == 400


def test_reading_twice_keeps_the_first_time(org: Organisation, dana: User, client: Client) -> None:
    item = notify(org, dana)
    first = client.post(url(org, f"/{item.public_id}/read")).json()["read_at"]
    second = client.post(url(org, f"/{item.public_id}/read")).json()["read_at"]
    assert first == second
    item.refresh_from_db()
    assert item.read_at is not None


# ---- list ---------------------------------------------------------------------------------------


def test_list_newest_first_rendered_in_the_readers_language(
    org: Organisation, dana: User, client: Client
) -> None:
    notify(org, dana, minutes_ago=10, job="Import contacts", summary="512 rows imported.")
    notify(
        org,
        dana,
        "notifications.document.quarantined",
        category=NotificationCategory.DOCUMENTS,
        file="invoice.pdf",
    )
    body = client.get(url(org)).json()
    first, second = body["results"]
    assert first["title"] == "invoice.pdf was blocked"
    assert first["category"] == "documents" and first["category_label"] == "Documents"
    assert second["title"] == "Import contacts finished"
    assert second["body"] == "512 rows imported."
    assert second["params"] == {"job": "Import contacts", "summary": "512 rows imported."}
    assert set(first) == {
        "id",
        "category",
        "category_label",
        "title",
        "body",
        "title_key",
        "params",
        "link",
        "read",
        "read_at",
        "created_at",
    }
    assert body["next"] is None and body["unread_count"] == 2


def test_cursor_pages_and_filters(org: Organisation, dana: User, client: Client) -> None:
    items = [notify(org, dana, minutes_ago=n) for n in range(1, 8)]  # newest first: items[0]
    notify(org, dana, read=True, minutes_ago=30)
    page = client.get(url(org), {"limit": 3}).json()
    assert [r["id"] for r in page["results"]] == [str(i.public_id) for i in items[:3]]
    page2 = client.get(url(org), {"limit": 3, "before": page["next"]}).json()
    assert [r["id"] for r in page2["results"]] == [str(i.public_id) for i in items[3:6]]
    page3 = client.get(url(org), {"limit": 3, "before": page2["next"]}).json()
    assert len(page3["results"]) == 2 and page3["next"] is None
    unread = client.get(url(org), {"unread": "1", "limit": "100"}).json()["results"]
    assert len(unread) == 7
    assert client.get(url(org), {"category": "documents"}).json()["results"] == []
    assert client.get(url(org), {"limit": "abc"}).status_code == 200


def test_someone_elses_notification_is_a_404(org: Organisation, dana: User, client: Client) -> None:
    other = _user("sam@refined.ca")
    OrganisationMember.objects.create(organisation=org, user=other, role="employee")
    theirs = notify(org, other)
    assert client.post(url(org, f"/{theirs.public_id}/read")).status_code == 404
    assert client.get(url(org), {"before": str(theirs.public_id)}).status_code == 404
    theirs.refresh_from_db()
    assert theirs.read_at is None


def test_outsiders_get_404(org: Organisation, dana: User) -> None:
    outsider = _user("mallory@example.ca")
    browser = Client()
    browser.force_login(outsider)
    item = notify(org, dana)
    assert browser.get(url(org)).status_code == 404
    assert browser.get(url(org, "/unread-count")).status_code == 404
    assert browser.post(url(org, f"/{item.public_id}/read")).status_code == 404
    assert Client().get(url(org)).status_code in {401, 403}


# ---- model and messages -------------------------------------------------------------------------


def test_model_rules(org: Organisation, dana: User) -> None:
    with pytest.raises(ValidationError) as error:
        notify(org, dana, "Not a key")
    assert error.value.error_dict["title_key"][0].code == "notifications.title_key_invalid"
    for link in ("https://evil.example/x", "//evil.example", "/\\evil"):
        with org_context(org), pytest.raises(ValidationError):
            Notification(
                organisation=org, recipient=dana, category="jobs", title_key="a.b", link=link
            ).save()
    with org_context(org):
        # The database repeats the rules that matter.
        for values in ({"category": "spam"}, {"title_key": ""}, {"link": "http://x"}):
            row = Notification(organisation=org, recipient=dana, category="jobs", title_key="a.b")
            for name, value in values.items():
                setattr(row, name, value)
            with pytest.raises(IntegrityError), transaction.atomic():
                super(Notification, row).save()


def test_messages_render_in_the_language_asked() -> None:
    register_text("notifications.test.hello", "Hello %(name)s", "You have %(count)s items.")
    assert render("notifications.test.hello", {"name": "Dana", "count": 3}) == (
        "Hello Dana",
        "You have 3 items.",
    )
    # Missing parameters render empty; unknown keys render generically.
    assert render("notifications.test.hello", {}) == ("Hello ", "You have  items.")
    assert render("notifications.gone.message", {"x": 1}) == ("Notification", "")


def test_french_reader(org: Organisation) -> None:
    from numo9.notifications.serializers import NotificationSerializer

    reader = _user("lucie@refined.ca", locale="fr-ca")
    item = notify(org, reader)

    class _Request:
        user = reader

    data = NotificationSerializer(item, context={"request": _Request()}).data
    with org_context(org):
        title_fr, _body = render(item.title_key, item.body_params, "fr-ca")
    assert data["title"] == title_fr
