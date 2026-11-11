"""The 15 system roles and their default permission sets (A-03-T03).

System roles are defined here, in code, and seeded by migration ``0002_seed_system_roles``. Their
permission sets are **rules over the catalogue**, not fixed lists: when an app declares new
permissions (contacts with B-01, journals with C-02, …) every system role gets the ones its rule
selects — ``sync_system_roles()`` runs after every ``migrate`` (``post_migrate``) and from
``manage.py sync_system_roles``. System roles are not editable, so the sync keeps each role's set
exactly equal to its rule. Organisations that want something else create a custom role.

The role keys are the membership roles of A-01: ``PracticeMember.role`` and
``OrganisationMember.role`` name the system role a membership carries.

The roles and what each rule grants are listed in ``docs/architecture/permissions.md``
§ System roles; ``SYSTEM_ROLES`` below is the source.

Every organisation role and practice role also gets ``organisation.profile.view``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from django.utils import translation
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from .catalogue import Permission, PermissionRegistry, Risk, Scope, catalogue

Rule = Callable[[Permission], bool]

PROFILE_VIEW = "organisation.profile.view"


@dataclass(frozen=True)
class SystemRole:
    scope: Scope
    key: str
    name: Promise
    description: Promise
    rule: Rule

    def permission_keys(self, registry: PermissionRegistry = catalogue) -> frozenset[str]:
        keys = {p.key for p in registry if self.rule(p)}
        # Never more than the role's scope may grant (models.GRANTABLE_SCOPES).
        allowed = {
            Scope.PLATFORM: {Scope.PLATFORM},
            Scope.PRACTICE: {Scope.PRACTICE, Scope.ORGANISATION},
            Scope.ORGANISATION: {Scope.ORGANISATION},
        }[self.scope]
        return frozenset(k for k in keys if registry.get(k).scope in allowed)


def _org(p: Permission) -> bool:
    return p.scope == Scope.ORGANISATION


def _practice(p: Permission) -> bool:
    return p.scope == Scope.PRACTICE


def _keys(*keys: str) -> Rule:
    wanted = frozenset(keys)
    return lambda p: p.key in wanted


def _any(*rules: Rule) -> Rule:
    return lambda p: any(rule(p) for rule in rules)


def _org_modules(modules: Iterable[str], read_only: Iterable[str] = ()) -> Rule:
    """Organisation permissions of `modules` (not critical) + read-only ones of `read_only`."""
    full, view = frozenset(modules), frozenset(read_only)
    return lambda p: (
        _org(p)
        and ((p.module in full and p.risk != Risk.CRITICAL) or (p.module in view and p.read_only))
    )


def _books(p: Permission) -> bool:
    """What an accountant does in a client's books: all but critical; users read-only."""
    return _org(p) and p.risk != Risk.CRITICAL and (p.module != "users" or p.read_only)


_profile = _keys(PROFILE_VIEW)

PLATFORM = Scope.PLATFORM
PRACTICE = Scope.PRACTICE
ORG = Scope.ORGANISATION

SYSTEM_ROLES: tuple[SystemRole, ...] = (
    # ---- platform (Numo9 staff) ----
    SystemRole(
        PLATFORM,
        "platform_owner",
        _("Platform owner"),
        _("Runs Numo9: products, packages, prices, feature flags and support tools."),
        lambda p: p.scope == Scope.PLATFORM,
    ),
    SystemRole(
        PLATFORM,
        "platform_support",
        _("Platform support"),
        _("Helps customers: console, background jobs, audited sign-in as a user."),
        _keys("platform.console.view", "platform.jobs.view", "platform.impersonate"),
    ),
    # ---- practice (accountants) ----
    SystemRole(
        PRACTICE,
        "practice_admin",
        _("Practice admin"),
        _("Runs the practice: staff, roles, clients, and full access to every client served."),
        lambda p: _practice(p) or (_org(p) and not p.owner_only),
    ),
    SystemRole(
        PRACTICE,
        "accountant",
        _("Accountant"),
        _("Keeps the books of the clients they are assigned to."),
        _any(
            _keys("practice.profile.view", "practice.staff.view", "practice.clients.create"),
            _books,
        ),
    ),
    SystemRole(
        PRACTICE,
        "reviewer",
        _("Reviewer"),
        _("Reviews and approves work in assigned clients; changes nothing else."),
        _any(
            _keys("practice.profile.view", "practice.staff.view"),
            lambda p: _org(p) and (p.read_only or p.action in {"approve", "review"}),
        ),
    ),
    SystemRole(
        PRACTICE,
        "payroll_specialist",
        _("Payroll specialist"),
        _("Runs payroll and HR for assigned clients."),
        _any(
            _keys("practice.profile.view"),
            _profile,
            _org_modules({"payroll", "hr"}, read_only={"reports", "documents", "contacts"}),
        ),
    ),
    SystemRole(
        PRACTICE,
        "read_only",
        _("Read-only staff"),
        _("Sees the practice and assigned clients; changes nothing."),
        lambda p: (_practice(p) or _org(p)) and p.read_only,
    ),
    # ---- organisation (the business) ----
    SystemRole(
        ORG,
        "owner",
        _("Owner"),
        _("Owns the organisation: everything, including closing it."),
        _org,
    ),
    SystemRole(
        ORG,
        "admin",
        _("Admin"),
        _("Manages the organisation and its users; can't close it."),
        lambda p: _org(p) and not p.owner_only,
    ),
    SystemRole(
        ORG,
        "accountant_delegate",
        _("Accountant delegate"),
        _("An in-house bookkeeper: the books, without user or critical settings."),
        _books,
    ),
    SystemRole(
        ORG,
        "sales",
        _("Sales"),
        _("Quotes, invoices and customers."),
        _any(_profile, _org_modules({"sales", "contacts"}, read_only={"reports", "documents"})),
    ),
    SystemRole(
        ORG,
        "purchasing",
        _("Purchasing"),
        _("Purchase orders, bills and suppliers."),
        _any(
            _profile,
            _org_modules(
                {"purchases", "contacts"}, read_only={"inventory", "reports", "documents"}
            ),
        ),
    ),
    SystemRole(
        ORG,
        "payroll",
        _("Payroll"),
        _("Pay runs and employees' pay."),
        _any(_profile, _org_modules({"payroll"}, read_only={"reports", "documents"})),
    ),
    SystemRole(
        ORG,
        "hr",
        _("HR"),
        _("Employees, leave and HR records."),
        _any(_profile, _org_modules({"hr"}, read_only={"documents"})),
    ),
    SystemRole(
        ORG,
        "employee",
        _("Employee"),
        _("Their own pay stubs, leave and expense claims (self-service)."),
        _profile,
    ),
)


def system_role(scope: Scope | str, key: str) -> SystemRole:
    for role in SYSTEM_ROLES:
        if role.scope == scope and role.key == key:
            return role
    raise KeyError(f"No system role {scope}/{key}.")


def sync_system_roles(
    role_model: Any, grant_model: Any, registry: PermissionRegistry = catalogue
) -> dict[str, int]:
    """Create missing system roles and make each one's permissions equal its rule.

    Takes the model classes so the data migration can pass its historical models. Returns
    counts (roles created, permissions added, permissions removed). Idempotent.
    """
    created = added = removed = 0
    for definition in SYSTEM_ROLES:
        with translation.override("en-ca"):  # stored in English; screens translate by key
            name, description = str(definition.name), str(definition.description)
        role, was_created = role_model.objects.get_or_create(
            scope=definition.scope.value,
            key=definition.key,
            is_system=True,
            defaults={"name": name, "description": description},
        )
        created += int(was_created)
        if not was_created and (role.name, role.description) != (name, description):
            role.name, role.description = name, description
            role.save(update_fields=["name", "description", "updated_at"])
        wanted = definition.permission_keys(registry)
        have = set(grant_model.objects.filter(role=role).values_list("permission", flat=True))
        missing = sorted(wanted - have)
        # bulk_create: the keys come from the catalogue and the rule respects the scope.
        grant_model.objects.bulk_create([grant_model(role=role, permission=k) for k in missing])
        added += len(missing)
        extra = have - wanted
        if extra:
            removed += grant_model.objects.filter(role=role, permission__in=extra).delete()[0]
    return {"roles_created": created, "permissions_added": added, "permissions_removed": removed}
