"""Invitation API (A-02-T09) over ``numo9.tenancy.invitations``.

- ``POST /api/v1/invitations`` — create and email (body: kind, email, role, and ``practice`` or
  ``organisation`` public id). An unknown target and a target the user may not invite to get the
  same 403, so ids can't be probed.
- ``POST /api/v1/invitations/<id>/resend`` · ``POST /api/v1/invitations/<id>/revoke`` — 404
  unless the user sent the invitation or may send it.
- ``POST /api/v1/invitations/preview`` ``{token}`` — anyone holding the link: what it invites to
  (for the accept screen, A-02-T12); 404 invalid, 410 used/revoked/expired.
- ``POST /api/v1/invitations/accept`` ``{token, practice?}`` — signed in; bound to the invited
  email (403 ``invitation.wrong_account`` otherwise).

The link token travels in the request body, never in a URL, so it does not reach access logs.
These routes are not organisation-scoped (a practice invitation has no organisation); they are on
the tenant-sweep exempt list and every object is checked by the service.
"""

from __future__ import annotations

from typing import Any, cast

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.i18n import errors
from numo9.i18n.errors import api_error

from . import invitations as service
from .models import (
    AssignmentRole,
    Invitation,
    InvitationKind,
    Organisation,
    OrganisationRole,
    Practice,
    PracticeRole,
)

ALL_ROLES = sorted({*PracticeRole.values, *OrganisationRole.values, *AssignmentRole.values})


class InvitationCreateSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=InvitationKind.choices)
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(
        choices=ALL_ROLES,
        required=False,
        help_text="Practice role, organisation role, or assignment role (organisation_accountant).",
    )
    practice = serializers.UUIDField(required=False, help_text="Target of practice_staff.")
    organisation = serializers.UUIDField(required=False, help_text="Target of organisation_*.")


class InvitationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    kind = serializers.ChoiceField(choices=InvitationKind.choices)
    email = serializers.EmailField()
    role = serializers.CharField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()
    target_name = serializers.CharField(source="target.name")
    target_id = serializers.UUIDField(source="target.public_id")
    inviter_name = serializers.CharField(source="inviter.name")


class TokenSerializer(serializers.Serializer[Any]):
    token = serializers.CharField(max_length=128)


class AcceptSerializer(TokenSerializer):
    practice = serializers.UUIDField(
        required=False,
        help_text="organisation_accountant: which of your practices serves the organisation.",
    )


def _user(request: Request) -> User:
    return cast(User, request.user)


def _target(kind: str, data: dict[str, Any]) -> Practice | Organisation:
    if kind == InvitationKind.PRACTICE_STAFF:
        practice = Practice.objects.filter(public_id=str(data.get("practice") or "")).first()
        if practice is not None:
            return practice
    else:
        organisation = Organisation.objects.filter(
            public_id=str(data.get("organisation") or "")
        ).first()
        if organisation is not None:
            return organisation
    raise api_error(errors.INVITATION_NOT_ALLOWED)  # unknown target: same answer as no right


def _default_role(kind: str) -> str:
    defaults: dict[str, str] = {
        InvitationKind.PRACTICE_STAFF: PracticeRole.ACCOUNTANT,
        InvitationKind.ORGANISATION_OWNER: OrganisationRole.OWNER,
        InvitationKind.ORGANISATION_USER: OrganisationRole.EMPLOYEE,
        InvitationKind.ORGANISATION_ACCOUNTANT: AssignmentRole.FULL_SERVICE,
    }
    return defaults[kind]


def _valid_role(kind: str, role: str) -> bool:
    allowed: dict[str, list[str]] = {
        InvitationKind.PRACTICE_STAFF: PracticeRole.values,
        InvitationKind.ORGANISATION_OWNER: [OrganisationRole.OWNER],
        InvitationKind.ORGANISATION_USER: OrganisationRole.values,
        InvitationKind.ORGANISATION_ACCOUNTANT: AssignmentRole.values,
    }
    return role in allowed[kind]


class InvitationCreateView(APIView):
    @extend_schema(
        operation_id="invitations_create",
        summary="Invite someone to a practice or an organisation (emails a single-use link)",
        request=InvitationCreateSerializer,
        responses={201: InvitationSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = InvitationCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        kind = data["kind"]
        role = data.get("role") or _default_role(kind)
        if not _valid_role(kind, role):
            raise serializers.ValidationError(
                {"role": [errors.error_detail(errors.INVITATION_ROLE_INVALID)]}
            )
        issued = service.create(
            inviter=_user(request),
            kind=kind,
            email=data["email"],
            role=role,
            target=_target(kind, data),
        )
        return Response(InvitationSerializer(issued.invitation).data, status.HTTP_201_CREATED)


class _ManageView(APIView):
    def _invitation(self, request: Request, invitation_id: Any) -> Invitation:
        invitation = (
            Invitation.objects.filter(public_id=invitation_id)
            .select_related("practice", "organisation", "inviter")
            .first()
        )
        if invitation is None or not service.can_manage(_user(request), invitation):
            raise api_error(errors.INVITATION_INVALID)  # 404: nothing about foreign invitations
        return invitation


class InvitationResendView(_ManageView):
    @extend_schema(
        operation_id="invitations_resend",
        summary="Send again with a new link and a fresh 7-day expiry",
        request=None,
        responses=InvitationSerializer,
    )
    def post(self, request: Request, invitation_id: Any) -> Response:
        issued = service.resend(self._invitation(request, invitation_id), by=_user(request))
        return Response(InvitationSerializer(issued.invitation).data)


class InvitationRevokeView(_ManageView):
    @extend_schema(
        operation_id="invitations_revoke",
        summary="Withdraw a pending invitation (its link stops working)",
        request=None,
        responses=InvitationSerializer,
    )
    def post(self, request: Request, invitation_id: Any) -> Response:
        invitation = service.revoke(self._invitation(request, invitation_id), by=_user(request))
        return Response(InvitationSerializer(invitation).data)


class InvitationPreviewView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="invitations_preview",
        summary="What an invitation link invites to (accept screen)",
        request=TokenSerializer,
        responses=InvitationSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = TokenSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        invitation = service.lookup(payload.validated_data["token"])
        return Response(InvitationSerializer(invitation).data)


class InvitationAcceptView(APIView):
    @extend_schema(
        operation_id="invitations_accept",
        summary="Accept an invitation as the signed-in user (must be the invited email)",
        request=AcceptSerializer,
        responses=InvitationSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = AcceptSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        practice = None
        if payload.validated_data.get("practice"):
            practice = Practice.objects.filter(public_id=payload.validated_data["practice"]).first()
            if practice is None:
                raise serializers.ValidationError(
                    {"practice": [errors.error_detail(errors.UNKNOWN_PRACTICE)]}
                )
        invitation = service.accept(
            payload.validated_data["token"], _user(request), practice=practice
        )
        return Response(InvitationSerializer(invitation).data)
