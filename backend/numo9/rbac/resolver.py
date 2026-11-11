"""Permission resolver (A-03-T04): ``has_perm(user, org, key)``.

A user's permissions **in an organisation** are the union of the organisation-scope
permissions of every role they hold there:

1. **as a member** — the system role of ``OrganisationMember.role``, plus the organisation roles
   given to them in that organisation (``RoleAssignment``, usually custom roles);
2. **through a practice** that is actively assigned to the organisation and gives them access
   (A-01-T05: practice-wide role, or assigned staff) — the system role of their
   ``PracticeMember.role`` plus the practice roles given to them in that practice.

Nothing is granted without access: a user the access resolver refuses has no permissions,
whatever roles they hold. Entitlements (U-03) will intersect this set (feature not in the
package → refused even with the permission).

Practice permissions (``has_practice_perm``) come from the practice membership and practice
roles; platform permissions (``has_platform_perm``) only from platform roles.

**Caching** — within one request only. ``PermissionCacheMiddleware`` opens a cache for each
request, so a view that checks several permissions queries once; nothing is cached across
requests, so a role removed or edited applies to the very next request (like access, A-01-T10).
Outside a cache scope (scripts, jobs) every call reads the database.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from django.db.models import Q
from django.http import HttpRequest, HttpResponse

from numo9.tenancy.access import PRACTICE_WIDE_ROLES, can_access
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)

from .catalogue import Scope, catalogue
from .models import Role, RoleAssignment, RolePermission, RoleScope

_Cache = dict[tuple[str, int, int | None], frozenset[str]]
_cache: ContextVar[_Cache | None] = ContextVar("numo9_permission_cache", default=None)


@contextmanager
def permission_cache() -> Iterator[None]:
    """Cache permission sets for the duration of a block (one request)."""
    token = _cache.set({})
    try:
        yield
    finally:
        _cache.reset(token)


class PermissionCacheMiddleware:
    """One permission cache per request (A-03-T04)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        with permission_cache():
            return self.get_response(request)


def _active(user: Any) -> bool:
    return bool(user is not None and user.is_authenticated and user.is_active)


def _cached(
    kind: str, user: Any, target: int | None, compute: Callable[[], frozenset[str]]
) -> frozenset[str]:
    cache = _cache.get()
    if cache is None:
        return compute()
    key = (kind, user.pk, target)
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def _keys(role_filter: Q, scope: Scope) -> frozenset[str]:
    keys = RolePermission.objects.filter(role__in=Role.objects.filter(role_filter)).values_list(
        "permission", flat=True
    )
    # Only permissions of the asked scope that still exist in the catalogue.
    return frozenset(k for k in keys if k in catalogue and catalogue.get(k).scope == scope)


def _organisation_roles(user: Any, organisation: Organisation) -> Q:
    roles = Q(pk__in=[])
    membership = (
        OrganisationMember.objects.filter(user=user, organisation=organisation)
        .values_list("role", flat=True)
        .first()
    )
    if membership is not None:
        roles |= Q(is_system=True, scope=RoleScope.ORGANISATION, key=membership)
    roles |= Q(
        pk__in=RoleAssignment.objects.filter(user=user, organisation=organisation).values("role")
    )
    # Practices that give the user access to this organisation (same rule as A-01-T05).
    serving = (
        PracticeAssignment.objects.filter(organisation=organisation, active=True)
        .filter(
            Q(practice__members__user=user, practice__members__role__in=PRACTICE_WIDE_ROLES)
            | Q(assigned_staff__user=user)
        )
        .values_list("practice_id", flat=True)
        .distinct()
    )
    practice_ids = list(serving)
    if practice_ids:
        practice_roles = set(
            PracticeMember.objects.filter(user=user, practice_id__in=practice_ids).values_list(
                "role", flat=True
            )
        )
        roles |= Q(is_system=True, scope=RoleScope.PRACTICE, key__in=practice_roles)
        roles |= Q(
            pk__in=RoleAssignment.objects.filter(user=user, practice_id__in=practice_ids).values(
                "role"
            )
        )
    return roles


def organisation_permissions(user: Any, organisation: Organisation) -> frozenset[str]:
    """Every organisation-scope permission the user has in the organisation."""
    if not _active(user):
        return frozenset()

    def compute() -> frozenset[str]:
        if not can_access(user, organisation):
            return frozenset()
        return _keys(_organisation_roles(user, organisation), Scope.ORGANISATION)

    return _cached("org", user, organisation.pk, compute)


def practice_permissions(user: Any, practice: Practice) -> frozenset[str]:
    """Every practice-scope permission the user has in the practice (members only)."""
    if not _active(user):
        return frozenset()

    def compute() -> frozenset[str]:
        role = (
            PracticeMember.objects.filter(user=user, practice=practice)
            .values_list("role", flat=True)
            .first()
        )
        if role is None:
            return frozenset()
        roles = Q(is_system=True, scope=RoleScope.PRACTICE, key=role) | Q(
            pk__in=RoleAssignment.objects.filter(user=user, practice=practice).values("role")
        )
        return _keys(roles, Scope.PRACTICE)

    return _cached("practice", user, practice.pk, compute)


def platform_permissions(user: Any) -> frozenset[str]:
    """Every platform permission (Numo9 staff roles) the user holds."""
    if not _active(user):
        return frozenset()

    def compute() -> frozenset[str]:
        roles = Q(
            pk__in=RoleAssignment.objects.filter(
                user=user,
                organisation__isnull=True,
                practice__isnull=True,
                role__scope=RoleScope.PLATFORM,
            ).values("role")
        )
        return _keys(roles, Scope.PLATFORM)

    return _cached("platform", user, None, compute)


def _check(key: str, scope: Scope) -> None:
    permission = catalogue.get(key)  # UnknownPermission for a typo
    if permission.scope != scope:
        raise ValueError(
            f"{key!r} is a {permission.scope.value} permission; check it with the "
            f"{permission.scope.value} resolver."
        )


def has_perm(user: Any, organisation: Organisation, key: str) -> bool:
    """Whether the user may do ``key`` (an organisation permission) in the organisation."""
    _check(key, Scope.ORGANISATION)
    return key in organisation_permissions(user, organisation)


def has_practice_perm(user: Any, practice: Practice, key: str) -> bool:
    _check(key, Scope.PRACTICE)
    return key in practice_permissions(user, practice)


def has_platform_perm(user: Any, key: str) -> bool:
    _check(key, Scope.PLATFORM)
    return key in platform_permissions(user)
