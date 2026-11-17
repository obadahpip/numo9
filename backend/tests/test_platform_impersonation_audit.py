"""U-06-T10 — audit entries in the target organisation's log for the start and end of an
impersonation session and every write during it (``acting_as``).

Acceptance: the organisation's owner sees the entries — start (with the reason), the write made
during the session (attributed to the user, signed in by the staff member) and the end.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.platform.models import ImpersonationSession
from numo9.tenancy.models import OrganisationMember
from tests.test_platform_impersonation_auth import START, staff
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def world() -> dict[str, Any]:
    from numo9.tenancy.models import Organisation

    org = Organisation.objects.create(name="Maple Leaf Supply")
    owner = user("dana@maple.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    actor, browser = staff()
    return {"org": org, "owner": owner, "actor": actor, "browser": browser}


def begin(world: dict[str, Any], minutes: int = 30) -> dict[str, Any]:
    response = world["browser"].post(
        START,
        {
            "organisation": str(world["org"].public_id),
            "user": str(world["owner"].public_id),
            "reason": "Ticket #42: invoice layout",
            "minutes": minutes,
        },
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    return response.json()


def owner_log(world: dict[str, Any]) -> list[dict[str, Any]]:
    owner = Client()
    owner.force_login(world["owner"])
    response = owner.get(f"/api/v1/o/{world['org'].public_id}/audit/events?page_size=100")
    assert response.status_code == 200, response.content
    return response.json()["results"]


def test_owner_sees_start_writes_and_end(world: dict[str, Any]) -> None:
    session = begin(world)
    browser = world["browser"]
    write = browser.patch(
        f"/api/v1/o/{world['org'].public_id}/settings",
        {"display_name": "Maple Leaf Supply Ltd."},
        content_type="application/json",
    )
    assert write.status_code == 200, write.content
    assert browser.post(f"{START}/end").status_code == 200

    events = AuditEvent.platform_events.filter(organisation=world["org"]).order_by("created_at")
    started = events.get(action="platform.impersonation.started")
    ended = events.get(action="platform.impersonation.ended")
    writes = events.exclude(action__startswith="platform.impersonation")
    assert writes.exists()
    for event in (started, *writes, ended):
        assert event.actor_kind == "impersonation"
        assert event.actor_user == world["owner"] and event.impersonator == world["actor"]
        assert event.meta["acting_as"] == "Dana Lee (dana@maple.ca)"
        assert event.meta["impersonation_session"] == session["id"]
    assert started.meta["reason"] == "Ticket #42: invoice layout"
    assert ended.meta["end_reason"] == "ended"
    assert started.created_at <= min(w.created_at for w in writes) <= ended.created_at

    shown = {row["action"]: row for row in owner_log(world)}
    assert {"platform.impersonation.started", "platform.impersonation.ended"} <= set(shown)
    start_row = shown["platform.impersonation.started"]
    assert start_row["actor"]["kind"] == "impersonation"
    assert start_row["actor"]["user"]["email"] == "dana@maple.ca"
    assert start_row["actor"]["impersonator"]["name"] == "Sam Support"
    assert start_row["actor"]["label"].startswith("Dana Lee (dana@maple.ca) — signed in by Sam")
    assert start_row["action_label"] == "Numo9 support signed in as this user"
    assert start_row["meta"]["reason"] == "Ticket #42: invoice layout"
    assert shown["platform.impersonation.ended"]["action_label"] == "Numo9 support session ended"


def test_expiry_is_logged_as_the_end(world: dict[str, Any]) -> None:
    begin(world, minutes=5)
    ImpersonationSession.objects.update(
        started_at=timezone.now() - dt.timedelta(minutes=6),
        expires_at=timezone.now() - dt.timedelta(minutes=1),
    )
    world["browser"].get("/api/v1/me/organisations")
    ended = AuditEvent.platform_events.get(
        organisation=world["org"], action="platform.impersonation.ended"
    )
    assert ended.meta["end_reason"] == "expired"
    assert ended.impersonator == world["actor"]
