"""How an audit event reads: labels for actions, record types and fields (A-04-T07).

One shape for the viewer, the record history drawer and the exports. Labels are translated into
the request's language (backend gettext catalogues); the raw keys stay alongside them so clients
can filter and link.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils.functional import Promise
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from .batch import SUMMARY_ACTION, SUMMARY_TYPE
from .models import AuditEvent

#: Longest text value shown in a list row; the event's detail shows it whole.
LIST_VALUE_CHARS = 200

VERB_LABELS: dict[str, Promise] = {
    "created": _("Created"),
    "updated": _("Edited"),
    "deleted": _("Deleted"),
    "restored": _("Restored"),
}

ACTION_LABELS: dict[str, Promise] = {
    SUMMARY_ACTION: _("Bulk operation"),
    "audit.log.exported": _("Audit log exported"),
    "auth.login.succeeded": _("Signed in"),
    "auth.login.failed": _("Sign-in failed"),
    "auth.login.locked": _("Sign-in refused: account locked"),
    "auth.logout": _("Signed out"),
    "auth.2fa.failed": _("Two-step verification failed"),
    "auth.2fa.enabled": _("Two-step verification turned on"),
    "auth.2fa.disabled": _("Two-step verification turned off"),
    "auth.recovery_codes.created": _("Recovery codes created"),
    "auth.recovery_codes.regenerated": _("Recovery codes replaced"),
    "auth.recovery_codes.removed": _("Recovery codes removed"),
    "tenancy.invitation.created": _("Invitation sent"),
    "tenancy.invitation.resent": _("Invitation sent again"),
    "tenancy.invitation.revoked": _("Invitation cancelled"),
    "tenancy.invitation.accepted": _("Invitation accepted"),
    "role.created": _("Role created"),
    "role.updated": _("Role edited"),
    "role.deleted": _("Role deleted"),
    "role.assigned": _("Role given"),
    "role.unassigned": _("Role removed"),
    "member.main_role_changed": _("Main role changed"),
    "limit.created": _("Approval limit set"),
    "limit.updated": _("Approval limit changed"),
    "limit.deleted": _("Approval limit removed"),
    "access_request.created": _("Access requested"),
    "access_request.closed": _("Access request closed"),
    "ledger.account.renumbered": _("Account renumbered"),
    "files.document.quarantined": _("File quarantined: a virus was found"),
    "files.document.duplicate_received": _("Same file received again"),
    "files.document.downloaded": _("File opened"),
    "files.inbound.processed": _("Email received"),
}

TYPE_LABELS: dict[str, Promise] = {
    SUMMARY_TYPE: _("Bulk operation"),
    "audit.Log": _("Audit log"),
    "accounts.User": _("User"),
}


def _model(object_type: str) -> type[models.Model] | None:
    try:
        return apps.get_model(object_type)
    except (LookupError, ValueError):
        return None


def _humanise(key: str) -> str:
    return capfirst(key.replace("_", " ").replace(".", " ").strip()) or key


def action_label(action: str) -> str:
    if action in ACTION_LABELS:
        return str(ACTION_LABELS[action])
    verb = action.rsplit(".", 1)[-1]
    if verb in VERB_LABELS:
        return str(VERB_LABELS[verb])
    return _humanise(verb)


def action_verb(action: str) -> str:
    verb = action.rsplit(".", 1)[-1]
    return verb if verb in VERB_LABELS else "other"


def type_label(object_type: str) -> str:
    if not object_type:
        return ""
    if object_type in TYPE_LABELS:
        return str(TYPE_LABELS[object_type])
    model = _model(object_type)
    if model is not None:
        return str(capfirst(model._meta.verbose_name))
    return _humanise(object_type.rsplit(".", 1)[-1])


def field_label(object_type: str, name: str) -> str:
    model = _model(object_type)
    if model is not None:
        try:
            return str(capfirst(model._meta.get_field(name).verbose_name))  # type: ignore[union-attr]
        except (FieldDoesNotExist, AttributeError):
            pass
    return _humanise(name)


def _shorten(value: Any) -> Any:
    if isinstance(value, str) and len(value) > LIST_VALUE_CHARS:
        return {"truncated": True, "text": value[:LIST_VALUE_CHARS], "length": len(value)}
    if isinstance(value, dict) and value.get("truncated"):
        text = str(value.get("text", ""))[:LIST_VALUE_CHARS]
        return {"truncated": True, "text": text, "length": value.get("length", len(text))}
    return value


def changes_data(event: AuditEvent, *, full: bool) -> list[dict[str, Any]]:
    rows = []
    for name, pair in sorted((event.changes or {}).items()):
        old, new = (pair + [None, None])[:2] if isinstance(pair, list) else (None, pair)
        if not full:
            old, new = _shorten(old), _shorten(new)
        masked = isinstance(old, dict) and old.get("masked") is True
        rows.append(
            {
                "field": name,
                "label": field_label(event.object_type, name),
                "old": old,
                "new": new,
                "masked": masked,
            }
        )
    return rows


def _person(user: Any) -> dict[str, str] | None:
    if user is None:
        return None
    return {"id": str(user.public_id), "name": user.name, "email": user.email}


def event_data(event: AuditEvent, *, full: bool = False) -> dict[str, Any]:
    """An event as the API returns it (``full``: whole values, for the event's detail)."""
    data: dict[str, Any] = {
        "id": str(event.public_id),
        "at": event.created_at.isoformat(),
        "action": event.action,
        "action_label": action_label(event.action),
        "verb": action_verb(event.action),
        "actor": {
            "kind": event.actor_kind,
            "label": event.actor_label,
            "user": _person(event.actor_user) if event.actor_user_id else None,
            "impersonator": _person(event.impersonator) if event.impersonator_id else None,
        },
        "record": {
            "type": event.object_type,
            "type_label": type_label(event.object_type),
            "id": event.object_id,
            "label": event.object_label,
        },
        "changes": changes_data(event, full=full),
        "ip": event.ip,
        "device": event.user_agent,
        "request_id": event.request_id,
        "batch_id": str(event.batch_id) if event.batch_id else None,
        "is_batch_summary": event.action == SUMMARY_ACTION,
    }
    data["meta"] = event.meta
    if full:
        data["hash"] = event.hash
        data["prev_hash"] = event.prev_hash
    return data
