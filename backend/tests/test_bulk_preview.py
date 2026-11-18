"""V-03-T04 — preview service (computes diffs without writing).

Acceptance: the preview writes 0 rows — no organisation data, no audit event, no bulk row —
while reporting one line per selected organisation (change / no change / skipped with the
reason), for a list of ids and for "all matching" (the directory's query).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from numo9.audit.models import AuditEvent
from numo9.bulk.models import BulkJobRow
from numo9.bulk.preview import preview
from numo9.orgsettings.models import OrganisationSettings
from numo9.workspace.models import OrgGroupMembership, OrgTag
from numo9.workspace.tags import create_tag, tag_organisation
from tests.bulk_helpers import bulk_world

pytestmark = pytest.mark.django_db


@pytest.fixture
def world() -> dict[str, Any]:
    return bulk_world(4, settings={"sales_terms_days": 30})


def ids(*orgs: Any) -> dict[str, list[str]]:
    return {"ids": [str(org.public_id) for org in orgs]}


def test_preview_writes_nothing(world: dict[str, Any]) -> None:
    orgs = world["orgs"]
    events = AuditEvent.platform_events.count()
    with CaptureQueriesContext(connection) as queries:
        result = preview(
            world["admin"],
            world["practice"],
            "settings",
            {"settings": {"sales_terms": {"type": "days_after_document", "days": 15}}},
            ids(*orgs, world["stranger"]),
        )
    writes = [
        q["sql"]
        for q in queries.captured_queries
        if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
    ]
    assert writes == []
    assert AuditEvent.platform_events.count() == events
    assert not BulkJobRow.objects.exists()
    assert OrganisationSettings._base_manager.filter(sales_terms_days=15).count() == 0
    assert result["total"] == 5
    assert result["counts"] == {"change": 4, "no_change": 0, "skipped": 1}
    first = result["lines"][0]
    assert first["status"] == "change"
    assert first["before"] == {"sales_terms": {"type": "days_after_document", "days": 30}}
    assert first["after"] == {"sales_terms": {"type": "days_after_document", "days": 15}}
    skipped = result["lines"][-1]
    assert (skipped["status"], skipped["reason"]) == ("skipped", "no_access")
    assert skipped["message"] == "You don't have access to this organisation."


def test_an_organisation_without_settings_is_previewed_without_creating_them() -> None:
    world = bulk_world(1)
    OrganisationSettings._base_manager.all().delete()
    result = preview(
        world["admin"],
        world["practice"],
        "settings",
        {"settings": {"time_format": {"value": "24h"}}},
        ids(*world["orgs"]),
    )
    assert result["lines"][0]["before"] == {"time_format": {"value": "12h"}}
    assert not OrganisationSettings._base_manager.exists()


def test_no_change_is_reported(world: dict[str, Any]) -> None:
    tag = create_tag(world["practice"], "Retail")
    tag_organisation(tag, world["orgs"][0])
    result = preview(
        world["admin"],
        world["practice"],
        "tags",
        {"add": [str(tag.public_id)], "remove": []},
        ids(*world["orgs"][:2]),
    )
    assert [line["status"] for line in result["lines"]] == ["no_change", "change"]
    assert result["lines"][1]["after"] == {"tags": ["Retail"]}
    assert OrgTag.objects.count() == 1


def test_select_all_matching_uses_the_directory_query(world: dict[str, Any]) -> None:
    result = preview(
        world["admin"], world["practice"], "export", {"format": "csv"}, {"query": {"q": "Client"}}
    )
    assert result["total"] == 4  # the practice's clients only, found by the server
    names = [line["organisation"]["name"] for line in result["lines"]]
    assert sorted(names) == ["Client 000", "Client 001", "Client 002", "Client 003"]
    narrowed = preview(
        world["admin"], world["practice"], "export", {"format": "csv"}, {"query": {"q": "001"}}
    )
    assert narrowed["total"] == 1


def test_lines_are_capped_at_50_with_the_total() -> None:
    world = bulk_world(55)
    result = preview(
        world["admin"], world["practice"], "export", {"format": "csv"}, ids(*world["orgs"])
    )
    assert result["total"] == 55 and len(result["lines"]) == 50
    assert not OrgGroupMembership.objects.exists()
