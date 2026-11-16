"""Masked values and "Reveal" (S-03-T05).

Sensitive values (SIN, bank account numbers — ``EncryptedField``, S-03-T04) are never sent in
full by the API: ``MaskedValueField`` serialises them as

    {"masked": "•••• 1234", "has_value": true, "reveal": {"record_type": "payroll.Employee",
     "record_id": "<uuid>", "field": "sin"}}

and the full value is fetched only with ``POST /api/v1/o/<org>/reveal`` (``reveal_api``), which
requires

1. the permission ``security.sensitive.reveal``  (else 403);
2. a **fresh password confirmation** — allauth's re-authentication within the last 5 minutes
   (``POST /_allauth/browser/v1/auth/reauthenticate``), else ``401
   security.reauthentication_required`` with the ``reauthenticate`` flow;
3. a field declared revealable (``register_revealable``) on a record of the active organisation
   (else 404);

and writes an audit event ``security.value.revealed`` naming the record and the field — never the
value. Masks keep the last ``keep`` characters (4 by default; a value of 4 or fewer characters is
fully hidden).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rest_framework import serializers

MASK = "••••"


def mask(value: Any, keep: int = 4) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    digits = "".join(ch for ch in text if not ch.isspace())
    if len(digits) <= keep:
        return MASK
    return f"{MASK} {digits[-keep:]}"


@dataclass(frozen=True)
class Revealable:
    model: str  # app label.Model
    field: str
    keep: int = 4


_revealable: dict[tuple[str, str], Revealable] = {}


def register_revealable(model: str, field: str, keep: int = 4) -> Revealable:
    entry = Revealable(model, field, keep)
    _revealable[(model, field)] = entry
    return entry


def revealable(model: str, field: str) -> Revealable | None:
    return _revealable.get((model, field))


class MaskedValueField(serializers.Field):  # type: ignore[type-arg]
    """Read-only: the masked form of a sensitive field and how to reveal it."""

    def __init__(self, *, keep: int = 4, **kwargs: Any) -> None:
        kwargs["read_only"] = True
        kwargs.setdefault("source", "*")
        self.keep = keep
        super().__init__(**kwargs)

    def bind(self, field_name: str, parent: Any) -> None:
        super().bind(field_name, parent)
        self.model_field = field_name

    def to_representation(self, obj: Any) -> dict[str, Any]:
        value = getattr(obj, self.model_field, None)
        label = obj._meta.label
        reveal = (
            {"record_type": label, "record_id": str(obj.public_id), "field": self.model_field}
            if value and revealable(label, self.model_field)
            else None
        )
        return {"masked": mask(value, self.keep), "has_value": bool(value), "reveal": reveal}
