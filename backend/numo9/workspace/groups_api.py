"""Groups and tags API (V-02-T07), under ``/api/v1/practice/``.

Groups (a tree per practice, depth ≤ 5):

- ``GET    groups?practice=…`` — the practice's groups in tree order, each with its parent, depth,
  organisations filed directly, organisations in the whole subtree and staff assigned directly;
- ``POST   groups`` — create (``name``, optional ``parent``);
- ``GET    groups/<id>`` — one group with its organisations and its staff (assigned here, and
  *inherited* from ancestor groups);
- ``PATCH  groups/<id>`` — rename (``name``) and/or move (``parent``: a group id, or ``null`` for
  the top level);
- ``GET    groups/<id>/impact`` — what deleting it affects: groups, organisations and staff
  assignments in the subtree, and the staff who would lose access to at least one organisation;
- ``DELETE groups/<id>`` — delete with its sub-groups (their organisations stay clients; the staff
  assignments go, which removes the access they granted);
- ``POST   groups/<id>/organisations`` — file organisations (``organisations``: ids);
- ``DELETE groups/<id>/organisations/<org id>`` — take one out;
- ``PUT    groups/<id>/staff/<user id>`` — assign a staff member (``role``) or change the role;
- ``DELETE groups/<id>/staff/<user id>`` — unassign.

Tags (12 named colours, names unique per practice):

- ``GET tags?practice=…``, ``POST tags`` (``name``, ``colour``), ``PATCH tags/<id>``,
  ``DELETE tags/<id>``;
- ``POST tags/<id>/organisations`` (``organisations``: ids),
  ``DELETE tags/<id>/organisations/<org>``.

Who: reading needs ``practice.directory.view`` (every practice role); every change needs
``practice.groups.manage`` (practice admins). Not a member of the practice, or a group/tag of
another practice → 404. Refusals of the group and tag rules are 400 ``{"detail", "code",
"field"}`` with the service's code (``workspace.group.too_deep``, ``workspace.tag.name_taken``…).
Not organisation-scoped: on the tenant-sweep exempt list (``^api/v1/practice/``).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import AUTHENTICATED, checks_practice_permission, requires_permission
from numo9.rbac.resolver import has_practice_perm
from numo9.tenancy.models import Organisation, Practice, PracticeAssignment, PracticeMember

from . import groups as group_service
from . import tags as tag_service
from .api import resolve_practice
from .models import (
    GroupStaffAssignment,
    GroupStaffRole,
    OrgGroup,
    OrgGroupMembership,
    OrgTag,
    Tag,
    TagColour,
)
from .permissions import DIRECTORY_VIEW, GROUPS_MANAGE

MAX_BATCH = 500


class RuleRefused(APIException):
    """A 400 from a group or tag rule: the service's message and stable code, and the field."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, error: ValidationError, field: str) -> None:
        super().__init__(detail=error.messages[0], code=error.code or "invalid")
        self.extra = {"field": field}


@contextmanager
def _refused(field: str) -> Iterator[None]:
    try:
        yield
    except ValidationError as error:
        raise RuleRefused(error, field) from None


def _label(permission: Any) -> str:
    text = str(permission.label)
    return text[:1].lower() + text[1:]


def _require(request: Request, practice: Practice, permission: Any) -> None:
    if not has_practice_perm(request.user, practice, permission.key):
        raise api_error(errors.PERMISSION_DENIED, action=_label(permission))


def _practice(request: Request, permission: Any) -> Practice:
    given = request.data.get("practice") if isinstance(request.data, dict) else None
    practice = resolve_practice(request, str(given) if given else None)
    _require(request, practice, permission)
    return practice


def _data(request: Request) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


def _uuid(value: Any) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise NotFound from None


def _group(request: Request, group_id: uuid.UUID, permission: Any) -> OrgGroup:
    group: OrgGroup | None = (
        OrgGroup.objects.filter(public_id=group_id).select_related("practice").first()
    )
    if (
        group is None
        or not PracticeMember.objects.filter(
            practice_id=group.practice_id, user=cast(User, request.user)
        ).exists()
    ):
        raise NotFound  # unknown, or another practice's group: the same answer
    _require(request, group.practice, permission)
    return group


def _tag(request: Request, tag_id: uuid.UUID, permission: Any) -> Tag:
    tag = Tag.objects.filter(public_id=tag_id).select_related("practice").first()
    if (
        tag is None
        or not PracticeMember.objects.filter(
            practice_id=tag.practice_id, user=cast(User, request.user)
        ).exists()
    ):
        raise NotFound
    _require(request, tag.practice, permission)
    return tag


def _served(practice: Practice, ids: Any, field: str = "organisations") -> list[Organisation]:
    if not isinstance(ids, list) or not ids or len(ids) > MAX_BATCH:
        raise RuleRefused(
            ValidationError(
                _("Choose 1 to %(max)d organisations.") % {"max": MAX_BATCH},
                code="workspace.organisations",
            ),
            field,
        )
    wanted = {_uuid(value) for value in ids}
    found = list(
        Organisation.objects.filter(
            public_id__in=wanted,
            practice_assignments__practice=practice,
            practice_assignments__active=True,
        ).distinct()
    )
    if len(found) != len(wanted):
        raise NotFound  # an organisation the practice doesn't serve: never named
    return found


# ---- presentation ------------------------------------------------------------------------------


def _subtree_counts(practice: Practice) -> dict[str, int]:
    """Distinct organisations per group path including its descendants (one query)."""
    rows = list(
        OrgGroupMembership.objects.filter(group__practice=practice).values_list(
            "group__path", "organisation_id"
        )
    )
    paths = list(OrgGroup.objects.filter(practice=practice).values_list("path", flat=True))
    counts: dict[str, int] = {}
    for path in paths:
        counts[path] = len({org for p, org in rows if p.startswith(path)})
    return counts


def present_groups(practice: Practice) -> list[dict[str, Any]]:
    groups = list(
        OrgGroup.objects.filter(practice=practice)
        .annotate(
            organisation_count=Count("memberships", distinct=True),
            staff_count=Count("staff", distinct=True),
        )
        .order_by("path")
    )
    by_path = {group.path: group for group in groups}
    subtree = _subtree_counts(practice)
    out = []
    for group in groups:
        parent = by_path.get(group.path[: -OrgGroup.steplen]) if group.depth > 1 else None
        out.append(
            {
                "id": group.public_id,
                "name": group.name,
                "parent": parent.public_id if parent else None,
                "depth": group.depth,
                "has_children": group.numchild > 0,
                "organisation_count": group.organisation_count,
                "subtree_organisation_count": subtree.get(group.path, 0),
                "staff_count": group.staff_count,
            }
        )
    return out


def _group_payload(group: OrgGroup) -> dict[str, Any]:
    for item in present_groups(group.practice):
        if item["id"] == group.public_id:
            return item
    raise NotFound


def _ancestors(group: OrgGroup) -> list[OrgGroup]:
    prefixes = [group.path[: i * OrgGroup.steplen] for i in range(1, group.depth)]
    return list(OrgGroup.objects.filter(practice=group.practice, path__in=prefixes))


def group_detail(group: OrgGroup) -> dict[str, Any]:
    organisations = (
        Organisation.objects.filter(group_memberships__group=group)
        .order_by("name")
        .values("public_id", "name")
    )
    ancestors = {a.pk: a for a in _ancestors(group)}
    staff_rows = (
        GroupStaffAssignment.objects.filter(group_id__in=[group.pk, *ancestors])
        .select_related("practice_member__user", "group")
        .order_by("practice_member__user__name")
    )
    staff = [
        {
            "user": row.practice_member.user.public_id,
            "name": row.practice_member.user.name,
            "email": row.practice_member.user.email,
            "role": row.role,
            "inherited_from": None
            if row.group_id == group.pk
            else {"id": row.group.public_id, "name": row.group.name},
        }
        for row in staff_rows
    ]
    return {
        **_group_payload(group),
        "organisations": [{"id": o["public_id"], "name": o["name"]} for o in organisations],
        "staff": staff,
    }


def group_impact(group: OrgGroup) -> dict[str, Any]:
    """What deleting ``group`` (and its sub-groups) affects — shown by the delete dialog."""
    subtree = OrgGroup.objects.filter(practice=group.practice, path__startswith=group.path)
    organisations = set(
        OrgGroupMembership.objects.filter(group__in=subtree).values_list(
            "organisation_id", flat=True
        )
    )
    staff = list(
        GroupStaffAssignment.objects.filter(group__in=subtree).values_list(
            "practice_member_id", "practice_member__user_id"
        )
    )
    # Who would lose access to at least one organisation: compare what each affected staff
    # member reaches with and without the subtree (other groups and direct assignments count).
    losing = 0
    for user_id in {u for _m, u in staff}:
        other_paths = list(
            GroupStaffAssignment.objects.filter(practice_member__user_id=user_id)
            .exclude(group__in=subtree)
            .filter(group__practice=group.practice)
            .values_list("group__path", flat=True)
        )
        kept = set()
        if other_paths:
            cover = Q()
            for path in other_paths:
                cover |= Q(group__path__startswith=path)
            kept = set(
                OrgGroupMembership.objects.filter(group__practice=group.practice)
                .exclude(group__in=subtree)
                .filter(cover)
                .values_list("organisation_id", flat=True)
            )
        direct = set(
            PracticeAssignment.objects.filter(
                practice=group.practice, active=True, assigned_staff__user_id=user_id
            ).values_list("organisation_id", flat=True)
        )
        wide = PracticeMember.objects.filter(
            practice=group.practice, user_id=user_id, role="practice_admin"
        ).exists()
        if not wide and organisations - kept - direct:
            losing += 1
    return {
        "groups": subtree.count(),
        "organisations": len(organisations),
        "staff_assignments": len(staff),
        "staff": len({m for m, _u in staff}),
        "staff_losing_access": losing,
    }


def present_tags(practice: Practice) -> list[dict[str, Any]]:
    tags = Tag.objects.filter(practice=practice).annotate(
        organisation_count=Count("assignments", distinct=True)
    )
    return [_tag_payload(tag, tag.organisation_count) for tag in tags]


def _tag_payload(tag: Tag, count: int | None = None) -> dict[str, Any]:
    if count is None:
        count = OrgTag.objects.filter(tag=tag).count()
    return {
        "id": tag.public_id,
        "name": tag.name,
        "colour": tag.colour,
        "colour_label": str(TagColour(tag.colour).label),
        "organisation_count": count,
    }


# ---- serializers (OpenAPI contract) -----------------------------------------------------------


class PracticeGroupSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    parent = serializers.UUIDField(allow_null=True)  # type: ignore[assignment]  # DRF Field.parent
    depth = serializers.IntegerField(help_text="1 = top level; 5 at most.")
    has_children = serializers.BooleanField()
    organisation_count = serializers.IntegerField(help_text="Organisations filed in this group.")
    subtree_organisation_count = serializers.IntegerField(
        help_text="Distinct organisations in this group and its sub-groups."
    )
    staff_count = serializers.IntegerField(help_text="Staff assigned to this group directly.")


class PracticeGroupListSerializer(serializers.Serializer[Any]):
    practice = serializers.UUIDField()
    groups = PracticeGroupSerializer(many=True)


class PracticeNamedSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class PracticeGroupStaffSerializer(serializers.Serializer[Any]):
    user = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.CharField()
    role = serializers.ChoiceField(choices=GroupStaffRole.choices)
    inherited_from = PracticeNamedSerializer(allow_null=True)


class PracticeGroupDetailSerializer(PracticeGroupSerializer):
    organisations = PracticeNamedSerializer(many=True)
    staff = PracticeGroupStaffSerializer(many=True)


class PracticeGroupImpactSerializer(serializers.Serializer[Any]):
    groups = serializers.IntegerField(help_text="The group and its sub-groups.")
    organisations = serializers.IntegerField(help_text="Distinct organisations filed there.")
    staff_assignments = serializers.IntegerField()
    staff = serializers.IntegerField(help_text="Distinct staff members assigned there.")
    staff_losing_access = serializers.IntegerField(
        help_text="Staff who would lose access to at least one organisation."
    )


class PracticeGroupWriteSerializer(serializers.Serializer[Any]):
    practice = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False, max_length=200, allow_blank=True)
    parent = serializers.UUIDField(  # type: ignore[assignment]  # DRF Field.parent
        required=False, allow_null=True
    )


class PracticeOrganisationsSerializer(serializers.Serializer[Any]):
    organisations = serializers.ListField(child=serializers.UUIDField(), max_length=MAX_BATCH)


class PracticeStaffWriteSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(choices=GroupStaffRole.choices)


class PracticeTagSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    colour = serializers.ChoiceField(choices=TagColour.choices)
    colour_label = serializers.CharField(help_text="The colour's name: tags never rely on colour.")
    organisation_count = serializers.IntegerField()


class PracticeTagListSerializer(serializers.Serializer[Any]):
    practice = serializers.UUIDField()
    tags = PracticeTagSerializer(many=True)


class PracticeTagWriteSerializer(serializers.Serializer[Any]):
    practice = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False, max_length=200, allow_blank=True)
    colour = serializers.CharField(required=False)


class PracticeCountSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()


def _parent(practice: Practice, value: Any) -> OrgGroup | None:
    if value is None:
        return None
    parent: OrgGroup | None = OrgGroup.objects.filter(
        public_id=_uuid(value), practice=practice
    ).first()
    if parent is None:
        raise NotFound
    return parent


PRACTICE_PARAM = OpenApiParameter("practice", OpenApiTypes.UUID)


# ---- views: groups -----------------------------------------------------------------------------


class GroupListView(APIView):
    required_feature = CORE  # the Practice product is free: never gated

    @requires_permission(AUTHENTICATED)  # practice.directory.view in the practice (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_groups_list",
        summary="The practice's groups (tree order)",
        parameters=[PRACTICE_PARAM],
        responses=PracticeGroupListSerializer,
    )
    def get(self, request: Request) -> Response:
        practice = _practice(request, DIRECTORY_VIEW)
        return Response({"practice": practice.public_id, "groups": present_groups(practice)})

    @requires_permission(AUTHENTICATED)  # practice.groups.manage in the practice (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_groups_create",
        summary="Create a group",
        request=PracticeGroupWriteSerializer,
        responses={201: PracticeGroupSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = PracticeGroupWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        practice = _practice(request, GROUPS_MANAGE)
        parent = _parent(practice, payload.validated_data.get("parent"))
        with _refused("name"):
            group = group_service.create_group(
                practice, payload.validated_data.get("name", ""), parent
            )
        return Response(_group_payload(group), status=status.HTTP_201_CREATED)


class GroupDetailView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_groups_detail",
        summary="One group: its organisations and staff",
        responses=PracticeGroupDetailSerializer,
    )
    def get(self, request: Request, group_id: uuid.UUID) -> Response:
        return Response(group_detail(_group(request, group_id, DIRECTORY_VIEW)))

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_groups_update",
        summary="Rename and/or move a group",
        request=PracticeGroupWriteSerializer,
        responses=PracticeGroupSerializer,
    )
    def patch(self, request: Request, group_id: uuid.UUID) -> Response:
        group = _group(request, group_id, GROUPS_MANAGE)
        payload = PracticeGroupWriteSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            if "name" in data:
                with _refused("name"):
                    group = group_service.rename_group(group, data["name"])
            if "parent" in data:
                parent = _parent(group.practice, data["parent"])
                with _refused("parent"):
                    group = group_service.move_group(group, parent)
        return Response(_group_payload(group))

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_groups_delete",
        summary="Delete a group and its sub-groups",
        responses={204: None},
    )
    def delete(self, request: Request, group_id: uuid.UUID) -> Response:
        group = _group(request, group_id, GROUPS_MANAGE)
        group_service.delete_group(group)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupImpactView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_groups_impact",
        summary="What deleting a group affects",
        responses=PracticeGroupImpactSerializer,
    )
    def get(self, request: Request, group_id: uuid.UUID) -> Response:
        return Response(group_impact(_group(request, group_id, GROUPS_MANAGE)))


class GroupOrganisationsView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_groups_add_organisations",
        summary="File organisations in a group",
        request=PracticeOrganisationsSerializer,
        responses=PracticeCountSerializer,
    )
    def post(self, request: Request, group_id: uuid.UUID) -> Response:
        group = _group(request, group_id, GROUPS_MANAGE)
        organisations = _served(group.practice, _data(request).get("organisations"))
        before = OrgGroupMembership.objects.filter(group=group).count()
        with transaction.atomic(), _refused("organisations"):
            for organisation in organisations:
                group_service.add_organisation(group, organisation)
        return Response({"count": OrgGroupMembership.objects.filter(group=group).count() - before})


class GroupOrganisationView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_groups_remove_organisation",
        summary="Take an organisation out of a group",
        responses={204: None},
    )
    def delete(self, request: Request, group_id: uuid.UUID, org_id: uuid.UUID) -> Response:
        group = _group(request, group_id, GROUPS_MANAGE)
        organisation = Organisation.objects.filter(public_id=org_id).first()
        if organisation is None or not group_service.remove_organisation(group, organisation):
            raise NotFound
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupStaffView(APIView):
    required_feature = CORE

    def _member(self, group: OrgGroup, user_id: uuid.UUID) -> PracticeMember:
        member = PracticeMember.objects.filter(
            practice_id=group.practice_id, user__public_id=user_id
        ).first()
        if member is None:
            raise NotFound  # not a member of this practice: never named
        return member

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_groups_assign_staff",
        summary="Assign a staff member to a group, or change their role",
        request=PracticeStaffWriteSerializer,
        responses=PracticeGroupStaffSerializer,
    )
    def put(self, request: Request, group_id: uuid.UUID, user_id: uuid.UUID) -> Response:
        group = _group(request, group_id, GROUPS_MANAGE)
        payload = PracticeStaffWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        member = self._member(group, user_id)
        with _refused("role"):
            row = group_service.assign_staff(group, member, payload.validated_data["role"])
        return Response(
            {
                "user": member.user.public_id,
                "name": member.user.name,
                "email": member.user.email,
                "role": row.role,
                "inherited_from": None,
            }
        )

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_groups_unassign_staff",
        summary="Unassign a staff member from a group",
        responses={204: None},
    )
    def delete(self, request: Request, group_id: uuid.UUID, user_id: uuid.UUID) -> Response:
        group = _group(request, group_id, GROUPS_MANAGE)
        if not group_service.unassign_staff(group, self._member(group, user_id)):
            raise NotFound
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---- views: tags -------------------------------------------------------------------------------


class TagListView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_tags_list",
        summary="The practice's tags",
        parameters=[PRACTICE_PARAM],
        responses=PracticeTagListSerializer,
    )
    def get(self, request: Request) -> Response:
        practice = _practice(request, DIRECTORY_VIEW)
        return Response({"practice": practice.public_id, "tags": present_tags(practice)})

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_tags_create",
        summary="Create a tag",
        request=PracticeTagWriteSerializer,
        responses={201: PracticeTagSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = PracticeTagWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        practice = _practice(request, GROUPS_MANAGE)
        data = payload.validated_data
        with _refused("name"):
            tag = tag_service.create_tag(
                practice, data.get("name", ""), data.get("colour", TagColour.SLATE)
            )
        return Response(_tag_payload(tag, 0), status=status.HTTP_201_CREATED)


class TagDetailView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_tags_update",
        summary="Rename or recolour a tag",
        request=PracticeTagWriteSerializer,
        responses=PracticeTagSerializer,
    )
    def patch(self, request: Request, tag_id: uuid.UUID) -> Response:
        tag = _tag(request, tag_id, GROUPS_MANAGE)
        payload = PracticeTagWriteSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            if "name" in data:
                with _refused("name"):
                    tag = tag_service.rename_tag(tag, data["name"])
            if "colour" in data:
                with _refused("colour"):
                    tag = tag_service.recolour_tag(tag, data["colour"])
        return Response(_tag_payload(tag))

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_tags_delete", summary="Delete a tag", responses={204: None}
    )
    def delete(self, request: Request, tag_id: uuid.UUID) -> Response:
        tag_service.delete_tag(_tag(request, tag_id, GROUPS_MANAGE))
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagOrganisationsView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_tags_add_organisations",
        summary="Tag organisations",
        request=PracticeOrganisationsSerializer,
        responses=PracticeCountSerializer,
    )
    def post(self, request: Request, tag_id: uuid.UUID) -> Response:
        tag = _tag(request, tag_id, GROUPS_MANAGE)
        organisations = _served(tag.practice, _data(request).get("organisations"))
        before = OrgTag.objects.filter(tag=tag).count()
        with transaction.atomic(), _refused("organisations"):
            for organisation in organisations:
                tag_service.tag_organisation(tag, organisation)
        return Response({"count": OrgTag.objects.filter(tag=tag).count() - before})


class TagOrganisationView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.groups.manage (checked here)
    @checks_practice_permission(GROUPS_MANAGE.key)
    @extend_schema(
        operation_id="practice_tags_remove_organisation",
        summary="Remove a tag from an organisation",
        responses={204: None},
    )
    def delete(self, request: Request, tag_id: uuid.UUID, org_id: uuid.UUID) -> Response:
        tag = _tag(request, tag_id, GROUPS_MANAGE)
        organisation = Organisation.objects.filter(public_id=org_id).first()
        if organisation is None or not tag_service.untag_organisation(tag, organisation):
            raise NotFound
        return Response(status=status.HTTP_204_NO_CONTENT)
