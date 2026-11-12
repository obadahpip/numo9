"""Changes announced by other apps, stored in the audit log (A-04-T03).

- ``rbac_changed`` (A-03-T15) — role, role assignment, approval limit and access request changes
  with their diff, in the organisation (or the practice, for practice roles).
"""

from __future__ import annotations

from typing import Any

from numo9.accounts.models import User
from numo9.tenancy.models import Organisation, Practice

from .service import record


def store_rbac_change(sender: Any, change: Any, **kwargs: Any) -> None:
    organisation = (
        Organisation.objects.filter(public_id=change.organisation_id).first()
        if change.organisation_id
        else None
    )
    practice = (
        Practice.objects.filter(public_id=change.practice_id).first()
        if change.practice_id
        else None
    )
    actor = User.objects.filter(public_id=change.actor_id).first() if change.actor_id else None
    record(
        change.action,
        organisation=organisation,
        practice=practice,
        object_type=change.object_type,
        object_id=change.object_id,
        object_label=change.object_label,
        changes=change.changes,
        actor=actor,
    )
