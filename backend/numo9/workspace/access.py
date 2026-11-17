"""Access through practice groups (V-02-T05): direct ∪ group ∪ ancestor groups.

A practice member assigned to a group (``GroupStaffAssignment``) may access every organisation
filed in that group **or any of its descendants** (an assignment to "Toronto office" covers
"Toronto office → Retail clients"), as long as the group's practice still actively serves the
organisation. Registered with the A-01 resolver (``tenancy.access.register_access_source``), so
``accessible_organisations`` and ``can_access`` — every organisation-scoped request — include it.

``group_organisation_ids(user)`` is one query (materialised paths: "path starts with an assigned
group's path") and is **cached per user**: key ``access:groups:<user id>:<generation>``. The
generation is a counter bumped on any change that could change the answer — groups (moves change
paths), memberships, staff assignments, practice assignments and practice members (signals,
at once and again at commit) — so a revocation is effective on the next request (V-02-T06).
"""

from __future__ import annotations

from functools import reduce
from operator import or_
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models.signals import post_delete, post_save

from numo9.tenancy.models import PracticeAssignment, PracticeMember

from .models import GroupStaffAssignment, OrgGroup, OrgGroupMembership

GENERATION_KEY = "access:groups:gen"
TTL = 60 * 60


def _generation() -> int:
    cache.add(GENERATION_KEY, 1, timeout=None)
    value = cache.get(GENERATION_KEY)
    return int(value) if value is not None else 1


def bump() -> None:
    """Invalidate every user's cached group access (now and when the transaction commits)."""

    def _bump() -> None:
        try:
            cache.incr(GENERATION_KEY)
        except ValueError:
            cache.set(GENERATION_KEY, _generation() + 1, timeout=None)

    _bump()
    transaction.on_commit(_bump)


def _resolve(user: Any) -> frozenset[int]:
    assigned = list(
        GroupStaffAssignment.objects.filter(practice_member__user=user).values_list(
            "group__path", "group__practice_id"
        )
    )
    if not assigned:
        return frozenset()
    covered = reduce(
        or_,
        (
            Q(group__path__startswith=path, group__practice_id=practice)
            for path, practice in assigned
        ),
    )
    served = PracticeAssignment.objects.filter(
        practice_id=OuterRef("group__practice_id"),
        organisation_id=OuterRef("organisation_id"),
        active=True,
    )
    ids = (
        OrgGroupMembership.objects.filter(covered)
        .filter(Exists(served))
        .values_list("organisation_id", flat=True)
        .distinct()
    )
    return frozenset(int(pk) for pk in ids)


def group_organisation_ids(user: Any) -> frozenset[int]:
    """Organisations the user reaches through groups (cached per user, see the docstring)."""
    if user is None or not getattr(user, "is_authenticated", False) or not user.is_active:
        return frozenset()
    key = f"access:groups:{user.pk}:{_generation()}"
    stored = cache.get(key)
    if stored is not None:
        return frozenset(stored)
    answer = _resolve(user)
    cache.set(key, sorted(answer), timeout=TTL)
    return answer


def _changed(sender: Any, **kwargs: Any) -> None:
    if not kwargs.get("raw"):
        bump()


WATCHED = (OrgGroup, OrgGroupMembership, GroupStaffAssignment, PracticeAssignment, PracticeMember)


def connect() -> None:
    from numo9.tenancy.access import register_access_source

    register_access_source(group_organisation_ids)
    for model in WATCHED:
        uid = f"numo9.workspace.access.{model.__name__}"
        post_save.connect(_changed, sender=model, dispatch_uid=f"{uid}.save")
        post_delete.connect(_changed, sender=model, dispatch_uid=f"{uid}.delete")
