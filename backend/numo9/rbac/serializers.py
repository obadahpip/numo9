"""Serializers of the roles, assignments, approval limits and catalogue API (A-03-T09)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from numo9.tenancy.models import OrganisationRole, PracticeRole

from .catalogue import MODULE_LABELS, RISK_LABELS, Permission, Risk
from .models import ApprovalDocumentType, ApprovalLimit, Role, RoleScope
from .services import Person, holders, role_description, role_name

# ---- catalogue -----------------------------------------------------------------------------


class ModuleSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]


class PermissionSerializer(serializers.Serializer[Any]):
    key = serializers.CharField(help_text="Stable dotted key, e.g. organisation.members.invite")
    label = serializers.CharField(  # type: ignore[assignment]
        help_text="What it allows, in the request's language"
    )
    module = serializers.CharField()
    risk = serializers.ChoiceField(choices=[r.value for r in Risk])
    risk_label = serializers.CharField()
    scope = serializers.ChoiceField(choices=RoleScope.choices)
    owner_only = serializers.BooleanField()
    read_only = serializers.BooleanField(  # type: ignore[assignment]
        help_text="Only views or exports (view, export)"
    )


class CatalogueSerializer(serializers.Serializer[Any]):
    modules = ModuleSerializer(many=True)
    permissions = PermissionSerializer(many=True)


def permission_data(p: Permission) -> dict[str, Any]:
    return {
        "key": p.key,
        "label": str(p.label),
        "module": p.module,
        "risk": p.risk.value,
        "risk_label": str(RISK_LABELS[p.risk.value]),
        "scope": p.scope.value,
        "owner_only": p.owner_only,
        "read_only": p.read_only,
    }


def module_data(module: str) -> dict[str, str]:
    return {"key": module, "label": str(MODULE_LABELS[module])}


# ---- roles ---------------------------------------------------------------------------------


class RoleRefSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    key = serializers.CharField(help_text="System roles only, e.g. 'owner'; empty for custom roles")
    name = serializers.CharField()
    scope = serializers.ChoiceField(choices=RoleScope.choices)
    is_system = serializers.BooleanField()


class RoleSerializer(RoleRefSerializer):
    description = serializers.CharField()
    editable = serializers.BooleanField(help_text="Custom roles only; system roles are read-only")
    assignable = serializers.BooleanField(
        help_text="Can be given to people here (organisation roles; practice roles come with "
        "the practice)"
    )
    permissions = serializers.ListField(child=serializers.CharField())
    holders = serializers.IntegerField(help_text="People holding it in this organisation")


def role_ref(role: Role) -> dict[str, Any]:
    return {
        "id": role.public_id,
        "key": role.key,
        "name": role_name(role),
        "scope": role.scope,
        "is_system": role.is_system,
    }


def role_data(role: Role, organisation: Any) -> dict[str, Any]:
    return {
        **role_ref(role),
        "description": role_description(role),
        "editable": role.editable,
        "assignable": role.scope == RoleScope.ORGANISATION,
        "permissions": sorted(role.permission_keys()),
        "holders": holders(organisation, role),
    }


class RoleCreateSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=100, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, default=list
    )
    copy_from = serializers.UUIDField(
        required=False, help_text="Start from this role's permissions (system or custom)"
    )


class RoleUpdateSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=100, required=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True)
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        help_text="The complete new set (replaces the current one)",
    )


#: How a person reaches the organisation (members list).
MEMBER_KINDS = (("member", "Member"), ("practice", "Through a practice"))

# ---- people --------------------------------------------------------------------------------


class PracticeAccessSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(help_text="Practice public id")
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=PracticeRole.choices)
    role_name = serializers.CharField()


class MemberSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(help_text="The person's public id")
    name = serializers.CharField()
    email = serializers.EmailField()
    kind = serializers.ChoiceField(
        choices=MEMBER_KINDS,
        help_text="member: belongs to the organisation; practice: works here through a practice",
    )
    main_role = RoleRefSerializer(allow_null=True, help_text="Members only: their membership role")
    practices = PracticeAccessSerializer(many=True)
    roles = RoleRefSerializer(many=True, help_text="Further roles given here (custom roles)")


def member_data(person: Person, main_roles: dict[str, Role]) -> dict[str, Any]:
    main = None
    if person.membership is not None:
        main = role_ref(main_roles[person.membership.role])
    return {
        "id": person.user.public_id,
        "name": person.user.name,
        "email": person.user.email,
        "kind": person.kind,
        "main_role": main,
        "practices": [
            {
                "id": pm.practice.public_id,
                "name": pm.practice.name,
                "role": pm.role,
                "role_name": str(PracticeRole(pm.role).label),
            }
            for pm in person.practices
        ],
        "roles": [role_ref(r) for r in person.roles],
    }


class AssignRoleSerializer(serializers.Serializer[Any]):
    role = serializers.UUIDField(
        help_text="Organisation role id: a system role replaces a member's main role, a custom "
        "role is added"
    )


class InvitationRowSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=OrganisationRole.choices)
    expires_at = serializers.DateTimeField()
    inviter_name = serializers.CharField(source="inviter.name")


# ---- approval limits -----------------------------------------------------------------------


class PersonRefSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class ApprovalLimitSerializer(serializers.ModelSerializer[ApprovalLimit]):
    id = serializers.UUIDField(source="public_id", read_only=True)
    doc_type = serializers.ChoiceField(choices=ApprovalDocumentType.choices)
    max_amount = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
        help_text="CAD (the organisation's base currency)",
    )
    user = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalLimit
        fields = ("id", "doc_type", "max_amount", "user", "role", "updated_at")
        read_only_fields = ("updated_at",)

    @extend_schema_field(PersonRefSerializer(allow_null=True))
    def get_user(self, row: ApprovalLimit) -> dict[str, Any] | None:
        if row.user is None:
            return None
        return {"id": str(row.user.public_id), "name": row.user.name}

    @extend_schema_field(RoleRefSerializer(allow_null=True))
    def get_role(self, row: ApprovalLimit) -> dict[str, Any] | None:
        return None if row.role is None else {**role_ref(row.role), "id": str(row.role.public_id)}


class ApprovalLimitCreateSerializer(serializers.Serializer[Any]):
    doc_type = serializers.ChoiceField(choices=ApprovalDocumentType.choices)
    max_amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    user = serializers.UUIDField(required=False, help_text="A person's id — or role, not both")
    role = serializers.UUIDField(required=False, help_text="A role's id — or user, not both")


class ApprovalLimitUpdateSerializer(serializers.Serializer[Any]):
    max_amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
