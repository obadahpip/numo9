"""Packages API for the platform console (U-02-T07), mounted under ``/api/v1/``.

Platform owner only (``platform.catalogue.manage``; everyone else 403 with "why can't I?"):

- ``platform/packages`` — GET every package (draft, active, retired) with products, price
  versions, current prices and subscriber count; POST a new draft package;
- ``platform/packages/<code>`` — GET one; PATCH texts, products, limits, founding flag, order;
  DELETE a draft nobody subscribes to (409 otherwise: retire it instead);
- ``platform/packages/<code>/activate`` · ``…/retire`` — POST the status change (409 when the
  rules refuse it);
- ``platform/packages/<code>/prices`` — POST a new price version (interval, amount in cents,
  start date): the version in force then ends on that date;
- ``platform/packages/<code>/prices/impact?interval=&effective_from=`` — GET how many
  subscriptions a price starting that day affects at their next renewal (the console dialog);
- ``platform/packages/<code>/prices/<id>`` — DELETE a version that hasn't started;
- ``platform/packages/promo-codes`` — GET every promo code, POST a new one;
- ``platform/packages/promo-codes/<code>`` — GET one; PATCH description, maximum, expiry,
  packages; ``…/expire`` — POST to end it now.

Validation errors come back in field form (``{"field": ["message"]}``, codes on each message).
Platform routes: no organisation, no feature key; every change is in the platform audit log.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Prefetch, QuerySet
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import requires_permission
from numo9.rbac.permissions import CATALOGUE_MANAGE

from . import presenter, promos, services
from .models import Package, PackagePrice, PromoCode, normalise_promo_code
from .serializers import (
    PackageCreateSerializer,
    PackageUpdateSerializer,
    PlatformPackageListSerializer,
    PlatformPackageSerializer,
    PriceCreatedSerializer,
    PriceCreateSerializer,
    PriceImpactQuerySerializer,
    PriceImpactSerializer,
    PromoCreateSerializer,
    PromoListSerializer,
    PromoSerializer,
    PromoUpdateSerializer,
)
from .subscriptions import get_source

MANAGE = CATALOGUE_MANAGE.key


def _packages() -> QuerySet[Package]:
    return Package.objects.prefetch_related(
        "products", Prefetch("prices", queryset=PackagePrice.objects.order_by("effective_from"))
    )


def _package(code: str) -> Package:
    package = _packages().filter(code=code).first()
    if package is None:
        raise api_error(errors.PACKAGE_NOT_FOUND)
    return package


def _detail(package: Package) -> dict[str, Any]:
    return dict(PlatformPackageSerializer(presenter.package_data(_package(package.code))).data)


def _promo(code: str) -> PromoCode:
    promo = (
        PromoCode.objects.prefetch_related("packages")
        .filter(code=normalise_promo_code(code))
        .first()
    )
    if promo is None:
        raise api_error(errors.PROMO_NOT_FOUND)
    return promo


# ---- packages ---------------------------------------------------------------------------------


class PackageListView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_list",
        summary="Every package with its products, price versions and subscriber count",
        responses=PlatformPackageListSerializer,
    )
    def get(self, request: Request) -> Response:
        rows = [presenter.package_data(p) for p in _packages().order_by("sort", "code")]
        return Response(PlatformPackageListSerializer({"packages": rows}).data)

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_create",
        summary="Create a draft package",
        request=PackageCreateSerializer,
        responses={201: PlatformPackageSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = PackageCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        package = services.create_package(dict(payload.validated_data), actor=request.user)
        return Response(_detail(package), status=status.HTTP_201_CREATED)


class PackageDetailView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(operation_id="platform_packages_retrieve", responses=PlatformPackageSerializer)
    def get(self, request: Request, code: str) -> Response:
        return Response(_detail(_package(code)))

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_update",
        summary="Change texts, products, limits, founding flag or order",
        request=PackageUpdateSerializer,
        responses=PlatformPackageSerializer,
    )
    def patch(self, request: Request, code: str) -> Response:
        package = _package(code)
        payload = PackageUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        services.update_package(package, dict(payload.validated_data), actor=request.user)
        return Response(_detail(package))

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_destroy",
        summary="Delete a draft package nobody subscribes to (409 otherwise)",
        responses={204: None},
    )
    def delete(self, request: Request, code: str) -> Response:
        services.delete_package(_package(code), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PackageActivateView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_activate",
        summary="Offer the package at sign-up (needs at least one product)",
        request=None,
        responses=PlatformPackageSerializer,
    )
    def post(self, request: Request, code: str) -> Response:
        return Response(_detail(services.activate(_package(code), actor=request.user)))


class PackageRetireView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_retire",
        summary="Hide the package from sign-up; subscribers keep it",
        request=None,
        responses=PlatformPackageSerializer,
    )
    def post(self, request: Request, code: str) -> Response:
        return Response(_detail(services.retire(_package(code), actor=request.user)))


# ---- prices -----------------------------------------------------------------------------------


class PriceListView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_prices_create",
        summary="Schedule a new price version (the version in force then ends on its start)",
        request=PriceCreateSerializer,
        responses={201: PriceCreatedSerializer},
    )
    def post(self, request: Request, code: str) -> Response:
        package = _package(code)
        payload = PriceCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        price = services.schedule_price(
            package,
            interval=data["interval"],
            amount_cents=data["amount_cents"],
            effective_from=data["effective_from"],
            actor=request.user,
        )
        detail = presenter.package_data(_package(code))
        body = {
            "price": presenter.price_data(price, timezone.localdate()),
            "affected_subscriptions": get_source().affected_by_price(
                package, price.interval, price.effective_from
            ),
            "package": detail,
        }
        return Response(PriceCreatedSerializer(body).data, status=status.HTTP_201_CREATED)


class PriceImpactView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_prices_impact",
        summary="Subscriptions a price starting on a date affects at their next renewal",
        parameters=[PriceImpactQuerySerializer],
        responses=PriceImpactSerializer,
    )
    def get(self, request: Request, code: str) -> Response:
        package = _package(code)
        query = PriceImpactQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        interval = query.validated_data["interval"]
        start = query.validated_data["effective_from"]
        before = start - timedelta(days=1)
        current = next(
            (p for p in package.prices.all() if p.interval == interval and p.covers(before)), None
        )
        body = {
            "affected_subscriptions": get_source().affected_by_price(package, interval, start),
            "current": presenter.price_data(current, before) if current else None,
        }
        return Response(PriceImpactSerializer(body).data)


class PriceDetailView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_packages_prices_destroy",
        summary="Delete a price version that hasn't started (409 once it has)",
        parameters=[OpenApiParameter("price_id", str, OpenApiParameter.PATH)],
        responses={204: None},
    )
    def delete(self, request: Request, code: str, price_id: Any) -> Response:
        package = _package(code)
        price = PackagePrice.objects.filter(package=package, public_id=price_id).first()
        if price is None:
            raise api_error(errors.PRICE_NOT_FOUND)
        services.delete_scheduled_price(price, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---- promo codes ------------------------------------------------------------------------------


class PromoListView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_promo_codes_list",
        summary="Every promo code with its usage and status",
        responses=PromoListSerializer,
    )
    def get(self, request: Request) -> Response:
        rows = [presenter.promo_data(p) for p in PromoCode.objects.prefetch_related("packages")]
        return Response(PromoListSerializer({"promo_codes": rows}).data)

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_promo_codes_create",
        summary="Create a promo code",
        request=PromoCreateSerializer,
        responses={201: PromoSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = PromoCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        promo = promos.create_promo(dict(payload.validated_data), actor=request.user)
        return Response(
            PromoSerializer(presenter.promo_data(_promo(promo.code))).data,
            status=status.HTTP_201_CREATED,
        )


class PromoDetailView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(operation_id="platform_promo_codes_retrieve", responses=PromoSerializer)
    def get(self, request: Request, code: str) -> Response:
        return Response(PromoSerializer(presenter.promo_data(_promo(code))).data)

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_promo_codes_update",
        summary="Change the description, maximum uses, expiry or packages",
        request=PromoUpdateSerializer,
        responses=PromoSerializer,
    )
    def patch(self, request: Request, code: str) -> Response:
        promo = _promo(code)
        payload = PromoUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        promos.update_promo(promo, dict(payload.validated_data), actor=request.user)
        return Response(PromoSerializer(presenter.promo_data(_promo(code))).data)


class PromoExpireView(APIView):
    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="platform_promo_codes_expire",
        summary="End the promo code now (redemptions already made are kept)",
        request=None,
        responses=PromoSerializer,
    )
    def post(self, request: Request, code: str) -> Response:
        promos.expire(_promo(code), actor=request.user)
        return Response(PromoSerializer(presenter.promo_data(_promo(code))).data)
