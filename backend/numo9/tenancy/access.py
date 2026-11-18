"""Organisation access resolver (A-01-T05).

A user may access an organisation when the user is active and

1. is a member of the organisation (any organisation role), **or**
2. is a member of a practice that is **actively** assigned to the organisation, and either
   - holds a practice-wide role in that practice (``PRACTICE_WIDE_ROLES``: practice admins see
     every organisation their practice serves), or
   - is one of the assignment's assigned staff, **or**
   - is assigned to a practice group (V-02) that holds the organisation — the group itself or
     one of its ancestors: an assignment to "Toronto office" covers "Toronto office → Retail
     clients" and every organisation filed there, including ones added later.

The group part is an *access source* registered by the workspace app
(``register_access_source``): it answers the organisation ids a user reaches through groups, from
a per-user cache that every change to groups, memberships, staff assignments, practice
assignments and practice memberships invalidates (V-02-T05/T06).

Nothing else grants access: Django superusers and platform staff reach organisations only
through audited impersonation (U-06). Direct access is never cached, and the group cache is
invalidated on every change, so removing a membership, staff assignment, group assignment or
practice assignment takes effect on the next request (A-01-T10).

``accessible_organisations(user)`` and ``can_access(user, org)`` share one query, so the
organisation list a user sees and the access check can never disagree.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from django.db.models import Q, QuerySet

from .models import (
    Organisation,
    OrganisationMember,
    PracticeAssignment,
    PracticeRole,
)

PRACTICE_WIDE_ROLES: frozenset[str] = frozenset({PracticeRole.PRACTICE_ADMIN})

#: ``source(user) -> iterable of organisation ids`` reached another way (practice groups, V-02).
AccessSource = Callable[[Any], Iterable[int]]
_sources: list[AccessSource] = []


def register_access_source(source: AccessSource) -> AccessSource:
    if source not in _sources:
        _sources.append(source)
    return source


def unregister_access_source(source: AccessSource) -> None:
    if source in _sources:
        _sources.remove(source)


def accessible_organisations(user: Any) -> QuerySet[Organisation]:
    """Every organisation the user may access (empty for anonymous or inactive users)."""
    if user is None or not user.is_authenticated or not user.is_active:
        return Organisation.objects.none()
    as_member = OrganisationMember.objects.filter(user=user).values("organisation_id")
    via_practice = (
        PracticeAssignment.objects.filter(active=True)
        .filter(
            Q(
                practice__members__user=user,
                practice__members__role__in=PRACTICE_WIDE_ROLES,
                practice__members__suspended_at__isnull=True,  # V-05-T05: suspended → nothing
            )
            | Q(assigned_staff__user=user, assigned_staff__suspended_at__isnull=True)
        )
        .values("organisation_id")
    )
    reached = Q(pk__in=as_member) | Q(pk__in=via_practice)
    extra = {int(pk) for source in _sources for pk in source(user)}
    if extra:
        reached |= Q(pk__in=extra)
    return Organisation.objects.filter(reached)


def can_access(user: Any, organisation: Organisation) -> bool:
    """Whether the user may access the organisation (always evaluated against the database)."""
    return accessible_organisations(user).filter(pk=organisation.pk).exists()
