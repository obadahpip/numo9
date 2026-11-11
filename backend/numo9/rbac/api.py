"""Roles, assignments, approval limits and the permission catalogue — API (A-03-T09).

Organisation-scoped (``/api/v1/o/<org>/…``; the organisation must be accessible, else 404):

- ``roles`` — GET list (``roles.role.view``) · POST create a custom role (``roles.role.manage``);
- ``roles/<role>`` — GET (view) · PATCH · DELETE, custom roles only (manage);
- ``members`` — GET people with access and their roles (``organisation.members.view``);
- ``members/<user>/roles`` — POST give a role (``roles.assignment.manage``);
- ``members/<user>/roles/<role>`` — DELETE take a custom role away (``roles.assignment.manage``);
- ``invitations`` — GET pending invitations (``organisation.members.view``);
- ``my-permissions`` — GET the signed-in user's permissions here (``organisation.profile.view``,
  which every role has), so screens show only the actions that work (A-03-T11);
- ``approval-limits`` — GET list (``roles.limit.view``) · POST create (``roles.limit.manage``);
- ``approval-limits/<limit>`` — GET (view) · PATCH · DELETE, soft (manage);
- ``approval-limits/check?doc_type&amount&user`` — GET whether that person may approve the
  amount (``assert_can_approve``: limit, refusal message, next approvers; ``roles.limit.view``).

Not organisation-scoped: ``GET /api/v1/permissions/catalogue`` (any signed-in user — it is the
same for everyone and holds no tenant data).

Rules (system roles read-only, no escalation, main role, last owner, …): ``services.py``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.i18n import errors
from numo9.i18n.errors import error_detail
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Invitation, InvitationKind, Organisation

from . import services
from .approvals import ApprovalLimitExceeded, assert_can_approve
from .catalogue import MODULES, catalogue
from .drf import AUTHENTICATED, requires_permission
from .models import ApprovalDocumentType, Role, RoleScope
from .permissions import (
    LIMITS_MANAGE,
    LIMITS_VIEW,
    ROLES_ASSIGN,
    ROLES_MANAGE,
    ROLES_VIEW,
)
from .resolver import organisation_permissions
from .serializers import (
    ApprovalLimitCreateSerializer,
    ApprovalLimitSerializer,
    ApprovalLimitUpdateSerializer,
    AssignRoleSerializer,
    CatalogueSerializer,
    InvitationRowSerializer,
    MemberSerializer,
    RoleCreateSerializer,
    RoleSerializer,
    RoleUpdateSerializer,
    member_data,
    module_data,
    permission_data,
    role_data,
)

MEMBERS_VIEW = "organisation.members.view"


def _org() -> Organisation:
    organisation = current_org()
    assert organisation is not None  # RequiresPermission answered 404 otherwise  # noqa: S101
    return organisation


def _user(request: Request) -> User:
    return cast(User, request.user)


# ---- catalogue -----------------------------------------------------------------------------


class PermissionCatalogueView(APIView):
    @requires_permission(AUTHENTICATED)  # the same for everyone; no tenant data
    @extend_schema(
        operation_id="permissions_catalogue",
        summary="Every permission Numo9 checks, grouped by module (role editor)",
        responses=CatalogueSerializer,
    )
    def get(self, request: Request) -> Response:
        used = {p.module for p in catalogue}
        body = {
            "modules": [module_data(m) for m in MODULES if m in used],
            "permissions": [permission_data(p) for p in catalogue],
        }
        return Response(CatalogueSerializer(body).data)


class MyPermissionsSerializer(serializers.Serializer[Any]):
    permissions = serializers.ListField(child=serializers.CharField())


class MyPermissionsView(APIView):
    """What the signed-in user may do here, so screens show only what works (A-03-T11)."""

    @requires_permission("organisation.profile.view")  # every role here has it
    @extend_schema(
        operation_id="my_permissions",
        summary="My permissions in the organisation (to show or hide actions)",
        responses=MyPermissionsSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        keys = sorted(organisation_permissions(request.user, _org()))
        return Response(MyPermissionsSerializer({"permissions": keys}).data)


# ---- roles ---------------------------------------------------------------------------------


class RoleListView(APIView):
    @requires_permission(ROLES_VIEW.key)
    @extend_schema(
        operation_id="roles_list",
        summary="Roles usable in the organisation (system and custom)",
        responses=RoleSerializer(many=True),
    )
    def get(self, request: Request, org: Any) -> Response:
        organisation = _org()
        roles = services.organisation_roles_here(organisation).prefetch_related("grants")
        ordered = sorted(
            roles,
            key=lambda r: (
                r.scope != RoleScope.ORGANISATION,
                not r.is_system,
                r.pk if r.is_system else 0,
                r.name.lower(),
            ),
        )
        return Response(
            RoleSerializer([role_data(r, organisation) for r in ordered], many=True).data
        )

    @requires_permission(ROLES_MANAGE.key)
    @extend_schema(
        operation_id="roles_create",
        summary="Create a custom role (optionally copied from another role)",
        request=RoleCreateSerializer,
        responses={201: RoleSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        organisation = _org()
        payload = RoleCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        copy_from = None
        if data.get("copy_from"):
            copy_from = (
                services.organisation_roles_here(organisation)
                .filter(public_id=data["copy_from"])
                .first()
            )
            if copy_from is None:
                raise serializers.ValidationError(
                    {"copy_from": [error_detail(errors.UNKNOWN_ROLE)]}
                )
        role = services.create_role(
            _user(request),
            organisation,
            name=data["name"],
            description=data.get("description", ""),
            permissions=data.get("permissions", []),
            copy_from=copy_from,
        )
        return Response(
            RoleSerializer(role_data(role, organisation)).data, status=status.HTTP_201_CREATED
        )


class RoleDetailView(APIView):
    @requires_permission(ROLES_VIEW.key)
    @extend_schema(operation_id="roles_retrieve", summary="One role", responses=RoleSerializer)
    def get(self, request: Request, org: Any, role_id: Any) -> Response:
        organisation = _org()
        role = services.get_role(organisation, role_id)
        return Response(RoleSerializer(role_data(role, organisation)).data)

    @requires_permission(ROLES_MANAGE.key)
    @extend_schema(
        operation_id="roles_update",
        summary="Rename or change a custom role's permissions (system roles: 409)",
        request=RoleUpdateSerializer,
        responses=RoleSerializer,
    )
    def patch(self, request: Request, org: Any, role_id: Any) -> Response:
        organisation = _org()
        role = services.get_role(organisation, role_id)
        payload = RoleUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        role = services.update_role(
            _user(request),
            organisation,
            role,
            name=data.get("name"),
            description=data.get("description"),
            permissions=data.get("permissions"),
        )
        return Response(RoleSerializer(role_data(role, organisation)).data)

    @requires_permission(ROLES_MANAGE.key)
    @extend_schema(
        operation_id="roles_destroy",
        summary="Delete a custom role nobody holds (system roles: 409)",
        responses={204: None},
    )
    def delete(self, request: Request, org: Any, role_id: Any) -> Response:
        organisation = _org()
        services.delete_role(organisation, services.get_role(organisation, role_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---- people and their roles ----------------------------------------------------------------


def _main_roles() -> dict[str, Role]:
    return {r.key: r for r in Role.objects.filter(is_system=True, scope=RoleScope.ORGANISATION)}


class MemberListView(APIView):
    @requires_permission(MEMBERS_VIEW)
    @extend_schema(
        operation_id="members_list",
        summary="People who can access the organisation, with their roles",
        responses=MemberSerializer(many=True),
    )
    def get(self, request: Request, org: Any) -> Response:
        main = _main_roles()
        rows = [member_data(p, main) for p in services.people(_org())]
        return Response(MemberSerializer(rows, many=True).data)


class MemberRolesView(APIView):
    @requires_permission(ROLES_ASSIGN.key)
    @extend_schema(
        operation_id="members_roles_assign",
        summary="Give a role: a system role replaces a member's main role, a custom role is added",
        request=AssignRoleSerializer,
        responses={200: MemberSerializer, 201: MemberSerializer},
    )
    def post(self, request: Request, org: Any, user_id: Any) -> Response:
        organisation = _org()
        person = services.get_person(organisation, user_id)
        payload = AssignRoleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        role = (
            services.organisation_roles_here(organisation)
            .filter(public_id=payload.validated_data["role"])
            .first()
        )
        if role is None:
            raise serializers.ValidationError({"role": [error_detail(errors.UNKNOWN_ROLE)]})
        with transaction.atomic():
            changed = services.assign_role(_user(request), organisation, person, role)
        person = services.get_person(organisation, user_id)
        code = status.HTTP_201_CREATED if changed and not role.is_system else status.HTTP_200_OK
        return Response(MemberSerializer(member_data(person, _main_roles())).data, status=code)


class MemberRoleDetailView(APIView):
    @requires_permission(ROLES_ASSIGN.key)
    @extend_schema(
        operation_id="members_roles_unassign",
        summary="Take a custom role away (the main role can only be replaced)",
        responses={204: None},
    )
    def delete(self, request: Request, org: Any, user_id: Any, role_id: Any) -> Response:
        organisation = _org()
        person = services.get_person(organisation, user_id)
        services.unassign_role(organisation, person, services.get_role(organisation, role_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PendingInvitationsView(APIView):
    @requires_permission(MEMBERS_VIEW)
    @extend_schema(
        operation_id="members_invitations_list",
        summary="Invitations to the organisation still waiting for an answer",
        responses=InvitationRowSerializer(many=True),
    )
    def get(self, request: Request, org: Any) -> Response:
        rows = (
            Invitation.objects.filter(
                organisation=_org(),
                kind__in=[InvitationKind.ORGANISATION_USER, InvitationKind.ORGANISATION_OWNER],
                accepted_at__isnull=True,
                revoked_at__isnull=True,
            )
            .filter(expires_at__gt=timezone.now())
            .select_related("inviter")
            .order_by("email")
        )
        return Response(InvitationRowSerializer(rows, many=True).data)


# ---- approval limits -----------------------------------------------------------------------


class ApprovalLimitListView(APIView):
    serializer_class = ApprovalLimitSerializer  # tenant sweep: rows of ApprovalLimit

    @requires_permission(LIMITS_VIEW.key)
    @extend_schema(
        operation_id="approval_limits_list",
        summary="Approval limits per person or role and document type (CAD)",
        responses=ApprovalLimitSerializer(many=True),
    )
    def get(self, request: Request, org: Any) -> Response:
        return Response(ApprovalLimitSerializer(services.limits(_org()), many=True).data)

    @requires_permission(LIMITS_MANAGE.key)
    @extend_schema(
        operation_id="approval_limits_create",
        summary="Set an approval limit for a person or a role",
        request=ApprovalLimitCreateSerializer,
        responses={201: ApprovalLimitSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        organisation = _org()
        payload = ApprovalLimitCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        user = role = None
        if data.get("user"):
            person = next(
                (
                    p
                    for p in services.people(organisation)
                    if str(p.user.public_id) == str(data["user"])
                ),
                None,
            )
            if person is None:
                raise serializers.ValidationError({"user": [error_detail(errors.UNKNOWN_PERSON)]})
            user = person.user
        if data.get("role"):
            role = (
                services.organisation_roles_here(organisation)
                .filter(public_id=data["role"])
                .first()
            )
            if role is None:
                raise serializers.ValidationError({"role": [error_detail(errors.UNKNOWN_ROLE)]})
        row = services.create_limit(
            _user(request),
            organisation,
            doc_type=data["doc_type"],
            max_amount=data["max_amount"],
            user=user,
            role=role,
        )
        return Response(ApprovalLimitSerializer(row).data, status=status.HTTP_201_CREATED)


class ApproverSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    limit = serializers.DecimalField(max_digits=18, decimal_places=2)


class LimitCheckQuerySerializer(serializers.Serializer[Any]):
    doc_type = serializers.ChoiceField(choices=ApprovalDocumentType.choices)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"))
    user = serializers.UUIDField(help_text="The person whose approval is checked")


class LimitCheckSerializer(serializers.Serializer[Any]):
    allowed = serializers.BooleanField()
    limit = serializers.DecimalField(max_digits=18, decimal_places=2, allow_null=True)
    code = serializers.CharField(allow_null=True)
    detail = serializers.CharField(allow_null=True)
    approvers = ApproverSerializer(many=True)


class ApprovalLimitCheckView(APIView):
    """Would this person be allowed to approve this amount? (A-03-T13 "Verify an amount")."""

    @requires_permission(LIMITS_VIEW.key)
    @extend_schema(
        operation_id="approval_limits_check",
        summary="Check an amount against a person's effective approval limit",
        parameters=[LimitCheckQuerySerializer],
        responses=LimitCheckSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        organisation = _org()
        query = LimitCheckQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        person = next(
            (
                p
                for p in services.people(organisation)
                if str(p.user.public_id) == str(data["user"])
            ),
            None,
        )
        if person is None:
            raise serializers.ValidationError({"user": [error_detail(errors.UNKNOWN_PERSON)]})
        try:
            limit = assert_can_approve(person.user, data["doc_type"], data["amount"])
        except ApprovalLimitExceeded as refused:
            body = {
                "allowed": False,
                "limit": refused.limit,
                "code": refused.get_codes(),
                "detail": str(refused.detail),
                "approvers": (refused.extra or {}).get("approvers", []),
            }
        else:
            body = {"allowed": True, "limit": limit, "code": None, "detail": None, "approvers": []}
        return Response(LimitCheckSerializer(body).data)


class ApprovalLimitDetailView(APIView):
    serializer_class = ApprovalLimitSerializer

    @requires_permission(LIMITS_VIEW.key)
    @extend_schema(
        operation_id="approval_limits_retrieve",
        summary="One approval limit",
        responses=ApprovalLimitSerializer,
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(ApprovalLimitSerializer(services.get_limit(_org(), public_id)).data)

    @requires_permission(LIMITS_MANAGE.key)
    @extend_schema(
        operation_id="approval_limits_update",
        summary="Change the amount of an approval limit",
        request=ApprovalLimitUpdateSerializer,
        responses=ApprovalLimitSerializer,
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        row = services.get_limit(_org(), public_id)
        payload = ApprovalLimitUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = services.update_limit(row, max_amount=payload.validated_data["max_amount"])
        return Response(ApprovalLimitSerializer(row).data)

    @requires_permission(LIMITS_MANAGE.key)
    @extend_schema(
        operation_id="approval_limits_destroy",
        summary="Remove an approval limit (kept in history)",
        responses={204: None},
    )
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        services.delete_limit(services.get_limit(_org(), public_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
