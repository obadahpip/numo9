"""Tenancy API (A-01-T13).

- ``GET  /api/v1/me/organisations`` — every organisation the signed-in user can access, with the
  user's own membership and the practices that give access (resolver of A-01-T05).
- ``POST /api/v1/practices`` — create a practice; the creator becomes its practice admin.
- ``POST /api/v1/organisations`` — create an organisation (status *trial*). For a practice the
  user belongs to: the practice is assigned and the user is named as assigned staff (an accountant
  creating a client's organisation; the owner is invited later, A-02-T09). Without a practice:
  the user becomes its owner.

None of these is organisation-scoped; they are on the tenant-sweep exempt list.
"""

from __future__ import annotations

from typing import Any, cast

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.i18n.errors import UNKNOWN_PRACTICE, error_detail

from .access import PRACTICE_WIDE_ROLES, accessible_organisations
from .models import (
    AssignmentRole,
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)
from .serializers import (
    MyOrganisationSerializer,
    OrganisationCreateSerializer,
    PracticeCreateSerializer,
    PracticeSerializer,
)


def _user(request: Request) -> User:
    """The signed-in user (every view here requires authentication)."""
    return cast(User, request.user)


def _describe(organisation: Organisation, user: Any) -> dict[str, Any]:
    membership = OrganisationMember.objects.filter(organisation=organisation, user=user).first()
    via: list[dict[str, Any]] = []
    assignments = (
        PracticeAssignment.objects.filter(
            organisation=organisation, active=True, practice__members__user=user
        )
        .select_related("practice")
        .order_by("practice__name")
        .distinct()
    )
    for assignment in assignments:
        member = PracticeMember.objects.get(practice=assignment.practice, user=user)
        is_staff = assignment.assigned_staff.filter(pk=member.pk).exists()
        if member.role in PRACTICE_WIDE_ROLES or is_staff:
            via.append(
                {
                    "practice_id": assignment.practice.public_id,
                    "practice_name": assignment.practice.name,
                    "practice_role": member.role,
                    "assignment_role": assignment.role,
                    "assigned_staff": is_staff,
                }
            )
    return {
        "public_id": organisation.public_id,
        "name": organisation.name,
        "status": organisation.status,
        "time_zone": organisation.time_zone,
        "locale": organisation.locale,
        "membership": {"role": membership.role} if membership else None,
        "via_practices": via,
    }


class MyOrganisationsView(APIView):
    @extend_schema(
        operation_id="me_organisations_list",
        summary="Organisations I can access",
        responses=MyOrganisationSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        organisations = accessible_organisations(request.user).order_by("name", "pk")
        data = [_describe(org, request.user) for org in organisations]
        return Response(MyOrganisationSerializer(data, many=True).data)


class PracticeCreateView(APIView):
    @extend_schema(
        operation_id="practices_create",
        summary="Create a practice (the creator becomes practice admin)",
        request=PracticeCreateSerializer,
        responses={201: PracticeSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = PracticeCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        with transaction.atomic():
            practice = Practice.objects.create(name=payload.validated_data["name"])
            PracticeMember.objects.create(
                practice=practice, user=_user(request), role=PracticeRole.PRACTICE_ADMIN
            )
        body = {"public_id": practice.public_id, "name": practice.name, "role": "practice_admin"}
        return Response(PracticeSerializer(body).data, status=status.HTTP_201_CREATED)


class OrganisationCreateView(APIView):
    @extend_schema(
        operation_id="organisations_create",
        summary="Create an organisation (trial)",
        request=OrganisationCreateSerializer,
        responses={201: MyOrganisationSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = OrganisationCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        member = None
        if data.get("practice"):
            member = (
                PracticeMember.objects.filter(
                    practice__public_id=data["practice"], user=_user(request)
                )
                .select_related("practice")
                .first()
            )
            if member is None:  # unknown practice or not a member: same answer
                raise serializers.ValidationError({"practice": [error_detail(UNKNOWN_PRACTICE)]})
        with transaction.atomic():
            organisation = Organisation.objects.create(
                name=data["name"],
                time_zone=data["time_zone"],
                locale=data["locale"],
                status=OrganisationStatus.TRIAL,
            )
            if member is not None:
                assignment = PracticeAssignment.objects.create(
                    practice=member.practice,
                    organisation=organisation,
                    role=AssignmentRole.FULL_SERVICE,
                )
                assignment.assigned_staff.add(member)
            else:
                OrganisationMember.objects.create(
                    organisation=organisation, user=_user(request), role=OrganisationRole.OWNER
                )
        body = _describe(organisation, request.user)
        return Response(MyOrganisationSerializer(body).data, status=status.HTTP_201_CREATED)
