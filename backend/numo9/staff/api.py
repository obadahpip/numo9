"""Practice staff API (V-05), under ``/api/v1/practice/staff``.

Assignments (V-05-T04): ``GET staff/<user>/assignments`` — the organisations a member works on
directly and the groups they are assigned to; ``PUT``/``DELETE staff/<user>/organisations/<org>``
(``practice.clients.assign``) and ``PUT``/``DELETE staff/<user>/groups/<group>`` with ``role``
(``practice.groups.manage``) — effective on the next request.

``GET staff?practice=…`` (V-05-T02) — the practice's members and pending invitations with role,
organisations they can open, last sign-in and status (``active``, ``dormant``, ``suspended``,
``pending``). Practice-scoped: members of the practice with ``practice.directory.view`` (any
practice role); not a member → 404. Tenant-sweep exempt (``^api/v1/practice/``).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import AUTHENTICATED, checks_practice_permission, requires_permission
from numo9.rbac.resolver import has_practice_perm
from numo9.tenancy.models import Practice
from numo9.workspace.api import resolve_practice
from numo9.workspace.permissions import DIRECTORY_VIEW, GROUPS_MANAGE

PRACTICE_PARAM = OpenApiParameter("practice", OpenApiTypes.UUID)
STATUSES = [(s, s) for s in ("active", "dormant", "suspended", "pending")]


def practice_for(request: Request, permission: Any) -> Practice:
    given = request.data.get("practice") if isinstance(request.data, dict) else None
    practice = resolve_practice(request, str(given) if given else None)
    if not has_practice_perm(request.user, practice, permission.key):
        label = str(permission.label)
        raise api_error(errors.PERMISSION_DENIED, action=label[:1].lower() + label[1:])
    return practice


class StaffLineSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(help_text="The user's id; an invitation's id when pending")
    name = serializers.CharField()
    email = serializers.CharField()
    role = serializers.CharField()
    role_label = serializers.CharField()
    status = serializers.ChoiceField(choices=STATUSES)
    organisation_count = serializers.IntegerField()
    last_login = serializers.DateTimeField(allow_null=True)
    joined_at = serializers.DateTimeField(allow_null=True)
    suspended_at = serializers.DateTimeField(allow_null=True)
    dormant = serializers.BooleanField()
    invitation_expires_at = serializers.DateTimeField(allow_null=True)


class StaffListSerializer(serializers.Serializer[Any]):
    practice = serializers.UUIDField()
    dormant_days = serializers.IntegerField()
    staff = StaffLineSerializer(many=True)


class StaffListView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_staff_list",
        summary="The practice's staff: role, organisations, last sign-in, status",
        parameters=[PRACTICE_PARAM],
        responses=StaffListSerializer,
    )
    def get(self, request: Request) -> Response:
        from .directory import staff_lines

        practice = practice_for(request, DIRECTORY_VIEW)
        return Response(
            {
                "practice": practice.public_id,
                "dormant_days": practice.dormant_days,
                "staff": staff_lines(practice),
            }
        )


# ---- assignments (V-05-T04) --------------------------------------------------------------------


def _member(practice: Practice, user_id: Any) -> Any:
    from rest_framework.exceptions import NotFound

    from numo9.tenancy.models import PracticeMember

    member = (
        PracticeMember.objects.select_related("user", "practice")
        .filter(practice=practice, user__public_id=user_id)
        .first()
    )
    if member is None:
        raise NotFound
    return member


def _clients_assign() -> Any:
    from numo9.rbac.catalogue import catalogue

    return catalogue.get("practice.clients.assign")


class AssignmentOrgSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class AssignmentGroupSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    role = serializers.CharField()
    depth = serializers.IntegerField()


class AssignmentsSerializer(serializers.Serializer[Any]):
    organisations = AssignmentOrgSerializer(many=True)
    groups = AssignmentGroupSerializer(many=True)


class GroupRoleSerializer(serializers.Serializer[Any]):
    practice = serializers.UUIDField(required=False)
    role = serializers.CharField(required=False, default="accountant")


class StaffAssignmentsView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_staff_assignments",
        summary="Organisations and groups a staff member works on",
        parameters=[PRACTICE_PARAM],
        responses=AssignmentsSerializer,
    )
    def get(self, request: Request, user_id: Any) -> Response:
        from .assignments import assignments_of

        practice = practice_for(request, DIRECTORY_VIEW)
        return Response(assignments_of(_member(practice, user_id)))


class StaffOrganisationView(APIView):
    required_feature = CORE

    def _resolve(self, request: Request, user_id: Any, org_id: Any) -> tuple[Any, Any]:
        from rest_framework.exceptions import NotFound

        from numo9.tenancy.models import Organisation

        practice = practice_for(request, _clients_assign())
        member = _member(practice, user_id)
        organisation = Organisation.objects.filter(public_id=org_id).first()
        if organisation is None:
            raise NotFound
        return member, organisation

    @requires_permission(AUTHENTICATED)  # practice.clients.assign (checked here)
    @checks_practice_permission("practice.clients.assign")
    @extend_schema(
        operation_id="practice_staff_organisation_assign",
        summary="Assign a staff member to an organisation (direct access)",
        parameters=[PRACTICE_PARAM],
        request=None,
        responses=AssignmentsSerializer,
    )
    def put(self, request: Request, user_id: Any, org_id: Any) -> Response:
        from rest_framework.exceptions import NotFound

        from .assignments import NotServed, assign_organisation, assignments_of

        member, organisation = self._resolve(request, user_id, org_id)
        try:
            assign_organisation(member, organisation)
        except NotServed:
            raise NotFound from None
        return Response(assignments_of(member))

    @requires_permission(AUTHENTICATED)  # practice.clients.assign (checked here)
    @checks_practice_permission("practice.clients.assign")
    @extend_schema(
        operation_id="practice_staff_organisation_unassign",
        summary="Unassign a staff member from an organisation",
        parameters=[PRACTICE_PARAM],
        responses=AssignmentsSerializer,
    )
    def delete(self, request: Request, user_id: Any, org_id: Any) -> Response:
        from .assignments import assignments_of, unassign_organisation

        member, organisation = self._resolve(request, user_id, org_id)
        unassign_organisation(member, organisation)
        return Response(assignments_of(member))


class StaffGroupView(APIView):
    required_feature = CORE

    def _resolve(self, request: Request, user_id: Any, group_id: Any) -> tuple[Any, Any]:
        from rest_framework.exceptions import NotFound

        from numo9.workspace.models import OrgGroup

        practice = practice_for(request, GROUPS_MANAGE)
        member = _member(practice, user_id)
        group = OrgGroup.objects.filter(practice=practice, public_id=group_id).first()
        if group is None:
            raise NotFound
        return member, group

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_staff_group_assign",
        summary="Assign a staff member to a group with a role (or change the role)",
        parameters=[PRACTICE_PARAM],
        request=GroupRoleSerializer,
        responses=AssignmentsSerializer,
    )
    def put(self, request: Request, user_id: Any, group_id: Any) -> Response:
        from django.core.exceptions import ValidationError

        from numo9.workspace import groups

        from .assignments import assignments_of

        member, group = self._resolve(request, user_id, group_id)
        body = GroupRoleSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            groups.assign_staff(group, member, body.validated_data.get("role") or "accountant")
        except ValidationError as error:
            raise serializers.ValidationError({"role": error.messages}) from None
        return Response(assignments_of(member))

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_staff_group_unassign",
        summary="Unassign a staff member from a group",
        parameters=[PRACTICE_PARAM],
        responses=AssignmentsSerializer,
    )
    def delete(self, request: Request, user_id: Any, group_id: Any) -> Response:
        from numo9.workspace import groups

        from .assignments import assignments_of

        member, group = self._resolve(request, user_id, group_id)
        groups.unassign_staff(group, member)
        return Response(assignments_of(member))
