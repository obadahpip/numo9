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
from .permissions import BILLING_MANAGE


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
