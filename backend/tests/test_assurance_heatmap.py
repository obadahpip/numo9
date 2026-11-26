"""K-09-T19 — user-activity heatmap from the audit log (A-04).

Acceptance: heatmap counts = audit counts (per day in the organisation's time zone and per
person, over the window); system events and other organisations don't count; a person filter
narrows it.
"""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.assurance.heatmap import heatmap, window
from numo9.audit import service as audit
from numo9.audit.models import AuditEvent
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.assurance_helpers import NOW, at
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


def _events(org: Organisation, user: object, *moments: dt.datetime) -> None:
    with org_context(org):
        for moment in moments:
            with at(moment):
                audit.record("contacts.contact.viewed", organisation=org, actor=user)


def test_heatmap_counts_equal_the_audit_log() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")
    other = Organisation.objects.create(name="Other Co.")
    staff = people(org)
    owner, adviser = staff["owner"], staff["adviser"]
    # 15 Jun 02:00 UTC is 14 Jun 22:00 in Toronto: the 14th there.
    _events(
        org,
        owner,
        dt.datetime(2026, 6, 15, 2, tzinfo=dt.UTC),
        dt.datetime(2026, 6, 15, 15, tzinfo=dt.UTC),
        dt.datetime(2026, 6, 15, 16, tzinfo=dt.UTC),
    )
    _events(org, adviser, dt.datetime(2026, 11, 20, 15, tzinfo=dt.UTC))
    _events(org, None, dt.datetime(2026, 11, 20, 15, tzinfo=dt.UTC))  # a system event
    _events(other, owner, dt.datetime(2026, 11, 20, 15, tzinfo=dt.UTC))
    found = heatmap(org, now=NOW)
    assert found["days"] == [
        {"date": "2026-06-14", "count": 1},
        {"date": "2026-06-15", "count": 2},
        {"date": "2026-11-20", "count": 1},
    ]
    since, _zone = window(org, 365, NOW)
    with org_context(org):
        audited = AuditEvent.objects.filter(
            organisation=org, actor_user__isnull=False, created_at__gte=since, created_at__lte=NOW
        ).count()
    assert found["total"] == audited == 4
    assert [(p["name"], p["count"]) for p in found["people"]] == [("Dana Lee", 3), ("Sam Patel", 1)]
    assert found["people"][0]["last"].startswith("2026-06-15T12:00")
    narrowed = heatmap(org, now=NOW, user=adviser)
    assert narrowed["total"] == 1
    assert heatmap(org, now=NOW, days=30)["total"] == 1
