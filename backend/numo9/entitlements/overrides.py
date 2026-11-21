"""Platform-owner product grants (U-03-T14): give an organisation a product for N days.

``EntitlementOverride`` rows (U-03-T03) are what the engine adds to an organisation's products
until they expire; this is the console's way to create and remove them:

- ``GET    platform/organisations/<org>/overrides`` — the organisation's grants, newest first, each
  active / expired / removed, and the products that can be granted (active, not free sets);
  ``platform.console.view``.
- ``POST   platform/organisations/<org>/overrides`` — ``{product, days (1–365), reason}``;
  ``platform.catalogue.manage``. Ends ``days`` × 24 h from now.
- ``DELETE platform/organisations/<org>/overrides/<id>`` — remove a grant now (kept, marked
  removed); ``platform.catalogue.manage``.

Every grant and removal is in the **organisation's** audit log (``AuditedModel``: created,
deleted, with the reason and who granted it) and bumps its entitlement cache at once.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, cast

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.catalogue.models import Product, ProductKind, ProductStatus
from numo9.catalogue.texts import product_name
from numo9.rbac.drf import requires_permission
from numo9.rbac.permissions import CATALOGUE_MANAGE, CONSOLE_VIEW
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .cache import bump_organisation
from .models import EntitlementOverride

MAX_DAYS = 365


def grantable_products() -> list[Product]:
    return list(
        Product.objects.filter(status=ProductStatus.ACTIVE)
        .exclude(kind=ProductKind.FREE_SET)
        .order_by("sort", "code")
    )


def _state(row: EntitlementOverride, now: dt.datetime) -> str:
    if row.deleted_at is not None:
        return "removed"
    return "active" if row.expires_at > now else "expired"


class OverrideSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    product = serializers.CharField(source="product.code")
    product_name = serializers.SerializerMethodField()
    expires_at = serializers.DateTimeField()
    reason = serializers.CharField()
    granted_by = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    removed_at = serializers.DateTimeField(source="deleted_at", allow_null=True)
    state = serializers.SerializerMethodField()

    def get_product_name(self, row: EntitlementOverride) -> str:
        return product_name(row.product.code)

    def get_granted_by(self, row: EntitlementOverride) -> str:
        user = row.granted_by
        return (user.name or user.email) if user is not None else ""

    def get_state(self, row: EntitlementOverride) -> str:
        return _state(row, timezone.now())


class GrantableProductSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()


class OverrideListSerializer(serializers.Serializer[Any]):
    overrides = OverrideSerializer(many=True)
    products = GrantableProductSerializer(many=True)
    max_days = serializers.IntegerField()


class GrantSerializer(serializers.Serializer[Any]):
    product = serializers.CharField()
    days = serializers.IntegerField(min_value=1, max_value=MAX_DAYS)
    reason = serializers.CharField(min_length=5, max_length=300, trim_whitespace=True)

    def validate_product(self, code: str) -> Product:
        product = next((p for p in grantable_products() if p.code == code), None)
        if product is None:
            raise serializers.ValidationError(
                _("Choose an active product (free products are always included).")
            )
        return product


def _organisation(org_id: Any) -> Organisation:
    organisation = Organisation.objects.filter(public_id=org_id).first()
    if organisation is None:
        raise NotFound
    return organisation


def _rows(organisation: Organisation) -> Any:
    return (
        EntitlementOverride._base_manager.filter(organisation_id=organisation.pk)
        .select_related("product", "granted_by")
        .order_by("-created_at", "-id")
    )


class OverrideListView(APIView):
    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_overrides_list",
        summary="An organisation's product grants and the products that can be granted",
        responses=OverrideListSerializer,
    )
    def get(self, request: Request, org_id: Any) -> Response:
        organisation = _organisation(org_id)
        body = {
            "overrides": list(_rows(organisation)),
            "products": [
                {"code": p.code, "name": product_name(p.code)} for p in grantable_products()
            ],
            "max_days": MAX_DAYS,
        }
        return Response(OverrideListSerializer(body).data)

    @requires_permission(CATALOGUE_MANAGE.key)
    @extend_schema(
        operation_id="platform_overrides_grant",
        summary="Grant a product for N days with a reason (in the organisation's audit log)",
        request=GrantSerializer,
        responses={201: OverrideSerializer},
    )
    def post(self, request: Request, org_id: Any) -> Response:
        organisation = _organisation(org_id)
        payload = GrantSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic(), org_context(organisation):
            row = EntitlementOverride(
                organisation=organisation,
                product=data["product"],
                granted_by=cast(User, request.user),
                expires_at=timezone.now() + dt.timedelta(days=data["days"]),
                reason=data["reason"],
            )
            row.save()
            bump_organisation(str(organisation.public_id))
        return Response(OverrideSerializer(row).data, status=status.HTTP_201_CREATED)


class OverrideDetailView(APIView):
    required_feature = CORE

    @requires_permission(CATALOGUE_MANAGE.key)
    @extend_schema(
        operation_id="platform_overrides_remove",
        summary="Remove a product grant now (kept as removed; audited)",
        responses={204: None},
    )
    def delete(self, request: Request, org_id: Any, public_id: Any) -> Response:
        organisation = _organisation(org_id)
        with transaction.atomic(), org_context(organisation):
            row = _rows(organisation).filter(public_id=public_id, deleted_at__isnull=True).first()
            if row is None:
                raise NotFound
            row.soft_delete()
            bump_organisation(str(organisation.public_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
