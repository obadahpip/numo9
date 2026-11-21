"""V-05-T03 — practice staff invitation: the A-02 invite flow with a practice role, pending in the
staff list until accepted, expiring at 14 days.

Acceptance: the invite expires at 14 days (organisation invitations keep 7); it shows "pending"
with its expiry and role in the staff list; resending gives a fresh 14 days; a revoked or expired
one leaves the list; accepting before day 14 makes a member with the chosen role; on day 14 the
link no longer works.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from numo9.tenancy.models import (
    Invitation,
    InvitationKind,
    PracticeMember,
    PracticeRole,
    invitation_ttl,
)
from tests.workspace_helpers import member, practice, user

pytestmark = pytest.mark.django_db
STAFF = "/api/v1/practice/staff"


@pytest.fixture
def firm() -> dict[str, Any]:
    office = practice("Abuodeh CPA")
    admin = user("ada@cpa.ca", name="Ada Admin")
    member(office, admin, role=PracticeRole.PRACTICE_ADMIN)
    browser = Client()
    browser.force_login(admin)
    return {"practice": office, "browser": browser}


def invite(firm: dict[str, Any], email: str = "new@cpa.ca", role: str = "reviewer") -> Any:
    return firm["browser"].post(
        "/api/v1/invitations",
        {
            "kind": "practice_staff",
            "practice": str(firm["practice"].public_id),
            "email": email,
            "role": role,
        },
        content_type="application/json",
    )


def token() -> str:
    match = re.search(r"/invite/(\S+)", str(mail.outbox[-1].body))
    assert match, mail.outbox[-1].body
    return match.group(1)


def pending(firm: dict[str, Any]) -> list[dict[str, Any]]:
    rows = firm["browser"].get(STAFF, {"practice": str(firm["practice"].public_id)}).json()
    return [r for r in rows["staff"] if r["status"] == "pending"]


def test_staff_invitation_expires_at_14_days(firm: dict[str, Any]) -> None:
    assert invitation_ttl(InvitationKind.PRACTICE_STAFF) == dt.timedelta(days=14)
    assert invitation_ttl(InvitationKind.ORGANISATION_USER) == dt.timedelta(days=7)
    response = invite(firm)
    assert response.status_code == 201, response.content
    expires = dt.datetime.fromisoformat(response.json()["expires_at"])
    assert abs(expires - (timezone.now() + dt.timedelta(days=14))) < dt.timedelta(minutes=1)
    assert response.json()["role"] == "reviewer"


def test_pending_in_the_staff_list_with_role_and_expiry(firm: dict[str, Any]) -> None:
    invite(firm)
    (row,) = pending(firm)
    assert row["email"] == "new@cpa.ca" and row["role"] == "reviewer"
    assert row["invitation_expires_at"] is not None


def test_resend_gives_a_fresh_14_days(firm: dict[str, Any]) -> None:
    created = invite(firm).json()
    Invitation.objects.filter(public_id=created["id"]).update(
        expires_at=timezone.now() + dt.timedelta(days=1), last_sent_at=None
    )
    response = firm["browser"].post(f"/api/v1/invitations/{created['id']}/resend")
    assert response.status_code == 200, response.content
    expires = dt.datetime.fromisoformat(response.json()["expires_at"])
    assert expires - timezone.now() > dt.timedelta(days=13, hours=23)


def test_revoked_and_expired_leave_the_list(firm: dict[str, Any]) -> None:
    one = invite(firm, "one@cpa.ca").json()
    invite(firm, "two@cpa.ca")
    firm["browser"].post(f"/api/v1/invitations/{one['id']}/revoke")
    Invitation.objects.filter(email="two@cpa.ca").update(
        expires_at=timezone.now() - dt.timedelta(seconds=1)
    )
    assert pending(firm) == []


def test_accept_before_day_14_makes_a_member_with_the_role(firm: dict[str, Any]) -> None:
    invite(firm, role="payroll_specialist")
    link = token()
    Invitation.objects.update(expires_at=timezone.now() + dt.timedelta(hours=1))  # day 13 and a bit
    newcomer = user("new@cpa.ca", name="Nina New")
    browser = Client()
    browser.force_login(newcomer)
    response = browser.post(
        "/api/v1/invitations/accept", {"token": link}, content_type="application/json"
    )
    assert response.status_code == 200, response.content
    membership = PracticeMember.objects.get(practice=firm["practice"], user=newcomer)
    assert membership.role == "payroll_specialist"


def test_day_14_the_link_no_longer_works(firm: dict[str, Any]) -> None:
    invite(firm)
    link = token()
    Invitation.objects.update(expires_at=timezone.now() - dt.timedelta(seconds=1))
    newcomer = user("new@cpa.ca", name="Nina New")
    browser = Client()
    browser.force_login(newcomer)
    response = browser.post(
        "/api/v1/invitations/accept", {"token": link}, content_type="application/json"
    )
    assert response.status_code in (400, 404, 410)
    assert not PracticeMember.objects.filter(user=newcomer).exists()
