"""Audit hooks for role, assignment, approval-limit and access-request changes (A-03-T15).

Every change made through ``services.py`` / ``access.py`` emits one ``RbacChange``: who did it
(the actor), what (``action``), which record (type, public id, label), in which organisation,
and the **diff** — ``{field: [before, after]}``, only for fields that changed (permission sets as
sorted key lists, so added/removed keys are visible).

Delivery: the ``rbac_changed`` signal and a structured log line on ``numo9.audit``. The audit
log itself (``AuditEvent`` table, hash chain, viewer — A-04) does not exist yet; A-04-T03 connects
its ``record()`` to ``rbac_changed`` so these events land in the log with their diff. Until
then the log line is the record.

Actions: ``role.created`` · ``role.updated`` · ``role.deleted`` · ``role.assigned`` ·
``role.unassigned`` · ``member.main_role_changed`` · ``limit.created`` · ``limit.updated`` ·
``limit.deleted`` · ``access_request.created`` · ``access_request.closed``.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from django.dispatch import Signal

logger = logging.getLogger("numo9.audit")

#: Sent with ``change=RbacChange`` after every role / limit / access-request change.
rbac_changed = Signal()

ACTIONS = frozenset(
    {
        "role.created",
        "role.updated",
        "role.deleted",
        "role.assigned",
        "role.unassigned",
        "member.main_role_changed",
        "limit.created",
        "limit.updated",
        "limit.deleted",
        "access_request.created",
        "access_request.closed",
    }
)


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, set | frozenset | tuple | list):
        return sorted(str(v) for v in value)
    if value is None or isinstance(value, bool | int | str):
        return value
    return str(value)


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """``{field: [before, after]}`` for every field whose value changed."""
    changes: dict[str, list[Any]] = {}
    for name in sorted(set(before) | set(after)):
        old, new = _plain(before.get(name)), _plain(after.get(name))
        if old != new:
            changes[name] = [old, new]
    return changes


@dataclass(frozen=True)
class RbacChange:
    action: str
    organisation_id: str | None
    actor_id: str | None
    object_type: str
    object_id: str
    object_label: str
    changes: dict[str, list[Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def record(
    action: str,
    *,
    actor: Any,
    organisation: Any,
    obj: Any,
    label: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> RbacChange:
    """Emit one change (signal + ``numo9.audit`` log line) and return it."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown audit action {action!r}.")
    change = RbacChange(
        action=action,
        organisation_id=str(organisation.public_id) if organisation is not None else None,
        actor_id=str(actor.public_id) if getattr(actor, "public_id", None) else None,
        object_type=obj._meta.label,
        object_id=str(obj.public_id),
        object_label=label,
        changes=diff(before or {}, after or {}),
    )
    rbac_changed.send(sender=RbacChange, change=change)
    logger.info("rbac change %s", action, extra={"audit": change.as_dict()})
    return change


def role_state(role: Any) -> dict[str, Any]:
    return {
        "name": role.name,
        "description": role.description,
        "permissions": sorted(role.permission_keys()),
    }


def limit_state(row: Any) -> dict[str, Any]:
    return {
        "doc_type": row.doc_type,
        "max_amount": row.max_amount,
        "user": str(row.user.public_id) if row.user_id else None,
        "role": str(row.role.public_id) if row.role_id else None,
    }
