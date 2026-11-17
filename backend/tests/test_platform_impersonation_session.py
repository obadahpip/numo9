"""U-06-T08 — ``ImpersonationSession`` model (actor, target user, organisation, reason, started,
expires, ended).

Acceptance: a row is created per session — with the reason, a 30-minute default and a 2-hour cap
(the database refuses longer), one open session per staff member, only members of the chosen
organisation, never oneself or other platform staff; expiry closes the session.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.db import IntegrityError, transaction

from numo9.platform import impersonation
from numo9.platform.impersonation import ImpersonationRefused
from numo9.platform.models import ImpersonationSession
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
NOW = dt.datetime(2026, 11, 18, 15, tzinfo=dt.UTC)


@pytest.fixture
def cast() -> dict[str, object]:
    staff = user("support@numo9.ca")
    RoleAssignment.objects.create(
        user=staff, role=Role.objects.get(scope=RoleScope.PLATFORM, key="platform_support")
    )
    org = Organisation.objects.create(name="Maple")
    other = Organisation.objects.create(name="Birch")
    owner = user("owner@maple.ca")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    OrganisationMember.objects.create(organisation=other, user=owner, role="owner")
    return {"staff": staff, "org": org, "other": other, "owner": owner}


def test_a_row_per_session_with_default_time_box(cast: dict[str, object]) -> None:
    session = impersonation.start(
        cast["staff"], cast["owner"], cast["org"], "  Ticket #42: bank feed  ", now=NOW
    )
    row = ImpersonationSession.objects.get()
    assert row.pk == session.pk
    assert (row.actor, row.target_user, row.organisation) == (
        cast["staff"],
        cast["owner"],
        cast["org"],
    )
    assert row.reason == "Ticket #42: bank feed"
    assert row.started_at == NOW and row.expires_at == NOW + dt.timedelta(minutes=30)
    assert row.ended_at is None and row.is_open(NOW)
    assert impersonation.current(cast["staff"], NOW) == row
    assert row.end("ended", NOW + dt.timedelta(minutes=5))
    assert impersonation.current(cast["staff"], NOW) is None
    second = impersonation.start(cast["staff"], cast["owner"], cast["other"], "again", 120, NOW)
    assert ImpersonationSession.objects.count() == 2
    assert second.expires_at == NOW + dt.timedelta(hours=2)


@pytest.mark.parametrize(
    ("reason", "minutes", "code"),
    [
        ("", 30, "reason_required"),
        ("   ", 30, "reason_required"),
        ("x" * 501, 30, "reason_too_long"),
        ("ok", 0, "bad_duration"),
        ("ok", 121, "bad_duration"),
    ],
)
def test_reason_and_duration_rules(
    cast: dict[str, object], reason: str, minutes: int, code: str
) -> None:
    with pytest.raises(ImpersonationRefused) as refused:
        impersonation.start(cast["staff"], cast["owner"], cast["org"], reason, minutes, NOW)
    assert refused.value.code == code
    assert not ImpersonationSession.objects.exists()


def test_only_a_member_of_that_organisation_never_self_or_staff(cast: dict[str, object]) -> None:
    stranger = user("someone@else.ca")
    for target, code in ((stranger, "not_a_member"), (cast["staff"], "not_self")):
        with pytest.raises(ImpersonationRefused) as refused:
            impersonation.start(cast["staff"], target, cast["org"], "why", now=NOW)
        assert refused.value.code == code
    colleague = user("owner2@numo9.ca")
    RoleAssignment.objects.create(
        user=colleague, role=Role.objects.get(scope=RoleScope.PLATFORM, key="platform_owner")
    )
    OrganisationMember.objects.create(organisation=cast["org"], user=colleague, role="admin")
    with pytest.raises(ImpersonationRefused) as refused:
        impersonation.start(cast["staff"], colleague, cast["org"], "why", now=NOW)
    assert refused.value.code == "platform_user"


def test_one_open_session_per_staff_member(cast: dict[str, object]) -> None:
    impersonation.start(cast["staff"], cast["owner"], cast["org"], "one", now=NOW)
    with pytest.raises(ImpersonationRefused) as refused:
        impersonation.start(cast["staff"], cast["owner"], cast["other"], "two", now=NOW)
    assert refused.value.code == "already_open"
    later = NOW + dt.timedelta(minutes=31)  # the first expired: closed, a new one starts
    impersonation.start(cast["staff"], cast["owner"], cast["other"], "two", now=later)
    first = ImpersonationSession.objects.get(reason="one")
    assert first.end_reason == "expired" and first.ended_at == first.expires_at


def test_expiry_closes_the_session(cast: dict[str, object]) -> None:
    session = impersonation.start(cast["staff"], cast["owner"], cast["org"], "why", 10, NOW)
    assert impersonation.current(cast["staff"], NOW + dt.timedelta(minutes=10)) is None
    session.refresh_from_db()
    assert session.end_reason == "expired"
    assert not session.end("ended")  # once only


def test_database_enforces_the_time_box(cast: dict[str, object]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ImpersonationSession.objects.create(
            actor=cast["staff"],
            target_user=cast["owner"],
            organisation=cast["org"],
            reason="why",
            started_at=NOW,
            expires_at=NOW + dt.timedelta(minutes=121),
        )
