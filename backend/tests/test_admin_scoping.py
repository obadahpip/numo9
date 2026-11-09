"""A-01-T15 — Django admin restricted to platform staff; organisation-owned models in the admin
use explicit, logged unscoped() access; deletes are soft; changes are logged."""

from __future__ import annotations

import logging

import pytest
from django.contrib.admin.models import LogEntry
from django.test import Client

from numo9.accounts.models import User
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeMember,
    PracticeRole,
)
from tests.testapp.models import Widget

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-staple"  # noqa: S105 (test fixture)
ADMIN_PAGES = [
    "/admin/",
    "/admin/accounts/user/",
    "/admin/tenancy/organisation/",
    "/admin/tenancy/practice/",
    "/admin/testapp/widget/",
]


def login(user: User) -> Client:
    client = Client()
    assert client.login(username=user.email, password=PASSWORD)
    return client


@pytest.fixture
def staff() -> User:
    return User.objects.create_superuser("ops@example.com", PASSWORD, name="Ops")


@pytest.fixture
def widgets() -> tuple[Organisation, Organisation]:
    a = Organisation.objects.create(name="Maple Bakery")
    b = Organisation.objects.create(name="Birch Garage")
    with org_context(a):
        Widget.objects.create(label="a1")
    with org_context(b):
        Widget.objects.create(label="b1")
    return a, b


def is_login_redirect(response: object) -> bool:
    return getattr(response, "status_code", 0) == 302 and "/admin/login/" in getattr(
        response, "url", ""
    )


@pytest.mark.parametrize("url", ADMIN_PAGES)
def test_anonymous_is_sent_to_login(url: str) -> None:
    assert is_login_redirect(Client().get(url))


@pytest.mark.parametrize("url", ADMIN_PAGES)
def test_non_staff_users_cannot_open_the_admin(url: str) -> None:
    org = Organisation.objects.create(name="Org")
    practice = Practice.objects.create(name="Firm")
    owner = User.objects.create_user("owner@example.com", PASSWORD, name="Owner")
    OrganisationMember.objects.create(organisation=org, user=owner, role=OrganisationRole.OWNER)
    accountant = User.objects.create_user("acc@example.com", PASSWORD, name="Acc")
    PracticeMember.objects.create(
        practice=practice, user=accountant, role=PracticeRole.PRACTICE_ADMIN
    )
    for user in (owner, accountant):
        assert is_login_redirect(login(user).get(url)), user.email


def test_non_staff_login_form_is_refused() -> None:
    User.objects.create_user("owner@example.com", PASSWORD, name="Owner")
    client = Client()
    response = client.post("/admin/login/", {"username": "owner@example.com", "password": PASSWORD})
    assert response.status_code == 200  # the form is shown again with an error
    assert "_auth_user_id" not in client.session
    assert is_login_redirect(client.get("/admin/"))


def test_inactive_staff_cannot_open_the_admin(staff: User) -> None:
    client = login(staff)
    staff.is_active = False
    staff.save()
    assert is_login_redirect(client.get("/admin/"))


@pytest.mark.parametrize("url", ADMIN_PAGES)
def test_platform_staff_can_open_the_admin(staff: User, url: str) -> None:
    assert login(staff).get(url).status_code == 200


def test_staff_without_model_permission_gets_403() -> None:
    support = User.objects.create_user("support@example.com", PASSWORD, name="S", is_staff=True)
    client = login(support)
    assert client.get("/admin/").status_code == 200
    assert client.get("/admin/testapp/widget/").status_code == 403


def test_org_owned_list_uses_logged_unscoped_access(
    staff: User,
    widgets: tuple[Organisation, Organisation],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="numo9.tenancy.unscoped"):
        response = login(staff).get("/admin/testapp/widget/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "Maple Bakery" in content and "Birch Garage" in content  # all organisations
    reasons = [getattr(r, "reason", "") for r in caplog.records]
    assert any(
        "Django admin testapp.Widget by platform staff ops@example.com" in r for r in reasons
    )


def test_admin_add_sets_created_by_and_is_logged(
    staff: User,
    widgets: tuple[Organisation, Organisation],
    caplog: pytest.LogCaptureFixture,
) -> None:
    a, _ = widgets
    with caplog.at_level(logging.WARNING, logger="numo9.tenancy.admin"):
        response = login(staff).post(
            "/admin/testapp/widget/add/", {"organisation": a.pk, "label": "from admin"}
        )
    assert response.status_code == 302
    widget = Widget.objects.unscoped(reason="test").get(label="from admin")
    assert widget.created_by == staff and widget.organisation == a
    assert any("Admin added testapp.Widget" in r.getMessage() for r in caplog.records)
    assert LogEntry.objects.filter(user=staff, object_id=str(widget.pk)).exists()


def test_admin_delete_is_a_soft_delete(
    staff: User, widgets: tuple[Organisation, Organisation]
) -> None:
    widget = Widget.objects.unscoped(reason="test").get(label="a1")
    client = login(staff)
    response = client.post(f"/admin/testapp/widget/{widget.pk}/delete/", {"post": "yes"})
    assert response.status_code == 302
    widget.refresh_from_db()  # row still exists
    assert widget.is_deleted


def test_bulk_hard_delete_is_not_offered_and_bulk_soft_delete_works(
    staff: User, widgets: tuple[Organisation, Organisation]
) -> None:
    client = login(staff)
    page = client.get("/admin/testapp/widget/").content.decode()
    assert 'value="delete_selected"' not in page
    assert 'value="soft_delete_selected"' in page
    ids = list(Widget.objects.unscoped(reason="test").values_list("pk", flat=True))
    response = client.post(
        "/admin/testapp/widget/",
        {"action": "soft_delete_selected", "_selected_action": [str(i) for i in ids]},
    )
    assert response.status_code == 302
    assert all(w.is_deleted for w in Widget.objects.unscoped(reason="test"))
    assert Widget.objects.unscoped(reason="test").count() == 2
