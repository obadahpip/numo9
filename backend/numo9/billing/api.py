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
