"""Billing API (U-04), under ``/api/v1/o/<org>/billing/``: the organisation's owner only.

- ``POST billing/checkout`` (U-04-T05) — ``{package, interval, methods?}`` → 201
  ``{url, session_id, package, interval, amount_cents}``: the Stripe Checkout page to send the
  owner to (card and/or pre-authorised debit).

Every endpoint needs ``organisation.billing.manage`` (or ``.view`` to read), which only the owner
role has — practice staff and admins get 403. Billing is part of every organisation (``CORE``).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.packages.models import BillingInterval
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .changes import change, preview
from .checkout import METHODS, start_checkout
from .export import cancel, export_link, latest_export, resume, start_export
from .permissions import BILLING_MANAGE, BILLING_VIEW


class CheckoutRequestSerializer(serializers.Serializer[Any]):
    package = serializers.CharField(max_length=40)
    interval = serializers.ChoiceField(choices=BillingInterval.choices)
    methods = serializers.ListField(
        child=serializers.ChoiceField(choices=list(METHODS)), required=False, allow_empty=False
    )


class CheckoutResponseSerializer(serializers.Serializer[Any]):
    url = serializers.URLField()
    session_id = serializers.CharField()
    package = serializers.CharField()
    interval = serializers.CharField()
    amount_cents = serializers.IntegerField()


class CheckoutView(APIView):
    required_feature = CORE
    serializer_class = CheckoutRequestSerializer

    @requires_permission(BILLING_MANAGE.key)
    @extend_schema(
        operation_id="billing_checkout",
        summary="Start paying for a package (Stripe Checkout: card or pre-authorised debit)",
        request=CheckoutRequestSerializer,
        responses={201: CheckoutResponseSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        body = CheckoutRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        organisation = current_org()
        assert organisation is not None  # noqa: S101 - RequiresPermission answered 404 otherwise
        started = start_checkout(
            organisation,
            body.validated_data["package"],
            body.validated_data["interval"],
            body.validated_data.get("methods"),
            request_key=request.headers.get("Idempotency-Key", ""),
        )
        return Response(
            {
                "url": started.session.url,
                "session_id": started.session.id,
                "package": started.package,
                "interval": started.interval,
                "amount_cents": started.amount_cents,
            },
            status=status.HTTP_201_CREATED,
        )


class ChangeQuerySerializer(serializers.Serializer[Any]):
    package = serializers.CharField(max_length=40)
    interval = serializers.ChoiceField(choices=BillingInterval.choices)


class ChangeRequestSerializer(ChangeQuerySerializer):
    proration_date = serializers.IntegerField(required=False, min_value=0)


class ChangePreviewSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=["upgrade", "downgrade"])
    package = serializers.CharField()
    interval = serializers.CharField()
    amount_cents = serializers.IntegerField()
    charged_today_cents = serializers.IntegerField()
    currency = serializers.CharField()
    effective_at = serializers.DateTimeField()
    proration_date = serializers.IntegerField()


def _preview_body(result: Any) -> dict[str, Any]:
    return ChangePreviewSerializer(
        {
            "kind": result.kind,
            "package": result.package,
            "interval": result.interval,
            "amount_cents": result.amount_cents,
            "charged_today_cents": result.charged_today_cents,
            "currency": result.currency,
            "effective_at": result.effective_at,
            "proration_date": result.proration_date,
        }
    ).data


class ChangePreviewView(APIView):
    required_feature = CORE
    serializer_class = ChangePreviewSerializer

    @requires_permission(BILLING_MANAGE.key)
    @extend_schema(
        operation_id="billing_change_preview",
        summary="What changing the package would cost (proration preview)",
        parameters=[ChangeQuerySerializer],
        responses=ChangePreviewSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        query = ChangeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        organisation = current_org()
        assert organisation is not None  # noqa: S101
        result = preview(
            organisation, query.validated_data["package"], query.validated_data["interval"]
        )
        return Response(_preview_body(result))


class ChangeView(APIView):
    required_feature = CORE
    serializer_class = ChangeRequestSerializer

    @requires_permission(BILLING_MANAGE.key)
    @extend_schema(
        operation_id="billing_change",
        summary="Upgrade now (prorated) or downgrade at the end of the period",
        request=ChangeRequestSerializer,
        responses=ChangePreviewSerializer,
    )
    def post(self, request: Request, org: Any) -> Response:
        body = ChangeRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        organisation = current_org()
        assert organisation is not None  # noqa: S101
        result = change(
            organisation,
            body.validated_data["package"],
            body.validated_data["interval"],
            body.validated_data.get("proration_date"),
        )
        return Response(_preview_body(result))


class ExportSerializer(serializers.Serializer[Any]):
    job = serializers.UUIDField(allow_null=True)
    status = serializers.CharField(allow_null=True)
    url = serializers.URLField(allow_null=True)
    expires_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)


def _export_body(run: Any) -> dict[str, Any]:
    if run is None:
        return {"job": None, "status": None, "url": None, "expires_at": None, "created_at": None}
    link = export_link(run)
    return {
        "job": run.public_id,
        "status": run.status,
        "url": link.url if link else None,
        "expires_at": link.expires_at if link else None,
        "created_at": run.created_at,
    }


class CancelSerializer(serializers.Serializer[Any]):
    resume = serializers.BooleanField(default=False)


class CancelResponseSerializer(serializers.Serializer[Any]):
    cancel_at_period_end = serializers.BooleanField()
    current_period_end = serializers.DateTimeField(allow_null=True)
    export = ExportSerializer(allow_null=True)


class CancelView(APIView):
    required_feature = CORE
    serializer_class = CancelSerializer

    @requires_permission(BILLING_MANAGE.key)
    @extend_schema(
        operation_id="billing_cancel",
        summary="Cancel at the end of the paid period (with the data export), or resume",
        request=CancelSerializer,
        responses=CancelResponseSerializer,
    )
    def post(self, request: Request, org: Any) -> Response:
        body = CancelSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        organisation = current_org()
        assert organisation is not None  # noqa: S101
        if body.validated_data["resume"]:
            subscription, run = resume(organisation, request.user), None
        else:
            subscription, run = cancel(organisation, request.user)
        return Response(
            {
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "current_period_end": subscription.current_period_end,
                "export": _export_body(run) if run is not None else None,
            }
        )


class ExportView(APIView):
    required_feature = CORE
    serializer_class = ExportSerializer

    @requires_permission(BILLING_VIEW.key)
    @extend_schema(
        operation_id="billing_export_get",
        summary="The latest data export and a fresh download link",
        responses=ExportSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        organisation = current_org()
        assert organisation is not None  # noqa: S101
        return Response(_export_body(latest_export(organisation)))

    @requires_permission(BILLING_MANAGE.key)
    @extend_schema(
        operation_id="billing_export_start",
        summary="Export every dataset and document (ZIP: CSV, XLSX, JSON ledger, files)",
        request=None,
        responses={202: ExportSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        organisation = current_org()
        assert organisation is not None  # noqa: S101
        run = start_export(organisation, request.user)
        return Response(_export_body(run), status=status.HTTP_202_ACCEPTED)
