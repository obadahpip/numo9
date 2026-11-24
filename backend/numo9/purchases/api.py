"""Bills API (E-02), under ``/api/v1/o/<org>/``.

- ``GET bills/check-number?supplier=<contact id>&number=<supplier invoice no>&exclude=<bill id>``
  — the live supplier-invoice-number check of the bill editor (E-02-T02, gap-24): ``available``
  and, when taken, the bill that has it (``number``, ``date``, ``url``) with the message the
  editor shows ("Already used on BILL-0042 (12 Sep 2026)").
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.documents.formatting import format_date
from numo9.rbac.drf import requires_permission

from .models import Bill
from .permissions import BILLS_VIEW
from .uniqueness import normalise, number_conflict

READ = "accounting.bills.read"
WRITE = "accounting.bills.write"
APPROVE = "accounting.bills.approve"


def bill_url(bill: Bill) -> str:
    return f"/o/{bill.organisation.public_id}/purchases/bills/{bill.public_id}"


def _uuid(value: str | None) -> str | None:
    import uuid

    try:
        return str(uuid.UUID(str(value))) if value else None
    except ValueError:
        return None


class BillNumberCheckView(APIView):
    @requires_permission(BILLS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="bills_check_number",
        summary="Is a supplier invoice number free for this supplier? (live check, gap-24)",
        parameters=[
            OpenApiParameter("supplier", OpenApiTypes.UUID, required=True),
            OpenApiParameter("number", str, required=True),
            OpenApiParameter("exclude", OpenApiTypes.UUID),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        from numo9.contacts.models import Contact

        query = request.query_params
        number = normalise(query.get("number") or "")
        supplier_id = _uuid(query.get("supplier"))
        supplier = Contact.objects.filter(public_id=supplier_id).first() if supplier_id else None
        exclude_id = _uuid(query.get("exclude"))
        exclude = Bill.objects.filter(public_id=exclude_id).first() if exclude_id else None
        found = number_conflict(supplier, number, exclude=exclude)
        if found is None:
            return Response({"number": number, "available": True, "conflict": None})
        label = found.number or _("a draft bill")
        locale = getattr(request, "LANGUAGE_CODE", None)
        return Response(
            {
                "number": number,
                "available": False,
                "conflict": {
                    "id": str(found.public_id),
                    "number": found.number,
                    "status": found.status,
                    "date": found.date.isoformat(),
                    "url": bill_url(found),
                    "message": _("Already used on %(bill)s (%(date)s)")
                    % {"bill": label, "date": format_date(found.date, locale)},
                },
            }
        )
