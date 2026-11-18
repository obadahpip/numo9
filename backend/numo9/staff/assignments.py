"""Assignments of a staff member (V-05-T04): the organisations they work on directly and the
groups they are assigned to (with the group role).

Direct assignment = the member on the organisation's practice assignment (``assigned_staff``,
A-01); group assignment = ``GroupStaffAssignment`` (V-02). Both take effect **on the next
request** — the V-02 access cache is invalidated by their signals (``m2m_changed`` on
``assigned_staff`` bumps it here), so assigning grants access at once and removing revokes it.
Each change is audited in the organisation's log (direct) or the practice's (group, V-02).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models.signals import m2m_changed

from numo9.audit.service import record
from numo9.tenancy.models import Organisation, PracticeAssignment, PracticeMember
from numo9.workspace.models import GroupStaffAssignment


class NotServed(LookupError):
    """The practice doesn't serve that organisation (or no longer does)."""


def assignment_for(member: PracticeMember, organisation: Organisation) -> PracticeAssignment:
    assignment = PracticeAssignment.objects.filter(
        practice_id=member.practice_id, organisation=organisation, active=True
    ).first()
    if assignment is None:
        raise NotServed(organisation.public_id)
    return assignment


def assignments_of(member: PracticeMember) -> dict[str, Any]:
    direct = (
        PracticeAssignment.objects.filter(
            practice_id=member.practice_id, active=True, assigned_staff=member
        )
        .select_related("organisation")
        .order_by("organisation__name")
    )
    groups = (
        GroupStaffAssignment.objects.filter(practice_member=member)
        .select_related("group")
        .order_by("group__path")
    )
    return {
        "organisations": [
            {"id": a.organisation.public_id, "name": a.organisation.name} for a in direct
        ],
        "groups": [
            {"id": g.group.public_id, "name": g.group.name, "role": g.role, "depth": g.group.depth}
            for g in groups
        ],
    }


def _audit(action: str, member: PracticeMember, organisation: Organisation) -> None:
    record(
        action,
        organisation=organisation,
        practice=member.practice,
        object_type="accounts.User",
        object_id=str(member.user.public_id),
        object_label=member.user.name or member.user.email,
        meta={"practice": member.practice.name, "member": member.user.email},
    )


def assign_organisation(member: PracticeMember, organisation: Organisation) -> bool:
    with transaction.atomic():
        assignment = assignment_for(member, organisation)
        if assignment.assigned_staff.filter(pk=member.pk).exists():
            return False
        assignment.assigned_staff.add(member)
        _audit("staff.organisation_assigned", member, organisation)
    return True


def unassign_organisation(member: PracticeMember, organisation: Organisation) -> bool:
    with transaction.atomic():
        assignment = PracticeAssignment.objects.filter(
            practice_id=member.practice_id, organisation=organisation
        ).first()
        if assignment is None or not assignment.assigned_staff.filter(pk=member.pk).exists():
            return False
        assignment.assigned_staff.remove(member)
        _audit("staff.organisation_unassigned", member, organisation)
    return True


def _staff_changed(sender: Any, **kwargs: Any) -> None:
    """Direct assignments change who may open what: invalidate the access cache (V-02-T06)."""
    if kwargs.get("action") in ("post_add", "post_remove", "post_clear"):
        from numo9.workspace.access import bump

        bump()


def connect() -> None:
    m2m_changed.connect(
        _staff_changed,
        sender=PracticeAssignment.assigned_staff.through,
        dispatch_uid="numo9.staff.assigned_staff_changed",
    )
