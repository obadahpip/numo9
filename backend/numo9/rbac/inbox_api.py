"""``GET /api/v1/o/<org>/approvals`` — the approvals inbox (C-04-T08; ``numo9.rbac.inbox``)."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.tenancy.context import current_org

from .drf import requires_permission
from .inbox import inbox
from .resolver import has_perm


class ApprovalsInboxView(APIView):
    """Everything waiting for approval that the person may approve or submitted; ``?kind=``
    keeps one kind (``journal``…)."""

    required_feature = CORE  # every organisation: what waits depends on its modules

    @requires_permission("organisation.profile.view")  # every role here has it
    @extend_schema(
        operation_id="approvals_inbox",
        summary="Everything waiting for approval that I may approve or submitted",
        responses={200: dict},
    )
    def get(self, request: Request, org: Any) -> Response:
        organisation = current_org()
        assert organisation is not None  # noqa: S101 - RequiresPermission answered 404 otherwise
        user = request.user
        body = inbox(user, organisation, has_perm=lambda key: has_perm(user, organisation, key))
        kind = request.query_params.get("kind")
        if kind:
            body["results"] = [i for i in body["results"] if i["kind"] == kind]
        return Response(body)
