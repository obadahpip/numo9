"""V-02-T13 — Audit entries for group, tag and assignment changes.

Acceptance: audited. Every change writes one event with the actor: group created, renamed,
moved, deleted (practice-level events, ``practice`` set); staff assigned, role changed,
unassigned; organisation filed in / taken out of a group and tagged / untagged — those also in
the organisation's own log (``organisation`` set); tag created, renamed, recoloured, deleted.
A rule refused writes nothing; repeating a change that changes nothing writes nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from numo9.audit.context import audit_context
from numo9.audit.models import AuditEvent
from numo9.workspace.groups import (
    GroupError,
    add_organisation,
    assign_staff,
    create_group,
    delete_group,
    move_group,
    remove_organisation,
    rename_group,
    unassign_staff,
)
from numo9.workspace.tags import (
    create_tag,
    delete_tag,
    recolour_tag,
    rename_tag,
    tag_organisation,
    untag_organisation,
)
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = pytest.mark.django_db


def _events() -> list[AuditEvent]:
    return list(AuditEvent.platform_events.filter(action__startswith="workspace.").order_by("id"))


def _summary() -> list[tuple[str, Any, Any]]:
    return [(e.action, e.organisation_id, e.changes) for e in _events()]


def test_every_change_is_audited_with_actor_and_scope() -> None:
    admin = user("oa@abuodeh.ca", "Obadah Abuodeh")
    firm = practice("Abuodeh CPA", admin)
    org = client_org(firm, "Maple Leaf Supply Ltd.")
    sam = member(firm, user("sam@abuodeh.ca", "Sam Patel"))
    with audit_context(user=admin):
        toronto = create_group(firm, "Toronto office")
        retail = create_group(firm, "Retail", toronto)
        rename_group(retail, "Retail clients")
        rename_group(retail, "Retail clients")  # no change: no event
        add_organisation(retail, org)
        add_organisation(retail, org)  # already filed: no event
        assign_staff(toronto, sam)
        assign_staff(toronto, sam, "reviewer")
        move_group(retail, None)
        with pytest.raises(GroupError):
            create_group(firm, "Toronto office")  # refused: nothing written
        remove_organisation(retail, org)
        unassign_staff(toronto, sam)
        tag = create_tag(firm, "VIP", "amber")
        rename_tag(tag, "Key client")
        recolour_tag(tag, "red")
        tag_organisation(tag, org)
        untag_organisation(tag, org)
        delete_tag(tag)
        delete_group(toronto)
    actions = [action for action, _org, _changes in _summary()]
    assert actions == [
        "workspace.group.created",
        "workspace.group.created",
        "workspace.group.renamed",
        "workspace.group.organisation_added",
        "workspace.group.staff_assigned",
        "workspace.group.staff_role_changed",
        "workspace.group.moved",
        "workspace.group.organisation_removed",
        "workspace.group.staff_unassigned",
        "workspace.tag.created",
        "workspace.tag.renamed",
        "workspace.tag.recoloured",
        "workspace.tag.organisation_tagged",
        "workspace.tag.organisation_untagged",
        "workspace.tag.deleted",
        "workspace.group.deleted",
    ]
    events = _events()
    assert all(e.actor_user_id == admin.pk and e.practice_id == firm.pk for e in events)
    in_org_log = {e.action for e in events if e.organisation_id == org.pk}
    assert in_org_log == {
        "workspace.group.organisation_added",
        "workspace.group.organisation_removed",
        "workspace.tag.organisation_tagged",
        "workspace.tag.organisation_untagged",
    }
    by_action = {e.action: e for e in events}
    assert by_action["workspace.group.renamed"].changes == {"name": ["Retail", "Retail clients"]}
    assert by_action["workspace.group.moved"].changes == {"parent": ["Toronto office", None]}
    assert by_action["workspace.group.staff_role_changed"].changes == {
        "role": ["accountant", "reviewer"]
    }
    assert by_action["workspace.group.staff_role_changed"].meta["name"] == "Sam Patel"
    assert by_action["workspace.tag.recoloured"].changes == {"colour": ["amber", "red"]}
