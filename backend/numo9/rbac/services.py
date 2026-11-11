"""Role, assignment and approval-limit management in an organisation (A-03-T09).

The API (``api.py``) is a thin layer over these functions; the permission to call each one is
checked by ``RequiresPermission`` (roles.role.manage, roles.assignment.manage,
roles.limit.manage). The rules here hold whoever calls them:

- **System roles are read-only** (``roles.system_role``); custom roles belong to one
  organisation and are edited there only (another organisation's role → "unknown role").
- **No escalation**: a person can only put into a role, or give someone a role with, permissions
  they hold themselves in the organisation (``roles.grant_exceeds_own``). Owners hold every
  organisation permission, so only they can create a role with ``organisation.close`` or make
  someone an owner.
- **Main role** = the membership role (``OrganisationMember.role``, a system role): members have
  exactly one; giving a member another system role replaces it. The last owner keeps the owner
  role (``roles.last_owner``). People who work here through a practice have no main role; they
  can be given custom roles.
- A role still given to people can't be deleted (``roles.in_use``); deleting a custom role
  removes its approval limits.
- Approval limits: one live limit per person (or role) and document type
  (``limits.duplicate``); deleting is a soft delete (CRA retention).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from numo9.i18n import errors
from numo9.i18n.errors import api_error, error_detail
from numo9.tenancy.access import PRACTICE_WIDE_ROLES, can_access
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    PracticeAssignment,
    PracticeMember,
)

from .catalogue import Scope, UnknownPermission, catalogue
from .models import ApprovalLimit, Role, RoleAssignment, RolePermission, RoleScope
from .resolver import organisation_permissions
from .system_roles import system_role


def role_name(role: Role) -> str:
    """The role's name in the active language (system roles are translated by key)."""
    if role.is_system:
        try:
            return str(system_role(role.scope, role.key).name)
        except KeyError:
            return role.name
    return role.name


def role_description(role: Role) -> str:
    if role.is_system:
        try:
            return str(system_role(role.scope, role.key).description)
        except KeyError:
            return role.description
    return role.description


# ---- roles ---------------------------------------------------------------------------------


def organisation_roles_here(organisation: Organisation) -> QuerySet[Role]:
    """Roles usable in the organisation: system organisation roles, its custom roles, and the
    system practice roles (which practices give their staff; approval limits may name them)."""
    return Role.objects.filter(
        Q(is_system=True, scope__in=[RoleScope.ORGANISATION, RoleScope.PRACTICE])
        | Q(is_system=False, scope=RoleScope.ORGANISATION, organisation=organisation)
    )


def get_role(organisation: Organisation, public_id: Any) -> Role:
    """A role usable in the organisation, or 404 (another organisation's role looks unknown)."""
    role = organisation_roles_here(organisation).filter(public_id=public_id).first()
    if role is None:
        raise api_error(errors.ROLE_NOT_FOUND)
    return role


def _clean_keys(keys: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    problems: list[Any] = []
    for key in dict.fromkeys(keys):  # keep order, drop duplicates
        try:
            permission = catalogue.get(key)
        except UnknownPermission:
            problems.append(error_detail(errors.UNKNOWN_PERMISSION, key=key))
            continue
        if permission.scope != Scope.ORGANISATION:
            problems.append(
                error_detail(errors.PERMISSION_NOT_GRANTABLE, key=key, scope=permission.scope.value)
            )
            continue
        cleaned.append(key)
    if problems:
        raise serializers.ValidationError({"permissions": problems})
    return cleaned


def _assert_within_own(actor: Any, organisation: Organisation, keys: Iterable[str]) -> None:
    missing = sorted(set(keys) - organisation_permissions(actor, organisation))
    if missing:
        labels = ", ".join(str(catalogue.get(k).label) for k in missing)
        error = api_error(errors.GRANT_EXCEEDS_OWN, permissions=labels)
        error.extra = {"permissions": missing}
        raise error


def _assert_editable(role: Role) -> None:
    if role.is_system:
        raise api_error(errors.ROLE_SYSTEM, role=role_name(role))


def _save_name(role: Role) -> None:
    try:
        with transaction.atomic():
            role.save()
    except IntegrityError:
        raise api_error(errors.ROLE_NAME_TAKEN, name=role.name) from None


def create_role(
    actor: Any,
    organisation: Organisation,
    *,
    name: str,
    description: str = "",
    permissions: Iterable[str] = (),
    copy_from: Role | None = None,
) -> Role:
    """A custom organisation role; ``copy_from`` starts from another role's permissions."""
    keys = list(permissions)
    if copy_from is not None:
        keys = [*copy_from.permission_keys(), *keys]
        keys = [k for k in keys if k in catalogue and catalogue.get(k).scope == Scope.ORGANISATION]
    keys = _clean_keys(keys)
    _assert_within_own(actor, organisation, keys)
    with transaction.atomic():
        role = Role(
            scope=RoleScope.ORGANISATION,
            name=name.strip(),
            description=description.strip(),
            organisation=organisation,
        )
        _save_name(role)
        RolePermission.objects.bulk_create([RolePermission(role=role, permission=k) for k in keys])
    return role


def update_role(
    actor: Any,
    organisation: Organisation,
    role: Role,
    *,
    name: str | None = None,
    description: str | None = None,
    permissions: Iterable[str] | None = None,
) -> Role:
    _assert_editable(role)
    with transaction.atomic():
        if name is not None:
            role.name = name.strip()
        if description is not None:
            role.description = description.strip()
        _save_name(role)
        if permissions is not None:
            keys = _clean_keys(permissions)
            have = role.permission_keys()
            _assert_within_own(actor, organisation, set(keys) - have)  # only additions
            role.grants.exclude(permission__in=keys).delete()
            RolePermission.objects.bulk_create(
                [RolePermission(role=role, permission=k) for k in keys if k not in have]
            )
    return role


def holders(organisation: Organisation, role: Role) -> int:
    """How many people hold the role in the organisation (membership + assignments)."""
    assigned = RoleAssignment.objects.filter(role=role, organisation=organisation).count()
    if role.is_system and role.scope == RoleScope.ORGANISATION:
        assigned += OrganisationMember.objects.filter(
            organisation=organisation, role=role.key
        ).count()
    return assigned


def delete_role(organisation: Organisation, role: Role) -> None:
    _assert_editable(role)
    count = holders(organisation, role)
    if count:
        raise api_error(errors.ROLE_IN_USE, role=role.name, count=count)
    with transaction.atomic():
        ApprovalLimit.objects.filter(role=role, organisation=organisation).delete()
        role.delete()


# ---- people and their roles ----------------------------------------------------------------


@dataclass
class Person:
    """Someone who can access the organisation (members list, A-03-T11)."""

    user: Any
    membership: OrganisationMember | None = None
    practices: list[PracticeMember] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)  # assigned (custom) organisation roles

    @property
    def kind(self) -> str:
        return "member" if self.membership is not None else "practice"


def people(organisation: Organisation) -> list[Person]:
    """Members, then staff of serving practices with access; each with their assigned roles."""
    found: dict[int, Person] = {}
    for membership in OrganisationMember.objects.filter(organisation=organisation).select_related(
        "user"
    ):
        found[membership.user_id] = Person(membership.user, membership=membership)
    assignments = PracticeAssignment.objects.filter(organisation=organisation, active=True)
    for assignment in assignments.prefetch_related("assigned_staff"):
        staff_ids = {m.pk for m in assignment.assigned_staff.all()}
        for pm in PracticeMember.objects.filter(practice_id=assignment.practice_id).select_related(
            "user", "practice"
        ):
            if pm.role in PRACTICE_WIDE_ROLES or pm.pk in staff_ids:
                person = found.setdefault(pm.user_id, Person(pm.user))
                person.practices.append(pm)
    for assignment_row in RoleAssignment.objects.filter(organisation=organisation).select_related(
        "role"
    ):
        if assignment_row.user_id in found:
            found[assignment_row.user_id].roles.append(assignment_row.role)
    everyone = [p for p in found.values() if p.user.is_active]
    for person in everyone:
        person.roles.sort(key=lambda r: r.name.lower())
    return sorted(everyone, key=lambda p: (p.kind != "member", p.user.name.lower(), p.user.pk))


def get_person(organisation: Organisation, public_id: Any) -> Person:
    for person in people(organisation):
        if str(person.user.public_id) == str(public_id):
            return person
    raise api_error(errors.PERSON_NOT_FOUND)


def _main_role(key: str) -> Role:
    return Role.objects.get(is_system=True, scope=RoleScope.ORGANISATION, key=key)


def assign_role(actor: Any, organisation: Organisation, person: Person, role: Role) -> bool:
    """Give ``role`` to the person; returns True when something changed.

    A system organisation role replaces a member's main role; a custom role is added.
    """
    if role.scope != RoleScope.ORGANISATION:
        raise serializers.ValidationError(
            {"role": [error_detail(errors.ROLE_NOT_ASSIGNABLE, role=role_name(role))]}
        )
    _assert_within_own(actor, organisation, role.permission_keys())
    if role.is_system:
        membership = person.membership
        if membership is None:
            raise serializers.ValidationError(
                {"role": [error_detail(errors.NOT_A_MEMBER, name=person.user.name)]}
            )
        if membership.role == role.key:
            return False
        with transaction.atomic():
            if membership.role == OrganisationRole.OWNER and not _other_owner(
                organisation, membership
            ):
                raise api_error(errors.LAST_OWNER, name=person.user.name)
            membership.role = role.key
            membership.save(update_fields=["role"])
        return True
    if not can_access(person.user, organisation):
        raise api_error(errors.PERSON_NOT_FOUND)
    _, created = RoleAssignment.objects.get_or_create(
        role=role, user=person.user, organisation=organisation, defaults={"assigned_by": actor}
    )
    return created


def _other_owner(organisation: Organisation, membership: OrganisationMember) -> bool:
    owners = OrganisationMember.objects.select_for_update().filter(
        organisation=organisation, role=OrganisationRole.OWNER
    )
    return owners.exclude(pk=membership.pk).filter(user__is_active=True).exists()


def unassign_role(organisation: Organisation, person: Person, role: Role) -> None:
    if role.is_system:
        if person.membership is not None and person.membership.role == role.key:
            raise api_error(errors.MAIN_ROLE)
        raise api_error(errors.ROLE_NOT_FOUND)
    deleted, _ = RoleAssignment.objects.filter(
        role=role, user=person.user, organisation=organisation
    ).delete()
    if not deleted:
        raise api_error(errors.ROLE_NOT_FOUND)


# ---- approval limits -----------------------------------------------------------------------


def limits(organisation: Organisation) -> QuerySet[ApprovalLimit]:
    return (
        ApprovalLimit.objects.filter(organisation=organisation, deleted_at__isnull=True)
        .select_related("user", "role")
        .order_by("doc_type", "role__name", "user__name", "pk")
    )


def get_limit(organisation: Organisation, public_id: Any) -> ApprovalLimit:
    row = limits(organisation).filter(public_id=public_id).first()
    if row is None:
        raise NotFound

    return row


def _who(row: ApprovalLimit) -> str:
    return row.user.name if row.user is not None else role_name(row.role)  # type: ignore[arg-type]


def create_limit(
    actor: Any,
    organisation: Organisation,
    *,
    doc_type: str,
    max_amount: Decimal,
    user: Any | None = None,
    role: Role | None = None,
) -> ApprovalLimit:
    if (user is None) == (role is None):
        raise serializers.ValidationError({"non_field_errors": [error_detail(errors.LIMIT_TARGET)]})
    row = ApprovalLimit(
        organisation=organisation,
        doc_type=doc_type,
        max_amount=max_amount,
        user=user,
        role=role,
        created_by=actor,
    )
    row.full_clean(validate_unique=False, validate_constraints=False)
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError:
        raise api_error(errors.LIMIT_DUPLICATE, who=_who(row)) from None
    return row


def update_limit(row: ApprovalLimit, *, max_amount: Decimal) -> ApprovalLimit:
    row.max_amount = max_amount
    row.full_clean(validate_unique=False, validate_constraints=False)
    row.save(update_fields=["max_amount", "updated_at"])
    return row


def delete_limit(row: ApprovalLimit) -> None:
    row.soft_delete()
