"""V-03-T06 — actions: group, tags, staff, settings, message (A-07), export (CSV/XLSX).

Acceptance: each action's fixture passes — the job changes what it says for every organisation,
skips what it must (with the reason) and leaves the rest alone.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest
from openpyxl import load_workbook

from numo9.bulk import service
from numo9.bulk.exports import export_file, results_csv
from numo9.bulk.models import BulkJob
from numo9.notifications.models import Notification
from numo9.orgsettings.models import OrganisationSettings
from numo9.tenancy.models import PracticeAssignment
from numo9.workspace.groups import add_organisation, create_group
from numo9.workspace.models import OrgGroupMembership, OrgTag
from numo9.workspace.tags import create_tag, tag_organisation
from tests.bulk_helpers import bulk_world

pytestmark = pytest.mark.django_db


@pytest.fixture
def world() -> dict[str, Any]:
    return bulk_world(3, settings={"sales_terms_days": 30})


def run(world: dict[str, Any], action: str, params: dict[str, Any], orgs: Any = None) -> BulkJob:
    selection = {"ids": [str(org.public_id) for org in (orgs or world["orgs"])]}
    job, _preview = service.create_job(world["admin"], world["practice"], action, params, selection)
    from unittest import mock

    with (
        mock.patch("numo9.jobs.runtime.start_job", return_value=None),
        mock.patch.object(service, "start_job", return_value=None),
    ):
        service.confirm(job, world["admin"])
    service.execute(job)
    job.refresh_from_db()
    return job


def outcome(job: BulkJob) -> list[tuple[str, str]]:
    return list(job.rows.order_by("position").values_list("outcome", "reason"))


def test_group_move_add_remove(world: dict[str, Any]) -> None:
    practice, orgs = world["practice"], world["orgs"]
    old = create_group(practice, "Old office")
    new = create_group(practice, "Toronto office")
    add_organisation(old, orgs[0])
    job = run(world, "group", {"group": str(new.public_id), "mode": "move"})
    assert outcome(job) == [("succeeded", "")] * 3
    assert set(OrgGroupMembership.objects.values_list("group__name", flat=True)) == {
        "Toronto office"
    }
    first = job.rows.get(position=0)
    assert (first.before, first.after) == (
        {"groups": ["Old office"]},
        {"groups": ["Toronto office"]},
    )
    again = run(world, "group", {"group": str(new.public_id), "mode": "add"})
    assert outcome(again) == [("skipped", "no_change")] * 3
    removed = run(world, "group", {"group": str(new.public_id), "mode": "remove"}, orgs[:1])
    assert outcome(removed) == [("succeeded", "")]
    assert OrgGroupMembership.objects.count() == 2


def test_tags_add_and_remove(world: dict[str, Any]) -> None:
    retail = create_tag(world["practice"], "Retail")
    vip = create_tag(world["practice"], "VIP")
    tag_organisation(vip, world["orgs"][0])
    job = run(world, "tags", {"add": [str(retail.public_id)], "remove": [str(vip.public_id)]})
    assert outcome(job) == [("succeeded", "")] * 3
    assert sorted(OrgTag.objects.values_list("tag__name", flat=True)) == ["Retail"] * 3
    assert job.rows.get(position=0).before == {"tags": ["VIP"]}


def test_staff_assign_and_unassign(world: dict[str, Any]) -> None:
    member = world["accountant"]
    PracticeAssignment.objects.filter(organisation=world["orgs"][2]).update(active=False)
    job = run(world, "staff", {"member": str(world["accountant_user"].public_id), "mode": "assign"})
    assert outcome(job)[:2] == [("succeeded", "")] * 2
    assert outcome(job)[2] == ("skipped", "no_access")
    assert PracticeAssignment.objects.filter(assigned_staff=member).count() == 2
    off = run(
        world,
        "staff",
        {"member": str(world["accountant_user"].public_id), "mode": "unassign"},
        world["orgs"][:2],
    )
    assert outcome(off) == [("succeeded", "")] * 2
    assert not PracticeAssignment.objects.filter(assigned_staff=member).exists()


def test_settings_change_and_fiscal_year_guard(world: dict[str, Any]) -> None:
    job = run(
        world,
        "settings",
        {"settings": {"sales_terms": {"type": "days_after_document", "days": 15}}},
    )
    assert outcome(job) == [("succeeded", "")] * 3
    assert OrganisationSettings._base_manager.filter(sales_terms_days=15).count() == 3

    guarded = world["orgs"][1]
    with mock_posted(guarded):
        fye = run(world, "settings", {"settings": {"fiscal_year_end": {"month": 3, "day": 31}}})
    assert outcome(fye)[1] == ("skipped", "fye_has_posted")
    assert outcome(fye)[0] == ("succeeded", "")
    assert OrganisationSettings._base_manager.get(organisation=guarded).fye_month == 12


def mock_posted(organisation: Any) -> Any:
    from unittest import mock

    from numo9.bulk import safe_settings

    real = safe_settings._has_posted
    return mock.patch.dict(
        safe_settings.SAFE_SETTINGS,
        {
            "fiscal_year_end": safe_settings.SafeSetting(
                "fiscal_year_end",
                {"month": "fye_month", "day": "fye_day"},
                safe_settings._fiscal_year_end,
                guard=lambda org: "fye_has_posted" if org == organisation else real(org),
            )
        },
    )


def test_message_notifies_owners(world: dict[str, Any]) -> None:
    job = run(world, "message", {"subject": "Year-end checklist", "body": "Please send receipts."})
    assert outcome(job) == [("succeeded", "")] * 3
    notes = Notification._base_manager.filter(title_key="notifications.practice.message")
    assert notes.count() == 3
    assert {n.recipient for n in notes} == set(world["owners"])
    assert notes.first().body_params["subject"] == "Year-end checklist"


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_export_lists_the_organisations(world: dict[str, Any], fmt: str) -> None:
    tag_organisation(create_tag(world["practice"], "Retail"), world["orgs"][0])
    job = run(world, "export", {"format": fmt})
    assert outcome(job) == [("succeeded", "")] * 3
    content, kind, name = export_file(job)
    if fmt == "csv":
        lines = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        assert lines[0][:2] == ["Organisation", "Business Number"]
        assert [line[0] for line in lines[1:]] == ["Client 000", "Client 001", "Client 002"]
        assert lines[1][4] == "Retail"
        assert kind == "text/csv" and name.endswith(".csv")
    else:
        sheet = load_workbook(io.BytesIO(content)).active
        assert [c.value for c in sheet[2]][0] == "Client 000"
        assert sheet.max_row == 4 and name.endswith(".xlsx")


def test_results_csv_has_every_organisation(world: dict[str, Any]) -> None:
    job = run(world, "tags", {"add": [str(create_tag(world["practice"], "A").public_id)]})
    lines = list(csv.reader(io.StringIO(results_csv(job).decode("utf-8-sig"))))
    assert len(lines) == 4 and lines[0][:3] == ["Organisation", "Outcome", "Reason"]
    assert {line[1] for line in lines[1:]} == {"Succeeded"}
