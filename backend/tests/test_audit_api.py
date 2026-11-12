"""Audit log API (A-04-T07).

Acceptance: the default range is the last 90 days. Also: every filter (user, system, type,
action verb and name, record, batch, text), newest-first cursor pages without gaps or repeats,
the organisation boundary (another organisation's events and platform events never listed; their
ids answer 404), the record timeline over every date, the filter choices, who may see the log,
the platform log (sign-ins) for platform staff, and A-03-T15's role diff visible in the log.
"""

from __future__ import annotations

import datetime as dt
import zoneinfo
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
from django.test import Client
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.audit.batch import audit_batch
from numo9.audit.models import AuditEvent
from numo9.audit.service import record
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    AssignmentRole,
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)
from tests.auth_helpers import login, make_user
from tests.testapp.models import AuditedInvoice

pytestmark = pytest.mark.django_db

TORONTO = zoneinfo.ZoneInfo("America/Toronto")
NOW = dt.datetime(2026, 11, 12, 15, 0, tzinfo=TORONTO)


@contextmanager
def at(moment: dt.datetime) -> Iterator[None]:
    with mock.patch("numo9.audit.service.timezone.now", return_value=moment):
        yield


@contextmanager
def today_is(moment: dt.datetime) -> Iterator[None]:
    with mock.patch("numo9.audit.query.timezone.now", return_value=moment):
        yield


def person(org: Organisation, role: str, email: str, name: str) -> User:
    user = User.objects.create_user(email=email, password="x" * 12, name=name)
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


def api(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")


@pytest.fixture
def owner(org: Organisation) -> User:
    return person(org, "owner", "avery@refined.ca", "Avery Owner")


def url(org: Organisation, path: str = "events") -> str:
    return f"/api/v1/o/{org.public_id}/audit/{path}"


def listed(client: APIClient, org: Organisation, **params: Any) -> list[str]:
    with today_is(NOW):
        response = client.get(url(org), params)
    assert response.status_code == 200, response.json()
    return [row["action"] for row in response.json()["results"]]


# ---- acceptance: default range = the last 90 days ---------------------------------------------


def test_default_range_is_the_last_90_days(org: Organisation, owner: User) -> None:
    start_of_day_89 = dt.datetime(2026, 8, 15, 0, 0, tzinfo=TORONTO)  # 12 Nov − 89 days
    for moment, action in [
        (NOW, "tests.today"),
        (start_of_day_89, "tests.day89"),
        (start_of_day_89 - dt.timedelta(seconds=1), "tests.day90"),
        (NOW - dt.timedelta(days=200), "tests.old"),
    ]:
        with at(moment):
            record(action, organisation=org)
    with today_is(NOW):
        body = api(owner).get(url(org)).json()
    assert [r["action"] for r in body["results"]] == ["tests.today", "tests.day89"]
    assert body["range"] == {
        "from": "2026-08-15",
        "to": "2026-11-12",
        "default": True,
        "time_zone": "America/Toronto",
    }
    assert listed(api(owner), org, **{"from": "2026-07-01"}) == [
        "tests.today",
        "tests.day89",
        "tests.day90",
    ]


def test_dates_follow_the_organisation_time_zone(owner: User) -> None:
    vancouver = Organisation.objects.create(name="West Ltd.", time_zone="America/Vancouver")
    OrganisationMember.objects.create(organisation=vancouver, user=owner, role="owner")
    late = dt.datetime(2026, 11, 12, 23, 30, tzinfo=zoneinfo.ZoneInfo("America/Vancouver"))
    with at(late):
        record("tests.late", organisation=vancouver)  # 13 Nov in Toronto, 12 Nov in Vancouver
    assert listed(api(owner), vancouver, **{"from": "2026-11-12", "to": "2026-11-12"}) == [
        "tests.late"
    ]


def test_bad_dates_and_order_are_refused(org: Organisation, owner: User) -> None:
    client = api(owner)
    assert client.get(url(org), {"from": "12/11/2026"}).json()["code"] == "audit.bad_date"
    bad = client.get(url(org), {"from": "2026-11-12", "to": "2026-11-01"})
    assert bad.status_code == 400 and bad.json()["code"] == "audit.date_order"


# ---- filters -----------------------------------------------------------------------------------


@pytest.fixture
def sam(org: Organisation) -> User:
    return person(org, "admin", "sam@refined.ca", "Sam Patel")


def test_filters(org: Organisation, owner: User, sam: User) -> None:
    with at(NOW):
        with org_context(org):
            invoice = AuditedInvoice.objects.create(number="INV-7", amount=Decimal("5.00"))
        record("tests.widget.updated", organisation=org, actor=owner, object_type="tests.Widget")
        record("tests.widget.deleted", organisation=org, actor=sam, object_type="tests.Widget")
        with audit_batch("Bulk edit", organisation=org) as batch:
            record("tests.thing.updated", organisation=org, actor=sam, object_type="tests.Thing")
    client = api(owner)
    assert listed(client, org, user=str(sam.public_id)) == [
        "tests.thing.updated",
        "tests.widget.deleted",
    ]
    assert listed(client, org, user="system") == ["audit.batch", "testapp.auditedinvoice.created"]
    assert listed(client, org, type="tests.Widget") == [
        "tests.widget.deleted",
        "tests.widget.updated",
    ]
    assert listed(client, org, action="updated") == ["tests.thing.updated", "tests.widget.updated"]
    assert listed(client, org, action="tests.widget.deleted,created") == [
        "tests.widget.deleted",
        "testapp.auditedinvoice.created",
    ]
    assert listed(
        client, org, object_type="testapp.AuditedInvoice", object_id=str(invoice.public_id)
    ) == ["testapp.auditedinvoice.created"]
    assert listed(client, org, batch=str(batch.id)) == ["audit.batch", "tests.thing.updated"]
    assert listed(client, org, q="INV-7") == ["testapp.auditedinvoice.created"]
    bad = client.get(url(org), {"user": "not-a-uuid"})
    assert bad.status_code == 400 and bad.json()["code"] == "audit.bad_filter"


def test_row_shape_names_the_change_and_its_labels(org: Organisation, owner: User) -> None:
    with at(NOW), org_context(org):
        invoice = AuditedInvoice.objects.create(number="INV-1", amount=Decimal("100.00"))
        invoice.amount = Decimal("120.50")
        invoice.notes = "x" * 500
        invoice.save()
    with today_is(NOW):
        row = api(owner).get(url(org), {"action": "updated"}).json()["results"][0]
    assert row["action_label"] == "Edited" and row["verb"] == "updated"
    assert row["record"] == {
        "type": "testapp.AuditedInvoice",
        "type_label": "Audited invoice",
        "id": str(invoice.public_id),
        "label": "Invoice INV-1",
    }
    amount = next(c for c in row["changes"] if c["field"] == "amount")
    assert amount == {
        "field": "amount",
        "label": "Amount",
        "old": "100.00",
        "new": "120.50",
        "masked": False,
    }
    notes = next(c for c in row["changes"] if c["field"] == "notes")
    assert notes["new"]["truncated"] is True and notes["new"]["length"] == 500
    detail = api(owner).get(url(org, f"events/{row['id']}")).json()
    assert next(c for c in detail["changes"] if c["field"] == "notes")["new"] == "x" * 500
    assert len(detail["hash"]) == 64


def test_viewer_preferences_come_with_the_list(org: Organisation, owner: User) -> None:
    owner.time_format = "24h"
    owner.save(update_fields=["time_format"])
    viewer = api(owner).get(url(org)).json()["viewer"]
    assert viewer == {"locale": "en-ca", "time_format": "24h", "time_zone": "America/Toronto"}


# ---- cursor pages ------------------------------------------------------------------------------


def test_cursor_pages_cover_every_event_once_newest_first(org: Organisation, owner: User) -> None:
    for n in range(120):
        with at(NOW - dt.timedelta(minutes=n // 2)):  # pairs share a time: id breaks the tie
            record(f"tests.e{n:03}", organisation=org)
    client, seen, cursor, pages = api(owner), [], None, 0
    while True:
        params: dict[str, Any] = {"limit": 50}
        if cursor:
            params["cursor"] = cursor
        with today_is(NOW):
            body = client.get(url(org), params).json()
        seen += [r["action"] for r in body["results"]]
        cursor, pages = body["next"], pages + 1
        if not cursor:
            break
    assert pages == 3 and len(seen) == 120 and len(set(seen)) == 120
    stored = AuditEvent.platform_events.filter(organisation=org).order_by("-created_at", "-id")
    assert seen == [e.action for e in stored]


def test_bad_cursor_and_limit_are_refused(org: Organisation, owner: User) -> None:
    client = api(owner)
    assert client.get(url(org), {"cursor": "nonsense"}).json()["code"] == "audit.bad_cursor"
    assert client.get(url(org), {"limit": 500}).json()["code"] == "audit.bad_limit"
    assert client.get(url(org), {"limit": 0}).status_code == 400


# ---- the organisation boundary -----------------------------------------------------------------


def test_other_organisations_and_platform_events_stay_out(org: Organisation, owner: User) -> None:
    other = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    with at(NOW):
        mine = record("tests.mine", organisation=org)
        theirs = record("tests.theirs", organisation=other)
        record("auth.login.succeeded", organisation=None)
    client = api(owner)
    assert listed(client, org) == ["tests.mine"]
    assert client.get(url(org, f"events/{theirs.public_id}")).status_code == 404
    assert client.get(url(org, f"events/{mine.public_id}")).status_code == 200
    assert client.get(url(other)).status_code == 404  # not a member: as if it did not exist


def test_who_may_see_the_log(org: Organisation, owner: User) -> None:
    sales = person(org, "sales", "lee@refined.ca", "Lee Chan")
    refused = api(sales).get(url(org))
    assert refused.status_code == 403 and refused.json()["code"] == "permission.denied"
    practice = Practice.objects.create(name="Maple Leaf Accounting")
    accountant = User.objects.create_user("dana@maple.ca", password="x" * 12, name="Dana Lee")
    staff = PracticeMember.objects.create(practice=practice, user=accountant, role="accountant")
    assignment = PracticeAssignment.objects.create(
        practice=practice, organisation=org, role=AssignmentRole.FULL_SERVICE
    )
    assignment.assigned_staff.add(staff)
    assert api(accountant).get(url(org)).status_code == 200
    assert api(person(org, "admin", "kim@refined.ca", "Kim")).get(url(org)).status_code == 200


# ---- record timeline ---------------------------------------------------------------------------


def test_record_history_covers_every_date(org: Organisation, owner: User) -> None:
    with at(NOW - dt.timedelta(days=400)), org_context(org):
        invoice = AuditedInvoice.objects.create(number="INV-2", amount=Decimal("1.00"))
    with at(NOW), org_context(org):
        invoice.amount = Decimal("2.00")
        invoice.save()
    path = url(org, f"records/testapp.AuditedInvoice/{invoice.public_id}")
    body = api(owner).get(path).json()
    assert [r["action"] for r in body["results"]] == [
        "testapp.auditedinvoice.updated",
        "testapp.auditedinvoice.created",
    ]
    assert body["record"]["label"] == "Invoice INV-2"
    assert body["record"]["type_label"] == "Audited invoice"
    unknown = url(org, "records/testapp.AuditedInvoice/00000000-0000-0000-0000-000000000000")
    assert api(owner).get(unknown).status_code == 404


# ---- filter choices ----------------------------------------------------------------------------


def test_filter_choices(org: Organisation, owner: User, sam: User) -> None:
    with at(NOW):
        record("tests.a.updated", organisation=org, actor=sam, object_type="tests.Widget")
        with org_context(org):
            AuditedInvoice.objects.create(number="INV-3", amount=Decimal("3.00"))
    body = api(owner).get(url(org, "filters")).json()
    assert body["users"] == [
        {"value": "system", "label": "System"},
        {"value": str(sam.public_id), "label": "Sam Patel (sam@refined.ca)"},
    ]
    assert body["types"] == [
        {"value": "testapp.AuditedInvoice", "label": "Audited invoice"},
        {"value": "tests.Widget", "label": "Widget"},
    ]
    assert [a["value"] for a in body["actions"]] == ["created", "updated", "deleted", "restored"]


# ---- platform log ------------------------------------------------------------------------------


def _platform_staff(key: str) -> Client:
    user = User.objects.create_user(f"{key}@numo9.ca", password="x" * 12, name=key)
    role = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key=key)
    RoleAssignment.objects.create(role=role, user=user)
    client = Client()
    client.force_login(user)
    return client


def test_platform_staff_see_sign_ins(org: Organisation, owner: User) -> None:
    make_user(email="dana@maple.ca")
    login(Client(), "dana@maple.ca")
    login(Client(), "dana@maple.ca", password="wrong password 12")  # noqa: S106
    for key in ("platform_owner", "platform_support"):
        body = _platform_staff(key).get("/api/v1/platform/audit/events").json()
        actions = [r["action"] for r in body["results"]]
        assert "auth.login.succeeded" in actions and "auth.login.failed" in actions
    refused = api(owner).get("/api/v1/platform/audit/events")
    assert refused.status_code == 403


def test_platform_log_filters_one_organisation(org: Organisation) -> None:
    other = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    record("tests.here", organisation=org)
    record("tests.there", organisation=other)
    body = (
        _platform_staff("platform_owner")
        .get("/api/v1/platform/audit/events", {"organisation": str(org.public_id)})
        .json()
    )
    assert [r["action"] for r in body["results"]] == ["tests.here"]


# ---- A-03-T15: role changes visible with their diff -------------------------------------------


def test_role_change_diff_is_visible_in_the_log(org: Organisation, owner: User) -> None:
    client = api(owner)
    created = client.post(f"/api/v1/o/{org.public_id}/roles", {"name": "Buyer"}, format="json")
    role_id = created.json()["id"]
    renamed = client.patch(
        f"/api/v1/o/{org.public_id}/roles/{role_id}", {"name": "Senior buyer"}, format="json"
    )
    assert renamed.status_code == 200
    row = client.get(url(org), {"action": "role.updated"}).json()["results"][0]
    assert row["action_label"] == "Role edited"
    assert {"field": "name", "old": "Buyer", "new": "Senior buyer"}.items() <= next(
        c for c in row["changes"] if c["field"] == "name"
    ).items()
    assert row["actor"]["user"]["id"] == str(owner.public_id)
