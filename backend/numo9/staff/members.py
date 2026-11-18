"""Suspend, reinstate and remove a practice member (V-05-T05).

- **Suspend** keeps the member and their history (assignments, audit) but they reach nothing
  through the practice: every access path ignores a suspended member (A-01 ``accessible_
  organisations`` and the RBAC resolver for direct and practice-wide access, V-02 group access,
  the directory and the practice API) — on the next request, since the access cache is bumped.
- **Reinstate** lifts the suspension.
- **Remove** deletes the membership with its direct and group assignments (history stays in the
  audit log): every organisation reached through the practice is revoked at once (404).

**Last-admin guard**: the practice's last *active* practice admin can't be suspended or removed
(``409 staff.last_admin``) — a practice always keeps someone who can manage it. Each change is
audited in the practice's log.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from numo9.audit.service import record
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.models import PracticeAssignment, PracticeMember, PracticeRole
from numo9.workspace.access import bump
from numo9.workspace.models import GroupStaffAssignment


def _name(member: PracticeMember) -> str:
    return member.user.name or member.user.email


def _guard_last_admin(member: PracticeMember) -> None:
    if member.role != PracticeRole.PRACTICE_ADMIN or member.suspended_at is not None:
        return
    others = (
        PracticeMember.objects.select_for_update()
        .filter(
            practice_id=member.practice_id,
            role=PracticeRole.PRACTICE_ADMIN,
            suspended_at__isnull=True,
        )
        .exclude(pk=member.pk)
    )
    if not others.exists():
        raise api_error(errors.STAFF_LAST_ADMIN, name=_name(member))


def _audit(action: str, member: PracticeMember, by: Any, **meta: Any) -> None:
    record(
        action,
        organisation=None,
        practice=member.practice,
        object_type="accounts.User",
        object_id=str(member.user.public_id),
        object_label=_name(member),
        meta={"role": member.role, **meta},
        actor=by,
    )


def suspend(member: PracticeMember, by: Any = None) -> PracticeMember:
    with transaction.atomic():
        member = (
            PracticeMember.objects.select_for_update()
            .select_related("user", "practice")
            .get(pk=member.pk)
        )
        if member.suspended_at is not None:
            return member
        _guard_last_admin(member)
        member.suspended_at = timezone.now()
        member.save(update_fields=["suspended_at"])
        _audit("staff.member_suspended", member, by)
        bump()
    return member


def reinstate(member: PracticeMember, by: Any = None) -> PracticeMember:
    with transaction.atomic():
        member = (
            PracticeMember.objects.select_for_update()
            .select_related("user", "practice")
            .get(pk=member.pk)
        )
        if member.suspended_at is None:
            raise api_error(errors.STAFF_NOT_SUSPENDED, name=_name(member))
        member.suspended_at = None
        member.save(update_fields=["suspended_at"])
        _audit("staff.member_reinstated", member, by)
        bump()
    return member


def remove(member: PracticeMember, by: Any = None) -> None:
    with transaction.atomic():
        member = (
            PracticeMember.objects.select_for_update()
            .select_related("user", "practice")
            .get(pk=member.pk)
        )
        _guard_last_admin(member)
        direct = PracticeAssignment.objects.filter(
            practice_id=member.practice_id, assigned_staff=member
        )
        organisations = [
            str(a.organisation.public_id) for a in direct.select_related("organisation")
        ]
        for assignment in direct:
            assignment.assigned_staff.remove(member)
        GroupStaffAssignment.objects.filter(practice_member=member).delete()
        _audit("staff.member_removed", member, by, organisations=organisations)
        member.delete()
        bump()
