"""Sending-domain API (A-07-T05, T06), under ``/api/v1/o/<org>/email-domains``.

Permission ``organisation.settings.manage`` (owners and admins); part of every organisation
(``CORE``). Another organisation's domain is a 404.

- ``email-domains`` — GET the organisation's domains with their DNS records; POST
  ``{"domain", "from_local_part"}`` adds one at the provider (201);
- ``email-domains/<id>`` — GET one; DELETE removes it (provider and here);
- ``email-domains/<id>/refresh`` — POST fetches the DKIM record from the provider again;
- ``email-domains/<id>/check`` — POST checks the DNS records now (A-07-T06).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.rbac.drf import requires_permission

from . import dnscheck, domains
from .models import SendingDomain, SendingDomainRecord

MANAGE = "organisation.settings.manage"


class RecordSerializer(serializers.ModelSerializer[SendingDomainRecord]):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SendingDomainRecord
        fields = (
            "kind", "kind_label", "record_type", "host", "value", "status", "status_label",
            "found", "checked_at",
        )  # fmt: skip
        read_only_fields = fields


class SendingDomainSerializer(serializers.ModelSerializer[SendingDomain]):
    id = serializers.UUIDField(source="public_id", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    from_address = serializers.CharField(read_only=True)
    records = RecordSerializer(many=True, read_only=True)

    class Meta:
        model = SendingDomain
        fields = (
            "id", "domain", "from_local_part", "from_address", "provider", "status",
            "status_label", "verified_at", "last_checked_at", "records", "created_at",
        )  # fmt: skip
        read_only_fields = fields


class AddDomainSerializer(serializers.Serializer[Any]):
    domain = serializers.CharField(max_length=253)
    from_local_part = serializers.RegexField(
        r"^[A-Za-z0-9._-]{1,64}$", required=False, default="billing"
    )


class DomainListSerializer(serializers.Serializer[Any]):
    results = SendingDomainSerializer(many=True)


def _one(public_id: Any) -> SendingDomain:
    row: SendingDomain | None = SendingDomain.objects.filter(
        public_id=public_id, deleted_at__isnull=True
    ).first()
    if row is None:
        raise NotFound
    return row


def _out(row: SendingDomain) -> Any:
    return SendingDomainSerializer(
        SendingDomain.objects.prefetch_related("records").get(pk=row.pk)
    ).data


class DomainListView(APIView):
    required_feature = CORE
    serializer_class = SendingDomainSerializer

    @requires_permission(MANAGE)
    @extend_schema(operation_id="email_domains_list", responses=DomainListSerializer)
    def get(self, request: Request, org: Any) -> Response:
        rows = SendingDomain.objects.filter(deleted_at__isnull=True).prefetch_related("records")
        return Response(
            {"results": SendingDomainSerializer(rows.order_by("domain"), many=True).data}
        )

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="email_domains_add",
        summary="Add a sending domain at the email provider; returns the DNS records to publish",
        request=AddDomainSerializer,
        responses={201: SendingDomainSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = AddDomainSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = domains.add_domain(
            payload.validated_data["domain"],
            payload.validated_data["from_local_part"],
            user=request.user,
        )
        return Response(_out(row), status=status.HTTP_201_CREATED)


class DomainDetailView(APIView):
    required_feature = CORE
    serializer_class = SendingDomainSerializer

    @requires_permission(MANAGE)
    @extend_schema(operation_id="email_domains_get", responses=SendingDomainSerializer)
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(_out(_one(public_id)))

    @requires_permission(MANAGE)
    @extend_schema(operation_id="email_domains_remove", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        domains.remove_domain(_one(public_id))
        return Response(status=status.HTTP_204_NO_CONTENT)


class DomainRefreshView(APIView):
    required_feature = CORE
    serializer_class = SendingDomainSerializer

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="email_domains_refresh",
        summary="Fetch the DKIM record from the email provider again",
        request=None,
        responses=SendingDomainSerializer,
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(_out(domains.refresh_from_provider(_one(public_id))))


class DomainCheckView(APIView):
    required_feature = CORE
    serializer_class = SendingDomainSerializer

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="email_domains_check",
        summary="Look up the domain's DNS records now and update their status",
        request=None,
        responses=SendingDomainSerializer,
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(_out(dnscheck.check_domain(_one(public_id))))
