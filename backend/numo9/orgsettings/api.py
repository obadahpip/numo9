"""Organisation settings API (A-05), under ``/api/v1/o/<org>/settings``.

Reading needs ``organisation.profile.view`` (every role); changing ``organisation.settings.manage``
(owners, admins). Models validate and audit every change; their errors come back as 400 with the
field and the code (``orgsettings.*``). Another organisation's registration is a 404 (A-05-T09):

- ``settings`` — GET / PATCH the organisation's settings (``base_currency`` is CAD, read-only);
- ``settings/registrations`` — GET list, POST add; ``settings/registrations/<id>`` — GET,
  PATCH, DELETE (soft);
- ``settings/lock-dates`` — GET every module × level (date, reason, last change); PATCH
  ``{"module", "level", "date" | null, "reason"}`` sets, moves or removes one (moving back needs
  a reason);
- ``settings/numbering`` — GET every document type's sequence (prefix, next number, padding,
  preview); PATCH ``{"doc_type", …}`` changes one;

- ``settings/lock-dates/impact?module=gl&date=2026-03-31`` — GET what a lock at that date would
  leave not posted (A-05-T07): ``{"module", "date", "items": [{"module", "kind", "label",
  "count"}], "total"}``; permission ``organisation.settings.manage`` (it is asked before changing a
  lock).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.core.exceptions import NON_FIELD_ERRORS
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ErrorDetail, NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .impact import impact
from .models import (
    DocType,
    LockDate,
    LockLevel,
    LockModule,
    NumberingSequence,
    OrganisationSettings,
    TaxRegistration,
)
from .numbering import get_sequence
from .service import get_settings

VIEW = "organisation.profile.view"
MANAGE = "organisation.settings.manage"


class ImpactItemSerializer(serializers.Serializer[Any]):
    module = serializers.CharField()
    kind = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]  # the field, not Field.label
    count = serializers.IntegerField()


class ImpactSerializer(serializers.Serializer[Any]):
    module = serializers.ChoiceField(choices=LockModule.choices)
    date = serializers.DateField()
    items = ImpactItemSerializer(many=True, read_only=True)
    total = serializers.IntegerField(read_only=True)


class ImpactQuerySerializer(serializers.Serializer[Any]):
    module = serializers.ChoiceField(choices=LockModule.choices)
    date = serializers.DateField()


class LockImpactView(APIView):
    required_feature = CORE
    serializer_class = ImpactSerializer

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="settings_lock_impact",
        summary="Records not posted that a lock at this date would leave behind",
        parameters=[
            OpenApiParameter("module", OpenApiTypes.STR, enum=LockModule.values),
            OpenApiParameter("date", OpenApiTypes.DATE),
        ],
        responses=ImpactSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        query = ImpactQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        module: str = query.validated_data["module"]
        date: dt.date = query.validated_data["date"]
        organisation = current_org()
        assert organisation is not None  # noqa: S101 — set by the tenant middleware for /o/<org>/
        items = impact(organisation, module, date)
        return Response(
            {
                "module": module,
                "date": date.isoformat(),
                "items": [item.__dict__ for item in items],
                "total": sum(item.count for item in items),
            }
        )


# ---- settings, registrations, lock dates, numbering (A-05-T09) -------------------------------


def drf_errors(error: DjangoValidationError) -> serializers.ValidationError:
    """A model's ValidationError as a DRF 400 with each message's code kept."""
    if hasattr(error, "error_dict"):
        body: dict[str, list[ErrorDetail]] = {}
        for field, items in error.error_dict.items():
            key = "non_field_errors" if field == NON_FIELD_ERRORS else field
            body[key] = [
                ErrorDetail(str(message), code=getattr(item, "code", None) or "invalid")
                for item in items
                for message in item.messages
            ]
        return serializers.ValidationError(body)
    return serializers.ValidationError(
        {"non_field_errors": [ErrorDetail(str(m), code="invalid") for m in error.messages]}
    )


def _save(row: Any) -> None:
    try:
        row.save()
    except DjangoValidationError as error:
        raise drf_errors(error) from None


class OrganisationSettingsSerializer(serializers.ModelSerializer[OrganisationSettings]):
    printed_name = serializers.CharField(read_only=True)

    class Meta:
        model = OrganisationSettings
        exclude = ("id", "organisation", "created_by", "deleted_at", "public_id")
        read_only_fields = ("base_currency", "created_at", "updated_at", "printed_name")

    def run_validators(self, value: Any) -> None:  # model rules run on save (all errors at once)
        return None

    def build_standard_field(self, field_name: str, model_field: Any) -> Any:
        cls, kwargs = super().build_standard_field(field_name, model_field)
        kwargs.pop("validators", None)  # the model validates (with its own codes) on save
        return cls, kwargs


class SettingsView(APIView):
    required_feature = CORE
    serializer_class = OrganisationSettingsSerializer

    @requires_permission(VIEW)
    @extend_schema(operation_id="settings_get", responses=OrganisationSettingsSerializer)
    def get(self, request: Request, org: Any) -> Response:
        return Response(OrganisationSettingsSerializer(get_settings()).data)

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="settings_update",
        summary="Change organisation settings (validated by the model; every change audited)",
        request=OrganisationSettingsSerializer,
        responses=OrganisationSettingsSerializer,
    )
    def patch(self, request: Request, org: Any) -> Response:
        row = get_settings()
        payload = OrganisationSettingsSerializer(row, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        for name, value in payload.validated_data.items():
            setattr(row, name, value)
        _save(row)
        return Response(OrganisationSettingsSerializer(row).data)


class RegistrationSerializer(serializers.ModelSerializer[TaxRegistration]):
    id = serializers.UUIDField(source="public_id", read_only=True)
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    display_number = serializers.CharField(read_only=True)

    class Meta:
        model = TaxRegistration
        fields = (
            "id", "type", "type_label", "number", "display_number", "effective_from",
            "effective_to", "status", "status_label", "cra_approval_ref", "created_at",
            "updated_at",
        )  # fmt: skip
        read_only_fields = ("created_at", "updated_at")

    def build_standard_field(self, field_name: str, model_field: Any) -> Any:
        cls, kwargs = super().build_standard_field(field_name, model_field)
        kwargs.pop("validators", None)
        return cls, kwargs


def _registration(public_id: Any) -> TaxRegistration:
    row: TaxRegistration | None = TaxRegistration.objects.filter(
        public_id=public_id, deleted_at__isnull=True
    ).first()
    if row is None:
        raise NotFound
    return row


class RegistrationListView(APIView):
    required_feature = CORE
    serializer_class = RegistrationSerializer

    @requires_permission(VIEW)
    @extend_schema(
        operation_id="settings_registrations_list", responses=RegistrationSerializer(many=True)
    )
    def get(self, request: Request, org: Any) -> Response:
        rows = TaxRegistration.objects.filter(deleted_at__isnull=True).order_by(
            "type", "effective_from", "pk"
        )
        return Response(RegistrationSerializer(rows, many=True).data)

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="settings_registrations_add",
        request=RegistrationSerializer,
        responses={201: RegistrationSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = RegistrationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = TaxRegistration(organisation=current_org(), **payload.validated_data)
        _save(row)
        return Response(RegistrationSerializer(row).data, status=status.HTTP_201_CREATED)


class RegistrationDetailView(APIView):
    required_feature = CORE
    serializer_class = RegistrationSerializer

    @requires_permission(VIEW)
    @extend_schema(operation_id="settings_registrations_get", responses=RegistrationSerializer)
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(RegistrationSerializer(_registration(public_id)).data)

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="settings_registrations_update",
        request=RegistrationSerializer,
        responses=RegistrationSerializer,
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        row = _registration(public_id)
        payload = RegistrationSerializer(row, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        for name, value in payload.validated_data.items():
            setattr(row, name, value)
        _save(row)
        return Response(RegistrationSerializer(row).data)

    @requires_permission(MANAGE)
    @extend_schema(operation_id="settings_registrations_remove", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        _registration(public_id).soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LockLevelSerializer(serializers.Serializer[Any]):
    date = serializers.DateField(allow_null=True)
    reason = serializers.CharField(allow_blank=True)
    updated_at = serializers.DateTimeField(allow_null=True)


class LockRowSerializer(serializers.Serializer[Any]):
    module = serializers.ChoiceField(choices=LockModule.choices)
    module_label = serializers.CharField()
    advisers_only = LockLevelSerializer()
    everyone = LockLevelSerializer()


class LockChangeSerializer(serializers.Serializer[Any]):
    module = serializers.ChoiceField(choices=LockModule.choices)
    level = serializers.ChoiceField(choices=LockLevel.choices)
    date = serializers.DateField(allow_null=True)
    reason = serializers.CharField(allow_blank=True, required=False, default="", max_length=500)


def lock_matrix() -> list[dict[str, Any]]:
    rows = {(r.module, r.level): r for r in LockDate.objects.filter(deleted_at__isnull=True)}
    matrix = []
    for module in LockModule:
        entry: dict[str, Any] = {"module": module.value, "module_label": str(module.label)}
        for level in LockLevel:
            row = rows.get((module.value, level.value))
            entry[level.value] = {
                "date": row.date.isoformat() if row and row.date else None,
                "reason": row.reason if row else "",
                "updated_at": row.updated_at.isoformat() if row else None,
            }
        matrix.append(entry)
    return matrix


def _tell_admins(lock: LockDate, actor: Any) -> None:
    """Flow F6: the organisation's owners and admins are told a lock date changed."""
    from numo9.notifications.services import notify
    from numo9.tenancy.models import OrganisationMember

    organisation = lock.organisation
    admins = [
        member.user
        for member in OrganisationMember.objects.filter(
            organisation=organisation, role__in=("owner", "admin")
        ).select_related("user")
        if member.user_id != getattr(actor, "pk", None)
    ]
    notify(
        "settings.lock_changed",
        admins,
        organisation=organisation,
        params={
            "module": str(LockModule(lock.module).label),
            "level": str(LockLevel(lock.level).label).lower(),
            "date": lock.date.isoformat() if lock.date else "—",
            "person": getattr(actor, "name", "") or getattr(actor, "email", ""),
        },
        link=f"/o/{organisation.public_id}/settings/lock-dates",
    )


class LockDatesView(APIView):
    required_feature = CORE
    serializer_class = LockChangeSerializer

    @requires_permission(VIEW)
    @extend_schema(
        operation_id="settings_lock_dates",
        summary="Lock dates: every module × level",
        responses=LockRowSerializer(many=True),
    )
    def get(self, request: Request, org: Any) -> Response:
        return Response(lock_matrix())

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="settings_lock_dates_set",
        summary="Set, move or remove one lock date (moving back needs a reason; audited)",
        request=LockChangeSerializer,
        responses=LockRowSerializer(many=True),
    )
    def patch(self, request: Request, org: Any) -> Response:
        payload = LockChangeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        row = LockDate.objects.filter(
            module=data["module"], level=data["level"], deleted_at__isnull=True
        ).first() or LockDate(
            organisation=current_org(), module=data["module"], level=data["level"]
        )
        before = (row.date, row.reason)
        row.set_lock(data["date"], data["reason"])
        _save(row)
        if before[0] != row.date:
            _tell_admins(row, request.user)
        return Response(lock_matrix())


class NumberingSerializer(serializers.ModelSerializer[NumberingSequence]):
    doc_type_label = serializers.CharField(source="get_doc_type_display", read_only=True)
    preview = serializers.CharField(read_only=True)

    class Meta:
        model = NumberingSequence
        fields = ("doc_type", "doc_type_label", "prefix", "next_number", "padding", "preview")
        read_only_fields = ("doc_type",)

    def build_standard_field(self, field_name: str, model_field: Any) -> Any:
        cls, kwargs = super().build_standard_field(field_name, model_field)
        kwargs.pop("validators", None)
        return cls, kwargs


class NumberingChangeSerializer(serializers.Serializer[Any]):
    doc_type = serializers.ChoiceField(choices=DocType.choices)
    prefix = serializers.CharField(required=False, allow_blank=True)
    next_number = serializers.IntegerField(required=False)
    padding = serializers.IntegerField(required=False)


class NumberingView(APIView):
    required_feature = CORE
    serializer_class = NumberingChangeSerializer

    @requires_permission(VIEW)
    @extend_schema(operation_id="settings_numbering", responses=NumberingSerializer(many=True))
    def get(self, request: Request, org: Any) -> Response:
        rows = [get_sequence(doc_type) for doc_type in DocType.values]
        return Response(NumberingSerializer(rows, many=True).data)

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="settings_numbering_update",
        summary="Change one document type's prefix, next number or padding",
        request=NumberingChangeSerializer,
        responses=NumberingSerializer,
    )
    def patch(self, request: Request, org: Any) -> Response:
        payload = NumberingChangeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        row = get_sequence(data.pop("doc_type"))
        for name, value in data.items():
            setattr(row, name, value)
        _save(row)
        return Response(NumberingSerializer(row).data)
