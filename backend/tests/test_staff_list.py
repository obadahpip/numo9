"""V-05-T02 — staff list API (role, organisations count, last sign-in, status).

Acceptance: practice-scoped — a practice's members and pending invitations only, with their role,
how many organisations each can open, last sign-in and status (active / dormant at day 60 /
suspended / pending); another practice's member sees 404.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from numo9.tenancy.models import Invitation, InvitationKind, PracticeMember, PracticeRole
from numo9.workspace.summary import rebuild_all
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = pytest.mark.django_db
URL = "/api/v1/practice/staff"


@pytest.fixture
def world() -> dict[str, Any]:
    firm = practice("Abuodeh CPA")
    other = practice("Other CPA")
    admin = user("ada@cpa.ca", name="Ada Admin")
    member(firm, admin, role=PracticeRole.PRACTICE_ADMIN)
    sam_user = user("sam@cpa.ca", name="Sam Patel")
    sam = member(firm, sam_user)
    lina_user = user("lina@cpa.ca", name="Lina Roy")
    lina = member(firm, lina_user, role=PracticeRole.REVIEWER)
    member(other, user("x@other.ca", name="Xavier Other"))
    for index in range(3):
        client_org(firm, f"Client {index}", staff=[sam] if index < 2 else [])
    rebuild_all()
    now = timezone.now()
    type(admin).objects.filter(pk=admin.pk).update(last_login=now)
    type(admin).objects.filter(pk=sam_user.pk).update(last_login=now - dt.timedelta(days=59))
    type(admin).objects.filter(pk=lina_user.pk).update(last_login=now - dt.timedelta(days=60))
    Invitation.objects.create(
        kind=InvitationKind.PRACTICE_STAFF,
        inviter=admin,
        practice=firm,
        role=PracticeRole.ACCOUNTANT,
        email="new@cpa.ca",
        token_hash="a" * 64,
        expires_at=now + dt.timedelta(days=14),
    )
    Invitation.objects.create(
        kind=InvitationKind.PRACTICE_STAFF,
        inviter=admin,
        practice=firm,
        role=PracticeRole.ACCOUNTANT,
        email="old@cpa.ca",
        token_hash="b" * 64,
        expires_at=now - dt.timedelta(days=1),
    )
    browser = Client()
    browser.force_login(admin)
    return {"firm": firm, "other": other, "browser": browser, "lina": lina, "sam": sam}


def test_staff_list(world: dict[str, Any]) -> None:
    response = world["browser"].get(f"{URL}?practice={world['firm'].public_id}")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["dormant_days"] == 60
    by_email = {line["email"]: line for line in body["staff"]}
    assert set(by_email) == {"ada@cpa.ca", "sam@cpa.ca", "lina@cpa.ca", "new@cpa.ca"}
    ada, sam, lina, new = (
        by_email[e] for e in ("ada@cpa.ca", "sam@cpa.ca", "lina@cpa.ca", "new@cpa.ca")
    )
    assert (ada["role"], ada["role_label"], ada["organisation_count"]) == (
        "practice_admin",
        "Practice admin",
        3,
    )
    assert (sam["organisation_count"], sam["status"]) == (2, "active")  # day 59
    assert (lina["status"], lina["dormant"]) == ("dormant", True)  # day 60
    assert lina["organisation_count"] == 0
    assert new["status"] == "pending" and new["invitation_expires_at"]


def test_suspended_member(world: dict[str, Any]) -> None:
    PracticeMember.objects.filter(pk=world["sam"].pk).update(suspended_at=timezone.now())
    body = world["browser"].get(f"{URL}?practice={world['firm'].public_id}").json()
    sam = next(line for line in body["staff"] if line["email"] == "sam@cpa.ca")
    assert (sam["status"], sam["organisation_count"], sam["dormant"]) == ("suspended", 0, False)


def test_practice_scoped(world: dict[str, Any]) -> None:
    assert world["browser"].get(f"{URL}?practice={world['other'].public_id}").status_code == 404
    outsider = Client()
    outsider.force_login(user("nobody@else.ca"))
    assert outsider.get(f"{URL}?practice={world['firm'].public_id}").status_code == 404
