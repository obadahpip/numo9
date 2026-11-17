"""V-03-T11 — audit per organisation (actor, bulk_job_id).

Acceptance: 200 organisations changed by one job → 200 ``bulk.<action>.applied`` events, one in
each organisation's log, attributed to the person who started the job (not "System") with the
job's id; the services' own events of the job carry it too; skipped organisations get none.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from numo9.audit.models import AuditEvent
from numo9.bulk import service
from numo9.tenancy.models import PracticeAssignment
from numo9.workspace.tags import create_tag
from tests.bulk_helpers import bulk_world

pytestmark = pytest.mark.django_db


def run(world: dict[str, Any], action: str, params: dict[str, Any]) -> Any:
    job, _preview = service.create_job(
        world["admin"],
        world["practice"],
        action,
        params,
        {"ids": [str(org.public_id) for org in world["orgs"]]},
    )
    with mock.patch.object(service, "start_job", return_value=None):
        service.confirm(job, world["admin"])
    service.execute(job)
    return job


def test_200_audit_rows_for_200_organisations() -> None:
    world = bulk_world(200, settings={"sales_terms_days": 30})
    job = run(
        world,
        "settings",
        {"settings": {"sales_terms": {"type": "days_after_document", "days": 15}}},
    )
    events = AuditEvent.platform_events.filter(action="bulk.settings.applied")
    assert events.count() == 200
    assert events.values("organisation").distinct().count() == 200
    assert set(events.values_list("organisation_id", flat=True)) == {o.pk for o in world["orgs"]}
    for event in events[:5]:
        assert event.actor_kind == "user" and event.actor_user == world["admin"]
        assert event.meta["bulk_job_id"] == str(job.public_id)
        assert event.changes["sales_terms"] == [
            {"type": "days_after_document", "days": 30},
            {"type": "days_after_document", "days": 15},
        ]
    # the settings' own change events are attributed the same way
    own = AuditEvent.platform_events.filter(meta__bulk_job_id=str(job.public_id)).exclude(
        action="bulk.settings.applied"
    )
    assert own.exists()
    assert set(own.values_list("actor_user", flat=True)) == {world["admin"].pk}


def test_skipped_organisations_get_no_event() -> None:
    world = bulk_world(3)
    tag = create_tag(world["practice"], "Retail")
    PracticeAssignment.objects.filter(organisation=world["orgs"][0]).update(active=False)
    job = run(world, "tags", {"add": [str(tag.public_id)]})
    events = AuditEvent.platform_events.filter(action="bulk.tags.applied")
    assert events.count() == 2
    assert world["orgs"][0].pk not in set(events.values_list("organisation_id", flat=True))
    assert job.rows.get(position=0).reason == "no_access"
