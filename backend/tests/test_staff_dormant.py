"""V-05-T06 — dormant-user job (daily) → notification + dashboard widget.

Acceptance: the alert fires on day 60 without a sign-in, not on day 59 (frozen clock); once per
period of inactivity; to the practice's active admins only; suspended members are never
reported; the widget lists the dormant members with their days.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client
from freezegun import freeze_time

from numo9.notifications.models import EmailMessage
from numo9.staff.dormant import run_dormant_alerts
from numo9.staff.models import DormantAlert
from numo9.tenancy.models import PracticeMember, PracticeRole
from tests.workspace_helpers import member, practice, user

pytestmark = pytest.mark.django_db
LAST = dt.datetime(2026, 9, 1, 14, 0, tzinfo=dt.UTC)  # Lina's last sign-in


@pytest.fixture
def world() -> dict[str, Any]:
    firm = practice("Abuodeh CPA")
    ada = user("ada@cpa.ca", name="Ada Admin")
    member(firm, ada, role=PracticeRole.PRACTICE_ADMIN)
    bo = user("bo@cpa.ca", name="Bo Admin")
    bo_member = member(firm, bo, role=PracticeRole.PRACTICE_ADMIN)
    lina = user("lina@cpa.ca", name="Lina Roy", last_login=LAST)
    member(firm, lina)
    for person in (ada, bo):
        type(person).objects.filter(pk=person.pk).update(last_login=LAST + dt.timedelta(days=58))
    return {"firm": firm, "ada": ada, "bo": bo, "bo_member": bo_member, "lina": lina}


def emails() -> list[EmailMessage]:
    return list(EmailMessage.platform_messages.filter(kind="staff.dormant").order_by("to_email"))


def test_alert_on_day_60_not_59(world: dict[str, Any]) -> None:
    with freeze_time(LAST + dt.timedelta(days=59, hours=2)):
        assert run_dormant_alerts() == 0
    assert emails() == []
    with freeze_time(LAST + dt.timedelta(days=60, hours=2)):
        assert run_dormant_alerts() == 1
    sent = emails()
    assert [e.to_email for e in sent] == ["ada@cpa.ca", "bo@cpa.ca"]
    assert sent[0].subject == "Lina Roy hasn't signed in for 60 days"
    assert f"/p/{world['firm'].public_id}/staff/{world['lina'].public_id}" in sent[0].text_body
    with freeze_time(LAST + dt.timedelta(days=61, hours=2)):
        assert run_dormant_alerts() == 0  # once per period of inactivity
    assert DormantAlert.objects.count() == 1


def test_signing_in_again_restarts_the_count(world: dict[str, Any]) -> None:
    with freeze_time(LAST + dt.timedelta(days=60, hours=2)):
        run_dormant_alerts()
    back = LAST + dt.timedelta(days=62)
    type(world["lina"]).objects.filter(pk=world["lina"].pk).update(last_login=back)
    type(world["ada"]).objects.filter(pk__in=[world["ada"].pk, world["bo"].pk]).update(
        last_login=back + dt.timedelta(days=58)
    )
    with freeze_time(back + dt.timedelta(days=59, hours=2)):
        assert run_dormant_alerts() == 0
    with freeze_time(back + dt.timedelta(days=60, hours=2)):
        assert run_dormant_alerts() == 1
    assert DormantAlert.objects.count() == 2


def test_suspended_admins_and_members_are_left_out(world: dict[str, Any]) -> None:
    PracticeMember.objects.filter(pk=world["bo_member"].pk).update(suspended_at=LAST)
    with freeze_time(LAST + dt.timedelta(days=60, hours=2)):
        run_dormant_alerts()
    assert [e.to_email for e in emails()] == ["ada@cpa.ca"]  # Bo is suspended: not alerted
    PracticeMember.objects.filter(user=world["lina"]).update(suspended_at=LAST)
    DormantAlert.objects.all().delete()
    with freeze_time(LAST + dt.timedelta(days=61)):
        assert run_dormant_alerts() == 0


def test_dashboard_widget(world: dict[str, Any]) -> None:
    browser = Client()
    browser.force_login(world["ada"])
    with freeze_time(LAST + dt.timedelta(days=65, hours=2)):
        body = browser.get(
            f"/api/v1/practice/staff/dormant?practice={world['firm'].public_id}"
        ).json()
    assert body["dormant_days"] == 60
    assert [(s["email"], s["days"]) for s in body["staff"]] == [("lina@cpa.ca", 65)]
    lina = Client()
    lina.force_login(world["lina"])
    refused = lina.get(f"/api/v1/practice/staff/dormant?practice={world['firm'].public_id}")
    assert refused.status_code == 403  # practice.staff.manage
