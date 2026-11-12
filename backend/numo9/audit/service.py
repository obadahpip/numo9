"""The audit service: ``record()`` writes one audit event (A-04-T03).

Everything that changes a business record writes its event through ``record()`` — directly for
named events (a sign-in, an invitation, a role change) or through ``AuditedModel``
(``mixins.py``), which captures the field diff of every save of a model.

    record(
        "tenancy.invitation.revoked",
        obj=invitation,                       # type, public id and label of the record
        organisation=invitation.organisation, # default: obj.organisation, else the active one
        changes={"status": ["pending", "revoked"]},
        actor=user,                           # default: the request's or job's actor (A-04-T04)
    )

Values in ``changes`` are stored as JSON the way people read them: decimals as exact strings
(``"1234.50"``), dates and times in ISO 8601, UUIDs as text, related records as
``{"id": <public id>, "label": <name>}``. **Masked fields** (``masked_value``) are stored as
``{"masked": true}`` on both sides — the log says the field changed, never what it was or became:
SIN and bank details, every ``EncryptedField``, passwords, secrets and tokens. Text longer than
``MAX_VALUE_CHARS`` is cut and marked (``{"truncated": true, "text": …, "length": n}``).

The event is written in the caller's transaction: if the change rolls back, so does its event.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Mapping
from decimal import Decimal
from enum import Enum
from typing import Any

from django.db import models
from django.utils import timezone

from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation, Practice

from .context import current_actor, user_label
from .models import ActorKind, AuditEvent

#: Stored in place of a masked field's old and new value.
MASKED: dict[str, bool] = {"masked": True}
#: Longest text value kept whole in ``changes``.
MAX_VALUE_CHARS = 10_000
#: Field names always masked, whatever their type (exact names or name parts).
MASKED_NAMES: frozenset[str] = frozenset(
    {
        "sin",
        "social_insurance_number",
        "password",
        "secret",
        "token",
        "token_hash",
        "bank_account",
        "bank_account_number",
        "institution_number",
        "transit_number",
        "account_number",
        "routing_number",
        "iban",
        "card_number",
    }
)
_MASKED_PARTS: tuple[str, ...] = ("password", "secret", "token")

_UNSET: Any = object()


def is_masked_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in MASKED_NAMES or any(part in lowered for part in _MASKED_PARTS)


def is_masked_field(field: models.Field[Any, Any], extra: frozenset[str] = frozenset()) -> bool:
    """SIN/bank/secret fields: by name, by the model's ``audit_masked`` or as encrypted fields."""
    from numo9.security.fields import EncryptedField

    return field.name in extra or is_masked_name(field.name) or isinstance(field, EncryptedField)


def plain(value: Any) -> Any:
    """A value as JSON people can read (see the module docstring)."""
    if value is None or isinstance(value, bool | int | str):
        if isinstance(value, str) and len(value) > MAX_VALUE_CHARS:
            return {"truncated": True, "text": value[:MAX_VALUE_CHARS], "length": len(value)}
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return plain(value.value)
    if isinstance(value, models.Model):
        return reference(value)
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [plain(v) for v in value]
    if isinstance(value, set | frozenset):
        return sorted((plain(v) for v in value), key=str)
    return plain(str(value))


def reference(obj: models.Model) -> dict[str, Any]:
    """A related record as ``{"id", "label"}`` — its public id when it has one."""
    public_id = getattr(obj, "public_id", None)
    return {"id": str(public_id if public_id is not None else obj.pk), "label": label_of(obj)}


def label_of(obj: models.Model) -> str:
    audit_label = getattr(obj, "audit_label", None)
    text = audit_label() if callable(audit_label) else str(obj)
    return str(text)[:300]


def object_id_of(obj: models.Model) -> str:
    public_id = getattr(obj, "public_id", None)
    return str(public_id if public_id is not None else obj.pk)[:64]


def diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, list[Any]]:
    """``{field: [old, new]}`` for every field whose value changed (values made ``plain``)."""
    changes: dict[str, list[Any]] = {}
    for name in sorted(set(before) | set(after)):
        old, new = plain(before.get(name)), plain(after.get(name))
        if old != new:
            changes[name] = [old, new]
    return changes


def clean_changes(changes: Mapping[str, Any] | None) -> dict[str, list[Any]]:
    """Validate ``{field: [old, new]}`` and mask fields that must never be stored in clear."""
    cleaned: dict[str, list[Any]] = {}
    for name, pair in (changes or {}).items():
        if not isinstance(pair, list | tuple) or len(pair) != 2:
            raise ValueError(f"changes[{name!r}] must be [old, new].")
        if is_masked_name(str(name)) and pair[0] != MASKED:
            cleaned[str(name)] = [dict(MASKED), dict(MASKED)]
        else:
            cleaned[str(name)] = [plain(pair[0]), plain(pair[1])]
    return cleaned


def record(
    action: str,
    *,
    obj: models.Model | None = None,
    organisation: Organisation | None = _UNSET,
    practice: Practice | None = None,
    object_type: str = "",
    object_id: str = "",
    object_label: str = "",
    changes: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    actor: Any = None,
    actor_label: str = "",
    ip: str | None = None,
    user_agent: str = "",
) -> AuditEvent:
    """Write one audit event in the caller's transaction and return it."""
    if not action or len(action) > 100:
        raise ValueError("An audit action is 1–100 characters, e.g. 'contacts.contact.updated'.")
    if organisation is _UNSET:
        organisation = getattr(obj, "organisation", None) if obj is not None else None
        if organisation is None and not (obj is not None and hasattr(obj, "organisation_id")):
            organisation = current_org()
    if (
        practice is None
        and obj is not None
        and isinstance(getattr(obj, "practice", None), Practice)
    ):
        practice = obj.practice  # type: ignore[attr-defined]
    if obj is not None:
        object_type = object_type or obj._meta.label
        object_id = object_id or object_id_of(obj)
        object_label = object_label or label_of(obj)
    context = current_actor()
    user = actor if getattr(actor, "is_authenticated", False) else None
    kind: str
    if user is not None:
        kind, impersonator, label = ActorKind.USER.value, None, user_label(user)
        if context.user is not None and context.user.pk == user.pk:
            kind, impersonator, label = context.kind, context.impersonator, context.label
    else:
        user, kind, impersonator, label = (
            context.user,
            context.kind,
            context.impersonator,
            context.label,
        )
    event: AuditEvent = AuditEvent.platform_events.create(
        created_at=timezone.now(),
        organisation=organisation,
        practice=practice,
        actor_kind=kind,
        actor_user=user,
        impersonator=impersonator,
        actor_label=(actor_label or label)[:300],
        action=action,
        object_type=object_type[:100],
        object_id=str(object_id)[:64],
        object_label=str(object_label)[:300],
        changes=clean_changes(changes),
        meta=plain({**context.meta, **dict(meta or {})}),
        ip=ip or context.ip,
        user_agent=(user_agent or context.user_agent)[:512],
        request_id=context.request_id[:64],
    )
    return event
