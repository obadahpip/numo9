"""Product catalogue API (U-01-T09), mounted under ``/api/v1/``.

- ``catalogue/products`` — GET every product (main, free sets, companion apps) with its status
  and feature keys: the Products screen and the in-app pages;
- ``catalogue/feature-matrix`` — GET every feature key once with its product and the packages
  that include it (key → product → packages): the "Package & features" page, and later the
  public pricing page (Q-01 serves the same data publicly, gap-61).

In an organisation (``organisation.profile.view``, never gated — part of every organisation):

- ``o/<org>/package-features`` — GET the feature matrix plus the organisation's current package
  (null until U-03/U-04 give organisations a subscription): the in-app "Package and features"
  page (U-01-T12).

Platform console (``platform.catalogue.view``):

- ``platform/catalogue/products`` — GET the same products as ``catalogue/products`` for the
  console's Products screen (U-01-T11): refused (403, "why can't I?") to anyone else;
- ``platform/catalogue/feature-matrix/export/<csv|xlsx>`` — GET the matrix as a file, one row
  per feature key (U-01-T10); every export is recorded in the platform audit log.

Signed-in users only; the same answer for everyone (no tenant data), texts in the request's
language. Public-safe fields only (``presenter``). Not organisation-scoped: no feature key.
"""

from __future__ import annotations

from typing import cast

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.audit.service import record
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import AUTHENTICATED, requires_permission
from numo9.tenancy.context import current_org

from . import exports, presenter
from .drf import CORE
from .models import FeatureKey
from .packages import get_source
from .permissions import CATALOGUE_VIEW
from .serializers import (
    FeatureMatrixSerializer,
    OrganisationMatrixSerializer,
    ProductListSerializer,
)


class ProductListView(APIView):
    @requires_permission(AUTHENTICATED)  # the same for everyone; no tenant data
    @extend_schema(
        operation_id="catalogue_products",
        summary="Every product with its status and feature keys",
        responses=ProductListSerializer,
    )
    def get(self, request: Request) -> Response:
        body = {"products": presenter.products(features=True)}
        return Response(ProductListSerializer(body).data)


class FeatureMatrixView(APIView):
    @requires_permission(AUTHENTICATED)
    @extend_schema(
        operation_id="catalogue_feature_matrix",
        summary="Every feature key once, with its product and the packages that include it",
        responses=FeatureMatrixSerializer,
    )
    def get(self, request: Request) -> Response:
        return Response(FeatureMatrixSerializer(presenter.feature_matrix()).data)


class OrganisationMatrixView(APIView):
    required_feature = CORE  # every organisation sees what its package includes

    @requires_permission("organisation.profile.view")
    @extend_schema(
        operation_id="organisation_package_features",
        summary="The feature matrix with the organisation's current package",
        responses=OrganisationMatrixSerializer,
    )
    def get(self, request: Request, org: object) -> Response:
        organisation = current_org()
        if organisation is None:  # RequiresPermission already answers 404 then
            raise NotFound
        body = {
            **presenter.feature_matrix(),
            "current_package": get_source().current_package(organisation),
        }
        return Response(OrganisationMatrixSerializer(body).data)


class PlatformProductListView(APIView):
    @requires_permission(CATALOGUE_VIEW.key)
    @extend_schema(
        operation_id="platform_catalogue_products",
        summary="Products, statuses and feature keys for the platform console",
        responses=ProductListSerializer,
    )
    def get(self, request: Request) -> Response:
        body = {"products": presenter.products(features=True)}
        return Response(ProductListSerializer(body).data)


class FeatureMatrixExportView(APIView):
    @requires_permission(CATALOGUE_VIEW.key)
    @extend_schema(
        operation_id="platform_catalogue_feature_matrix_export",
        summary="The feature matrix as CSV or XLSX, one row per feature key",
        parameters=[
            OpenApiParameter(
                "kind",
                OpenApiTypes.STR,
                OpenApiParameter.PATH,
                enum=list(exports.FORMATS),
                description="File format: csv or xlsx",
            )
        ],
        responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, kind: str) -> HttpResponse:
        kind = kind.lower()
        if kind not in exports.FORMATS:
            raise api_error(errors.CATALOGUE_EXPORT_FORMAT)
        user = cast(User, request.user)
        response = HttpResponse(
            exports.write(kind, user.locale), content_type=exports.CONTENT_TYPES[kind]
        )
        name = f"numo9-feature-matrix_{timezone.localdate().isoformat()}.{kind}"
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        response["Cache-Control"] = "no-store"
        record(
            "catalogue.matrix.exported",
            organisation=None,
            object_type="catalogue.FeatureKey",
            object_label="Feature matrix",
            meta={"format": kind, "rows": FeatureKey.objects.count()},
            actor=user,
        )
        return response
