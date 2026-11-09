"""Organisation access resolver (A-01-T05).

A user may access an organisation when the user is active and

1. is a member of the organisation (any organisation role), **or**
2. is a member of a practice that is **actively** assigned to the organisation, and either
   - holds a practice-wide role in that practice (``PRACTICE_WIDE_ROLES``: practice admins see
     every organisation their practice serves), or
   - is one of the assignment's assigned staff.
   (Assignment through organisation groups is added with V-02-T04.)

Nothing else grants access: Django superusers and platform staff reach organisations only
through audited impersonation (U-06). Results are never cached, so removing a membership,
staff assignment or practice assignment takes effect on the next request (A-01-T10).

``accessible_organisations(user)`` and ``can_access(user, org)`` share one query, so the
organisation list a user sees and the access check can never disagree.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from .models import (
    Organisation,
    OrganisationMember,
    PracticeAssignment,
    PracticeRole,
)

PRACTICE_WIDE_ROLES: frozenset[str] = frozenset({PracticeRole.PRACTICE_ADMIN})


def accessible_organisations(user: Any) -> QuerySet[Organisation]:
    """Every organisation the user may access (empty for anonymous or inactive users)."""
    if user is None or not user.is_authenticated or not user.is_active:
        return Organisation.objects.none()
    as_member = OrganisationMember.objects.filter(user=user).values("organisation_id")
    via_practice = (
        PracticeAssignment.objects.filter(active=True)
        .filter(
            Q(practice__members__user=user, practice__members__role__in=PRACTICE_WIDE_ROLES)
            | Q(assigned_staff__user=user)
        )
        .values("organisation_id")
    )
    return Organisation.objects.filter(Q(pk__in=as_member) | Q(pk__in=via_practice))


def can_access(user: Any, organisation: Organisation) -> bool:
    """Whether the user may access the organisation (always evaluated against the database)."""
    return accessible_organisations(user).filter(pk=organisation.pk).exists()
