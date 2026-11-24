"""Approvals inbox (C-04-T08): one list of everything waiting for someone's approval.

Each module that has documents waiting for approval registers an ``Approvable`` in the
``ApprovableRegistry`` (journals now — ``numo9.ledger``; bills, purchase orders and expense claims
register theirs when they arrive). ``GET /api/v1/o/<org>/approvals`` asks every registered
approvable whose permission and feature the person has for its items and merges them, oldest
submission first.

An item says whether **this person** may approve it (``can_approve``) and, when not, why
(``blocked``): ``self`` — they wrote or submitted it (segregation of duties; the item is listed
so they can follow it, "You created this"), ``limit`` — above their approval limit (the limit is
shown, ``limit``), ``no_limit`` — they have no limit for that document type. Items of a type
whose approve permission the person lacks are listed only when they submitted them.
``counts``: ``total`` and ``can_approve`` — the inbox badge is the second.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils.functional import Promise


@dataclass(frozen=True)
class Approvable:
    kind: str
    label: Promise
    #: The permission that lets someone approve this kind (items of others are listed with it).
    permission: str
    feature: str
    #: ``items(user, organisation, may_approve)`` → the item dicts (``item()`` below).
    items: Callable[[Any, Any, bool], list[dict[str, Any]]]


class ApprovableRegistry:
    def __init__(self) -> None:
        self._kinds: dict[str, Approvable] = {}

    def register(self, approvable: Approvable) -> Approvable:
        self._kinds[approvable.kind] = approvable
        return approvable

    def __iter__(self) -> Iterator[Approvable]:
        return iter(sorted(self._kinds.values(), key=lambda a: a.kind))

    def get(self, kind: str) -> Approvable | None:
        return self._kinds.get(kind)


approvables = ApprovableRegistry()


def blocked_reason(
    user: Any, authors: set[int], limit: Decimal | None, amount: Decimal
) -> str | None:
    """Why ``user`` can't approve: ``self``, ``no_limit``, ``limit`` — or ``None``."""
    if getattr(user, "pk", None) in authors:
        return "self"
    if limit is None:
        return "no_limit"
    if amount > limit:
        return "limit"
    return None


def item(
    *,
    kind: str,
    id: str,
    title: str,
    subtitle: str,
    amount: Decimal,
    date: Any,
    url: str,
    submitted_by: Any,
    submitted_at: Any,
    created_by: Any,
    blocked: str | None,
    limit: Decimal | None,
) -> dict[str, Any]:
    def person(user: Any) -> dict[str, str] | None:
        return {"id": str(user.public_id), "name": user.name} if user is not None else None

    return {
        "kind": kind,
        "id": id,
        "title": title,
        "subtitle": subtitle,
        "amount": f"{amount:.2f}",
        "date": date.isoformat() if date else None,
        "url": url,
        "submitted_by": person(submitted_by),
        "submitted_at": submitted_at.isoformat() if submitted_at else None,
        "created_by": person(created_by),
        "can_approve": blocked is None,
        "blocked": blocked,
        "limit": None if limit is None else f"{limit:.2f}",
    }


def inbox(user: Any, organisation: Any, *, has_perm: Callable[[str], bool]) -> dict[str, Any]:
    """The merged inbox of ``user`` (module docstring); ``has_perm(key)`` is their permission
    check in the organisation. Kinds whose feature the package lacks are left out."""
    from numo9.catalogue.entitlements import get_resolver

    resolver = get_resolver()
    results: list[dict[str, Any]] = []
    kinds: list[dict[str, Any]] = []
    for approvable in approvables:
        if not resolver.allows(organisation, approvable.feature):
            continue
        may = has_perm(approvable.permission)
        found = approvable.items(user, organisation, may)
        results.extend(found)
        kinds.append(
            {
                "kind": approvable.kind,
                "label": str(approvable.label),
                "count": len(found),
                "can_approve": sum(1 for i in found if i["can_approve"]),
            }
        )
    results.sort(key=lambda i: (i["submitted_at"] or "", i["id"]))
    return {
        "results": results,
        "kinds": kinds,
        "counts": {
            "total": len(results),
            "can_approve": sum(1 for i in results if i["can_approve"]),
        },
    }
