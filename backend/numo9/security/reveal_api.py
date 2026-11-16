"""``POST /api/v1/o/<org>/reveal`` — the full value of a masked field (S-03-T05).

Body ``{"record_type": "payroll.Employee", "record_id": "<uuid>", "field": "sin"}`` → ``{"value":
"046454286"}``. Permission ``security.sensitive.reveal``; a password confirmed in the last 5
minutes (``401 security.reauthentication_required`` otherwise — the web app shows the password
prompt, then asks again); the field must be registered revealable and the record in this
organisation (404). Each reveal writes the audit event ``security.value.revealed`` (record,
field — not the value). See ``numo9.security.masking``.
"""

from __future__ import annotations

from typing import Any

from allauth.account.internal.flows.reauthentication import did_recently_reauthenticate
from django.apps import apps
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.audit.service import record
from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import requires_permission

from .masking import revealable
from .permissions import SENSITIVE_REVEAL


class RevealRequestSerializer(serializers.Serializer[Any]):
    record_type = serializers.CharField(max_length=100)
    record_id = serializers.UUIDField()
    field = serializers.CharField(max_length=100)


class RevealResultSerializer(serializers.Serializer[Any]):
    value = serializers.CharField(allow_blank=True)


class RevealView(APIView):
    required_feature = CORE
    serializer_class = RevealRequestSerializer

    @requires_permission(SENSITIVE_REVEAL.key)
    @extend_schema(
        operation_id="security_reveal",
        summary="The full value of a masked field (password confirmed, audited)",
        request=RevealRequestSerializer,
        responses=RevealResultSerializer,
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = RevealRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        entry = revealable(data["record_type"], data["field"])
        if entry is None:
            raise NotFound
        if not did_recently_reauthenticate(request._request):
            raise api_error(errors.SECURITY_REAUTHENTICATION_REQUIRED)
        model = apps.get_model(entry.model)
        try:
            row = model.objects.filter(public_id=data["record_id"], deleted_at__isnull=True).first()
        except ValidationError:
            row = None
        if row is None:  # the scoped manager: another organisation's record is not found
            raise NotFound
        value = getattr(row, entry.field)
        record(
            "security.value.revealed",
            obj=row,
            meta={"field": entry.field},
            actor=request.user,
        )
        return Response({"value": "" if value is None else str(value)})
