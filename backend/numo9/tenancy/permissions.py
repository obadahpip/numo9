"""DRF permission for organisation-scoped endpoints (A-01-T06) and the tenancy permissions of the
catalogue (A-03-T01, at the end).

``IsOrgMemberOrAssigned`` lets a request through only when

- the user is authenticated (otherwise DRF's usual 401/403 — the same for every organisation id),
- the request has an active organisation (``TenantContextMiddleware``, A-01-T03), and
- the access resolver allows the user in that organisation (``can_access``, A-01-T05).

Every refusal about *which* organisation or object is a ``404 Not Found``, never ``403``: an
organisation the user may not see, an unknown organisation (middleware) and an object of another
organisation all answer the same, so responses never reveal that something exists.

The object-level check is defence in depth: ``OrgScopedManager`` already limits querysets to the
active organisation, and this check also catches objects loaded any other way.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from numo9.rbac.catalogue import Permission, Risk, Scope, register

from .access import can_access
from .context import current_org
from .models import Organisation


class IsOrgMemberOrAssigned(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        organisation = current_org()
        if organisation is None or not can_access(request.user, organisation):
            raise NotFound
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        organisation = current_org()
        if isinstance(obj, Organisation):
            owner_id = obj.pk
        elif hasattr(obj, "organisation_id"):
            owner_id = obj.organisation_id
        else:
            raise ImproperlyConfigured(
                f"IsOrgMemberOrAssigned used on {type(obj).__name__}, which has no organisation."
            )
        if organisation is None or owner_id != organisation.pk:
            raise NotFound
        return True


# ---- Permission catalogue (A-03-T01): what organisations and practices let people do --------
# Imported by numo9.rbac at start-up; the keys are stable (stored in role permissions).

ORG = Scope.ORGANISATION
PRACTICE = Scope.PRACTICE

ORGANISATION_PROFILE_VIEW = register(
    Permission(
        "organisation.profile.view", _("View the organisation's details"), "settings", Risk.LOW
    )
)
ORGANISATION_SETTINGS_MANAGE = register(
    Permission(
        "organisation.settings.manage", _("Change organisation settings"), "settings", Risk.HIGH
    )
)
ORGANISATION_CLOSE = register(
    Permission(
        "organisation.close",
        _("Close the organisation"),
        "settings",
        Risk.CRITICAL,
        owner_only=True,
    )
)
ORGANISATION_MEMBERS_VIEW = register(
    Permission("organisation.members.view", _("See the organisation's users"), "users", Risk.LOW)
)
ORGANISATION_MEMBERS_INVITE = register(
    Permission(
        "organisation.members.invite", _("Invite users to the organisation"), "users", Risk.HIGH
    )
)
ORGANISATION_MEMBERS_MANAGE = register(
    Permission(
        "organisation.members.manage",
        _("Change or remove the organisation's users"),
        "users",
        Risk.CRITICAL,
    )
)
ORGANISATION_ACCOUNTANT_INVITE = register(
    Permission(
        "organisation.accountant.invite",
        _("Invite an accountant to look after the organisation"),
        "users",
        Risk.HIGH,
    )
)

PRACTICE_PROFILE_VIEW = register(
    Permission("practice.profile.view", _("View the practice"), "practice", Risk.LOW, PRACTICE)
)
PRACTICE_SETTINGS_MANAGE = register(
    Permission(
        "practice.settings.manage", _("Change practice settings"), "practice", Risk.HIGH, PRACTICE
    )
)
PRACTICE_STAFF_VIEW = register(
    Permission("practice.staff.view", _("See the practice's staff"), "practice", Risk.LOW, PRACTICE)
)
PRACTICE_STAFF_INVITE = register(
    Permission(
        "practice.staff.invite", _("Invite staff to the practice"), "practice", Risk.HIGH, PRACTICE
    )
)
PRACTICE_STAFF_MANAGE = register(
    Permission(
        "practice.staff.manage",
        _("Change or remove the practice's staff"),
        "practice",
        Risk.CRITICAL,
        PRACTICE,
    )
)
PRACTICE_CLIENTS_CREATE = register(
    Permission(
        "practice.clients.create",
        _("Create client organisations"),
        "practice",
        Risk.MEDIUM,
        PRACTICE,
    )
)
PRACTICE_CLIENTS_ASSIGN = register(
    Permission(
        "practice.clients.assign",
        _("Assign staff to client organisations"),
        "practice",
        Risk.HIGH,
        PRACTICE,
    )
)
PRACTICE_CLIENTS_INVITE_OWNER = register(
    Permission(
        "practice.clients.invite_owner",
        _("Invite a client organisation's owner"),
        "practice",
        Risk.HIGH,
        PRACTICE,
    )
)
