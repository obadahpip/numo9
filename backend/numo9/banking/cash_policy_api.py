"""Negative-balance policy settings API (F-07-T08), under ``/api/v1/o/<org>/``.

- ``GET bank-settings/cash-policies`` — one row per controlled account type (Chequing, Savings,
  Cash / petty cash, Clearing) with its two actions (``standard`` for people who aren't advisers,
  ``adviser``), the defaults, the choices and an explanation of each type (why Cash defaults to
  BLOCK and bank accounts to WARN). Credit cards, lines of credit and loans aren't listed: they
  are liabilities, never checked.
- ``PUT bank-settings/cash-policies`` ``{policies: [{account_type, standard, adviser}]}`` —
  changes the rows given (audited, ``AuditedModel``); the next posting reads them (no cache).

Permissions ``accounting.banking.view`` (read) / ``accounting.banking.settings`` (change);
features ``accounting.banking.read`` / ``.write``.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.ledger.renumber import acting_as
from numo9.orgsettings.locks import acting_user
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .cash_controls import DEFAULTS, effective_policies, seed_cash_policies
from .models import CONTROLLED_TYPES, BankAccountType, CashControlAction, CashControlPolicy
from .permissions import BANKING_SETTINGS, BANKING_VIEW

READ = "accounting.banking.read"
WRITE = "accounting.banking.write"

EXPLANATIONS: dict[str, Any] = {
    BankAccountType.CASH: gettext_lazy(
        "Cash on hand can't be negative: a negative petty cash means money was spent that was "
        "never put in. Blocked by default for everyone but your adviser."
    ),
    BankAccountType.CHEQUING: gettext_lazy(
        "A chequing account can be overdrawn when you have an overdraft: by default you are "
        "warned and give a reason."
    ),
    BankAccountType.SAVINGS: gettext_lazy(
        "Savings accounts rarely go below zero: by default you are warned and give a reason."
    ),
    BankAccountType.CLEARING: gettext_lazy(
        "Money in transit between accounts: by default you are warned and give a reason."
    ),
}


def _rows(organisation: Any) -> list[dict[str, Any]]:
    policies = effective_policies(organisation)
    return [
        {
            "account_type": kind,
            "label": str(BankAccountType(kind).label),
            "standard": policies[kind].standard,
            "adviser": policies[kind].adviser,
            "default": {"standard": DEFAULTS[kind].standard, "adviser": DEFAULTS[kind].adviser},
            "explanation": str(EXPLANATIONS[kind]),
        }
        for kind in CONTROLLED_TYPES
    ]


def _body(organisation: Any) -> dict[str, Any]:
    return {
        "policies": _rows(organisation),
        "actions": [{"value": a.value, "label": str(a.label)} for a in CashControlAction],
    }


class PolicyRowSerializer(serializers.Serializer[Any]):
    account_type = serializers.ChoiceField(choices=list(CONTROLLED_TYPES))
    standard = serializers.ChoiceField(choices=CashControlAction.choices)
    adviser = serializers.ChoiceField(choices=CashControlAction.choices)


class PoliciesInputSerializer(serializers.Serializer[Any]):
    policies = PolicyRowSerializer(many=True)


class CashPolicyView(APIView):
    queryset = CashControlPolicy._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_cash_policies_read", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        return Response(_body(current_org()))

    @requires_permission(BANKING_SETTINGS.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_cash_policies_update",
        request=PoliciesInputSerializer,
        responses={200: dict},
    )
    def put(self, request: Request, org: Any) -> Response:
        payload = PoliciesInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        organisation = current_org()
        rows = payload.validated_data["policies"]
        if len({row["account_type"] for row in rows}) != len(rows):
            raise serializers.ValidationError({"policies": [_("Give each account type once.")]})
        person = acting_user()
        with transaction.atomic(), acting_as(person):
            seed_cash_policies(organisation)
            stored = {
                row.account_type: row
                for row in CashControlPolicy.objects.select_for_update().filter(
                    account_type__in=[r["account_type"] for r in rows]
                )
            }
            for row in rows:
                policy = stored[row["account_type"]]
                if (policy.standard_action, policy.adviser_action) == (
                    row["standard"],
                    row["adviser"],
                ):
                    continue
                policy.standard_action = row["standard"]
                policy.adviser_action = row["adviser"]
                policy.save()
        return Response(_body(organisation))
