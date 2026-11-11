"""Permission catalogue (A-03-T01).

Every permission Numo9 checks is declared in code, in the ``permissions.py`` module of the app
that owns it, and registered here. The catalogue is the single source for

- the API permission checks (``RequiresPermission``, A-03-T05) — an unknown key is an error;
- the system roles' default permission sets (A-03-T03) and custom-role editing (A-03-T09/T12);
- the exported catalogue (``manage.py permcat_export``) and its docs page (A-03-T16).

A permission has

- ``key`` — stable dotted identifier, ``<area>.<thing>.<action>`` (``organisation.members.invite``);
  never renamed once released (stored in ``RolePermission``);
- ``label`` — a gettext message (the translation key) people read in the role editor;
- ``module`` — the product area it belongs to, for grouping (``MODULES``);
- ``risk`` — ``low`` / ``medium`` / ``high`` / ``critical``: what misuse could do (risk badges in
  the role editor, extra care when granting);
- ``scope`` — where it is checked: ``organisation`` (in one organisation: org roles and the roles
  of a practice that serves it), ``practice`` (in one practice) or ``platform`` (Numo9 staff).

    # numo9/<app>/permissions.py
    from numo9.rbac.catalogue import Permission, Risk, Scope, register

    CONTACTS_VIEW = register(
        Permission("contacts.contact.view", _("View contacts"), "contacts", Risk.LOW)
    )
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from django.utils.functional import Promise

KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$")

#: Product areas, in navigation order (Phase 0 plan §3.1 UX principle 2), plus practice and
#: platform. A module is added here when its first permission is declared.
MODULES: tuple[str, ...] = (
    "home",
    "sales",
    "purchases",
    "banking",
    "accounting",
    "tax",
    "payroll",
    "hr",
    "inventory",
    "reports",
    "contacts",
    "documents",
    "settings",
    "users",
    "practice",
    "platform",
)


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Scope(StrEnum):
    ORGANISATION = "organisation"
    PRACTICE = "practice"
    PLATFORM = "platform"


#: Actions that only read: what read-only roles get.
READ_ACTIONS: frozenset[str] = frozenset({"view", "export"})


@dataclass(frozen=True)
class Permission:
    key: str
    label: Promise | str
    module: str
    risk: Risk
    scope: Scope = Scope.ORGANISATION
    #: Who should not get it by default even in broad roles, e.g. closing the organisation.
    owner_only: bool = False

    @property
    def action(self) -> str:
        """Last part of the key: ``view``, ``create``, ``approve``…"""
        return self.key.rsplit(".", 1)[-1]

    @property
    def read_only(self) -> bool:
        return self.action in READ_ACTIONS


class CatalogueError(ValueError):
    """A permission is declared wrongly (bad key, unknown module, declared twice)."""


class UnknownPermission(KeyError):
    """A permission key that is not in the catalogue (a typo or a missing declaration)."""


class PermissionRegistry:
    def __init__(self) -> None:
        self._permissions: dict[str, Permission] = {}

    def register(self, permission: Permission) -> Permission:
        if not KEY.match(permission.key):
            raise CatalogueError(
                f"Permission key {permission.key!r} must be dotted lower-case, 2–4 parts, "
                "e.g. 'organisation.members.invite'."
            )
        if permission.module not in MODULES:
            raise CatalogueError(
                f"Permission {permission.key!r}: unknown module {permission.module!r}; "
                f"add it to numo9.rbac.catalogue.MODULES."
            )
        if not isinstance(permission.risk, Risk) or not isinstance(permission.scope, Scope):
            raise CatalogueError(f"Permission {permission.key!r}: risk/scope must be Risk/Scope.")
        if permission.key in self._permissions:
            raise CatalogueError(f"Permission {permission.key!r} is declared twice.")
        self._permissions[permission.key] = permission
        return permission

    def unregister(self, key: str) -> None:
        """Tests only: remove a permission registered by a test."""
        self._permissions.pop(key, None)

    def get(self, key: str) -> Permission:
        try:
            return self._permissions[key]
        except KeyError:
            raise UnknownPermission(key) from None

    def __contains__(self, key: object) -> bool:
        return key in self._permissions

    def __iter__(self) -> Iterator[Permission]:
        """Permissions grouped by module (``MODULES`` order), then by key."""
        order = {module: index for index, module in enumerate(MODULES)}
        return iter(sorted(self._permissions.values(), key=lambda p: (order[p.module], p.key)))

    def __len__(self) -> int:
        return len(self._permissions)

    def keys(self) -> frozenset[str]:
        return frozenset(self._permissions)

    def in_scope(self, scope: Scope) -> list[Permission]:
        return [p for p in self if p.scope == scope]


#: The catalogue. Filled when the apps load (``RbacConfig.ready`` imports every installed app's
#: ``permissions`` module).
catalogue = PermissionRegistry()


def register(permission: Permission) -> Permission:
    """Declare a permission (in an app's ``permissions.py``); returns it for use as a constant."""
    return catalogue.register(permission)
