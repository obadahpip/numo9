"""Demo API (U-07-T10…T12), under /api/v1/.

- ``POST o/<org>/demo/convert`` {name} — start my free trial: a new empty organisation, the demo
  deleted (owner of the demo; a real account);
- ``POST o/<org>/demo/reset`` — back to the sample data (owner);
- ``GET  o/<org>/demo/outbox`` — the emails the demo would have sent (any member);
- ``POST demo`` — open a demo (U-07-T11; signed in or anonymous).

A non-demo organisation answers 409 ``demo.not_a_demo``.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.entitlements.trials import TrialAlreadyUsed
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import requires_permission
from numo9.tenancy.api import trial_refused
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation

from .convert import NotADemo, SignUpFirst, convert_to_trial
from .exclusions import is_demo
from .models import DemoOutbox

CLOSE = "organisation.close"
VIEW = "organisation.profile.view"


def _demo() -> Organisation:
    organisation = current_org()
    if organisation is None or not is_demo(organisation):
        raise api_error(errors.DEMO_NOT_A_DEMO)
    return organisation


class ConvertSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200)


class DemoConvertView(APIView):
    queryset = DemoOutbox._base_manager.none()  # tenant sweep: organisation-scoped

    @requires_permission(CLOSE)
    @extend_schema(
        operation_id="demo_convert",
        summary="Start my free trial: a new empty organisation; the demo is deleted",
        request=ConvertSerializer,
        responses={
            201: inline_serializer(
                "DemoConverted", {"id": serializers.UUIDField(), "name": serializers.CharField()}
            )
        },
    )
    def post(self, request: Request, org: Any) -> Response:
        demo = _demo()
        incoming = ConvertSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        try:
            organisation = convert_to_trial(
                demo, request.user, name=incoming.validated_data["name"]
            )
        except NotADemo:
            raise api_error(errors.DEMO_NOT_A_DEMO) from None
        except SignUpFirst:
            raise api_error(errors.DEMO_SIGN_UP_FIRST) from None
        except TrialAlreadyUsed as refused:
            raise trial_refused(request, refused) from None
        return Response(
            {"id": str(organisation.public_id), "name": organisation.name},
            status=status.HTTP_201_CREATED,
        )
