"""V-05-T07 — activity aggregation from the audit log (daily counts per user), materialised.

Data validation: the materialised counts equal the audit log's — per person and per Toronto
calendar day (an event at 23:30 Toronto counts on that day, not the next UTC day), across
organisations; recomputing after more events updates the day; the API answers the heatmap's days.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client
from freezegun import freeze_time

from numo9.audit.models import AuditEvent
from numo9.audit.service import record
from numo9.staff.activity import ACTIVITY_TIME_ZONE, aggregate, audit_counts
from numo9.staff.models import StaffActivityDaily
from numo9.tenancy.models import Organisation, PracticeRole
from tests.workspace_helpers import member, practice, user

pytestmark = pytest.mark.django_db
TZ = ACTIVITY_TIME_ZONE


def at(year: int, month: int, day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=TZ)


def events(person: Any, org: Organisation, moments: list[dt.datetime]) -> None:
    for moment in moments:
        with freeze_time(moment):
            record("contacts.contact.updated", organisation=org, actor=person, object_type="x")


@pytest.fixture
def world() -> dict[str, Any]:
    firm = practice("Abuodeh CPA")
    ada = user("ada@cpa.ca", name="Ada Admin")
    member(firm, ada, role=PracticeRole.PRACTICE_ADMIN)
    sam = user("sam@cpa.ca", name="Sam Patel")
    member(firm, sam)
    maple, birch = (
        Organisation.objects.create(name="Maple"),
        Organisation.objects.create(name="Birch"),
    )
    events(sam, maple, [at(2026, 11, 2, 9), at(2026, 11, 2, 14), at(2026, 11, 2, 23, 30)])
    events(sam, birch, [at(2026, 11, 3, 0, 15), at(2026, 11, 5, 10)])
    events(ada, maple, [at(2026, 11, 2, 10)])
    return {"firm": firm, "ada": ada, "sam": sam, "maple": maple}


def test_materialised_counts_equal_the_audit_log(world: dict[str, Any]) -> None:
    since, until = dt.date(2026, 11, 1), dt.date(2026, 11, 30)
    aggregate(since, until)
    stored = {(row.user_id, row.date): row.count for row in StaffActivityDaily.objects.all()}
    assert stored == audit_counts(since, until)
    sam = world["sam"].pk
    assert stored[(sam, dt.date(2026, 11, 2))] == 3  # 23:30 Toronto stays on the 2nd
    assert stored[(sam, dt.date(2026, 11, 3))] == 1
    assert stored[(sam, dt.date(2026, 11, 5))] == 1
    assert stored[(world["ada"].pk, dt.date(2026, 11, 2))] == 1
    total = AuditEvent.platform_events.filter(actor_user=world["sam"]).count()
    assert sum(v for (u, _d), v in stored.items() if u == sam) == total


def test_recomputing_follows_new_events(world: dict[str, Any]) -> None:
    aggregate(dt.date(2026, 11, 1), dt.date(2026, 11, 30))
    events(world["sam"], world["maple"], [at(2026, 11, 5, 16)])
    aggregate(dt.date(2026, 11, 5), dt.date(2026, 11, 5))
    assert StaffActivityDaily.objects.get(user=world["sam"], date=dt.date(2026, 11, 5)).count == 2
    assert StaffActivityDaily.objects.filter(user=world["sam"]).count() == 3


def test_api_answers_the_heatmap_days(world: dict[str, Any]) -> None:
    aggregate(dt.date(2026, 11, 1), dt.date(2026, 11, 30))
    browser = Client()
    browser.force_login(world["ada"])
    with freeze_time(at(2026, 11, 18, 12)):
        body = browser.get(
            f"/api/v1/practice/staff/{world['sam'].public_id}/activity"
            f"?practice={world['firm'].public_id}"
        ).json()
    assert body["to"] == "2026-11-18" and body["from"] == "2025-11-19"
    assert body["total"] == 5
    assert body["days"] == [
        {"date": "2026-11-02", "count": 3},
        {"date": "2026-11-03", "count": 1},
        {"date": "2026-11-05", "count": 1},
    ]
