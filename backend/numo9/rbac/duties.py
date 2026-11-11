"""Segregation of duties (A-03-T08): ``assert_not_creator(user, obj)``.

Where a workflow requires it (bill and purchase-order approval, pay runs, tax filings: "reviewer
≠ preparer"), the person who **created** a record may not also approve it. Callers decide where
the rule applies; this helper only answers "is this user the record's creator?".

- The creator is read from ``obj.<field>_id`` (default ``created_by``, set on every
  ``OrgOwnedModel``, A-01-T02) — no query; pass ``fields=("created_by", "submitted_by")`` to
  check several people fields.
- A record created by a system process (``created_by`` empty: imports, seeders, scheduled jobs)
  has no creator, so anyone may approve it.
- Refusal raises ``SelfApprovalRefused``: a ``403`` API error ``approval.self_approval`` naming
  the record ("You created this bill, so someone else has to approve it.").
- Asking about a field the object does not have is a programming error (``TypeError``).

With approval limits (A-03-T07), pass the creator to ``assert_can_approve(..., exclude=[creator])``
so they are never suggested as the next approver.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from numo9.i18n import errors
from numo9.i18n.errors import CatalogueError


class SelfApprovalRefused(CatalogueError):
    """The approver created the record (segregation of duties)."""

    def __init__(self, record: str, field: str) -> None:
        self.field = field
        super().__init__(errors.SELF_APPROVAL, record=record)
        self.extra = {"field": field}


def _record_name(obj: Any) -> str:
    meta = getattr(obj, "_meta", None)
    name = str(meta.verbose_name) if meta is not None else type(obj).__name__
    return name[:1].lower() + name[1:]


def _creator_id(obj: Any, field: str) -> Any:
    attribute = f"{field}_id"
    if not hasattr(obj, attribute):
        raise TypeError(f"{type(obj).__name__} has no people field {field!r}.")
    return getattr(obj, attribute)


def creators(obj: Any, fields: Sequence[str] = ("created_by",)) -> list[Any]:
    """Primary keys of the people named in ``fields`` (empty ones left out)."""
    return [pk for pk in (_creator_id(obj, f) for f in fields) if pk is not None]


def is_creator(user: Any, obj: Any, fields: Sequence[str] = ("created_by",)) -> bool:
    if user is None or getattr(user, "pk", None) is None:
        return False
    return user.pk in creators(obj, fields)


def assert_not_creator(
    user: Any,
    obj: Any,
    *,
    fields: Sequence[str] = ("created_by",),
    record: str | None = None,
) -> None:
    """Raise ``SelfApprovalRefused`` when ``user`` is named in one of ``fields`` of ``obj``."""
    if isinstance(fields, str):
        fields = (fields,)
    for field in fields:
        if user is not None and getattr(user, "pk", None) is not None:
            if _creator_id(obj, field) == user.pk:
                raise SelfApprovalRefused(record or _record_name(obj), field)
        else:
            _creator_id(obj, field)  # still refuse a field the object does not have
