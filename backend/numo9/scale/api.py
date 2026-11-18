"""Perf-only posting endpoint for the k6 "post journal" baseline (S-06-T09).

``POST /api/v1/o/<org>/perf/journal`` posts one balanced two-line journal through the real
``post_journal`` service (validation, period locks, numbering, audit), so the baseline measures
the posting path a manual journal will take. Phase 1's manual-journal API replaces it in the k6
script; until then it exists only where ``NUMO9_PERF_ENDPOINTS`` is on (staging/scratch), and it
answers 403 everywhere else. It needs the permission to manage the chart of accounts (the
practice accountant roles have it) and is left out of the public API schema.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.ledger.models import Account, AccountStatus, JournalEntry
from numo9.ledger.permissions import ACCOUNTS_MANAGE
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.rbac.drf import requires_permission

WRITE = "accounting.journals.write"


def _amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value if value not in (None, "") else "10.00")).quantize(
            Decimal("0.01")
        )
    except InvalidOperation:
        raise ValidationError({"amount": ["Enter an amount."]}) from None
    if amount <= 0:
        raise ValidationError({"amount": ["Enter an amount above zero."]})
    return amount


class PerfJournalView(APIView):
    queryset = JournalEntry._base_manager.none()  # tenant sweep: rows of JournalEntry

    @requires_permission(ACCOUNTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(exclude=True)
    def post(self, request: Request, org: Any) -> Response:
        if not getattr(settings, "NUMO9_PERF_ENDPOINTS", False):
            raise PermissionDenied("Perf endpoints are off (NUMO9_PERF_ENDPOINTS).")
        leaves = [
            a
            for a in Account.objects.filter(status=AccountStatus.ACTIVE).order_by("code")[:20]
            if not a.children.exists()
        ][:2]
        if len(leaves) < 2:
            raise ValidationError({"accounts": ["The organisation needs two active accounts."]})
        body: Any = request.data
        amount = _amount(body.get("amount"))
        date = body.get("date") or timezone.localdate().isoformat()
        try:
            day = dt.date.fromisoformat(str(date))
        except ValueError:
            raise ValidationError({"date": ["Enter a date (YYYY-MM-DD)."]}) from None
        entry = post_journal(
            JournalSpec(
                date=day,
                narration="k6 baseline",
                lines=[
                    LineSpec(account=leaves[0], debit=amount),
                    LineSpec(account=leaves[1], credit=amount),
                ],
            )
        )
        return Response({"id": str(entry.public_id), "number": entry.number}, status=201)
