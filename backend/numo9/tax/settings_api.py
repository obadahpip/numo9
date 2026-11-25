"""Tax settings API (G-06-T07), under ``/api/v1/o/<org>/tax/``: everything the one tax settings
page edits.

- ``GET tax/settings`` — basis, rounding, quick method, default codes per side and account
  type, the restricted-ITC accounts, and whether the organisation is registered for GST/HST or
  QST. ``PATCH tax/settings`` ``{rounding_mode, quick_method, quick_method_from, default_codes,
  basis, basis_reason}`` — a basis change needs its reason (400 ``tax.settings.
  basis_reason_required``); the answer carries ``basis_warning`` for a change during the year.
- ``GET tax/settings/basis-check?basis=cash`` — what changing the basis today means.
- ``PUT tax/settings/restricted-itc/<account>`` ``{pct}`` — the share of the ITC an expense
  account may claim (50 for meals); ``null`` lifts the restriction.
- ``GET tax/registrations`` — the BN, program accounts, QST and provincial numbers, each with
  its filing summary (frequency, next return due, overdue count). ``POST`` adds one
  (``frequency`` for GST/HST and QST: the first cycle and periods are created, G-06-T04).
- ``GET / PATCH / DELETE tax/registrations/<id>`` — one registration; a change the filed
  periods forbid is a 422 ``tax.registration.filed_periods``.

Reading needs ``tax.codes.view``, changing ``tax.manage``. Every change is audited with its
author (the tax history, ``GET audit/events?scope=tax``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE, requires_feature
from numo9.ledger.models import Account
from numo9.orgsettings.api import RegistrationSerializer, drf_errors
from numo9.orgsettings.models import FILING_TYPES, TaxRegistration
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from . import registrations
from .filing import MONTHS
from .filing_api import _today
from .models import RoundingMode, TaxBasis, TaxError, TaxSettings
from .permissions import TAX_MANAGE, TAX_VIEW
from .settings import basis_change_check, change_basis, tax_settings


def _restricted() -> list[dict[str, Any]]:
    accounts = Account.objects.filter(
        itc_restriction_pct__isnull=False, deleted_at__isnull=True
    ).order_by("code")
    return [
        {
            "id": str(a.public_id),
            "code": a.code,
            "name": a.name,
            "pct": f"{a.itc_restriction_pct.normalize():f}",
        }
        for a in accounts
        if a.itc_restriction_pct is not None
    ]


def settings_body(row: TaxSettings) -> dict[str, Any]:
    registered = TaxRegistration.objects.filter(
        deleted_at__isnull=True, type__in=FILING_TYPES, status="active"
    ).exists()
    return {
        "basis": row.basis,
        "rounding_mode": row.rounding_mode,
        "quick_method": row.quick_method,
        "quick_method_from": row.quick_method_from.isoformat() if row.quick_method_from else None,
        "default_codes": row.default_codes or {},
        "restricted_itc_accounts": _restricted(),
        "registered": registered,
    }


class SettingsPatchSerializer(serializers.Serializer[Any]):
    basis = serializers.ChoiceField(choices=TaxBasis.choices, required=False)
    basis_reason = serializers.CharField(required=False, allow_blank=True)
    rounding_mode = serializers.ChoiceField(choices=RoundingMode.choices, required=False)
    quick_method = serializers.BooleanField(required=False)
    quick_method_from = serializers.DateField(required=False, allow_null=True)
    default_codes = serializers.DictField(required=False)


class TaxSettingsView(APIView):
    queryset = TaxSettings._base_manager.none()

    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_settings_get", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        return Response(settings_body(tax_settings(current_org())))

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_settings_update", request=SettingsPatchSerializer, responses={200: dict}
    )
    def patch(self, request: Request, org: Any) -> Response:
        from django.db import transaction

        payload = SettingsPatchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        organisation = current_org()
        warning = ""
        try:
            with transaction.atomic():
                basis = data.pop("basis", None)
                reason = data.pop("basis_reason", "")
                row = tax_settings(organisation)
                if basis is not None and basis != row.basis:
                    warning = basis_change_check(organisation, basis, _today())["warning"]
                    row = change_basis(
                        organisation, basis, reason, user=request.user, today=_today()
                    )
                if data:
                    for name, value in data.items():
                        setattr(row, name, value)
                    if data.get("quick_method") is False:
                        row.quick_method_from = None
                    row.full_clean(exclude=["organisation", "created_by", "public_id"])
                    row.save()
        except DjangoValidationError as error:
            raise drf_errors(error) from None
        return Response({**settings_body(row), "basis_warning": warning})


class TaxBasisCheckView(APIView):
    queryset = TaxSettings._base_manager.none()

    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_settings_basis_check", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        basis = request.query_params.get("basis", "")
        if basis not in TaxBasis.values:
            raise serializers.ValidationError({"basis": ["Choose accrual or cash."]})
        return Response(basis_change_check(current_org(), basis, _today()))


class RestrictedItcSerializer(serializers.Serializer[Any]):
    pct = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"),
        allow_null=True,
    )  # fmt: skip


class TaxRestrictedItcView(APIView):
    queryset = Account._base_manager.none()

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_settings_restricted_itc",
        request=RestrictedItcSerializer,
        responses={200: dict},
    )
    def put(self, request: Request, org: Any, public_id: Any) -> Response:
        account = Account.objects.filter(public_id=public_id, deleted_at__isnull=True).first()
        if account is None:
            raise NotFound
        payload = RestrictedItcSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        account.itc_restriction_pct = payload.validated_data["pct"]
        try:
            account.save()
        except DjangoValidationError as error:
            raise drf_errors(error) from None
        return Response({"restricted_itc_accounts": _restricted()})


# ---- registrations --------------------------------------------------------------------------


class RegistrationInputSerializer(RegistrationSerializer):
    frequency = serializers.ChoiceField(choices=sorted(MONTHS), required=False, write_only=True)

    class Meta(RegistrationSerializer.Meta):
        fields = (*RegistrationSerializer.Meta.fields, "frequency")  # type: ignore[assignment]


def registration_body(row: TaxRegistration) -> dict[str, Any]:
    body = dict(RegistrationSerializer(row).data)
    body["files_returns"] = row.files_returns
    body["filing"] = registrations.summary(row, _today())
    return body


def _registration(public_id: Any) -> TaxRegistration:
    row: TaxRegistration | None = TaxRegistration.objects.filter(
        public_id=public_id, deleted_at__isnull=True
    ).first()
    if row is None:
        raise NotFound
    return row


def _refused(error: TaxError) -> Response:
    return Response(
        {"code": getattr(error, "code", None) or "invalid", "detail": " ".join(error.messages)},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


class TaxRegistrationListView(APIView):
    queryset = TaxRegistration._base_manager.none()

    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_registrations_list", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        rows = TaxRegistration.objects.filter(deleted_at__isnull=True).order_by(
            "type", "effective_from", "pk"
        )
        return Response({"results": [registration_body(row) for row in rows]})

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_registrations_add",
        request=RegistrationInputSerializer,
        responses={201: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = RegistrationInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            row = registrations.create_registration(
                current_org(), user=request.user, today=_today(), **payload.validated_data
            )
        except TaxError as error:
            return _refused(error)
        except DjangoValidationError as error:
            raise drf_errors(error) from None
        return Response(registration_body(row), status=status.HTTP_201_CREATED)


class TaxRegistrationDetailView(APIView):
    queryset = TaxRegistration._base_manager.none()

    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_registrations_get", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(registration_body(_registration(public_id)))

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_registrations_update",
        request=RegistrationInputSerializer,
        responses={200: dict},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        row = _registration(public_id)
        payload = RegistrationInputSerializer(row, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        if "type" in data and data.pop("type") != row.type:
            raise serializers.ValidationError({"type": ["A registration's type can't change."]})
        try:
            registrations.update_registration(row, user=request.user, today=_today(), **data)
        except TaxError as error:
            return _refused(error)
        except DjangoValidationError as error:
            raise drf_errors(error) from None
        return Response(registration_body(row))

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_registrations_remove", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        try:
            registrations.remove_registration(_registration(public_id), user=request.user)
        except TaxError as error:
            return _refused(error)
        return Response(status=status.HTTP_204_NO_CONTENT)
