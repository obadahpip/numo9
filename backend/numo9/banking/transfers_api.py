"""Transfers API (F-06-T06), under ``/api/v1/o/<org>/`` like the rest of banking (F-01-T07).

- ``GET bank-transfers`` ``?bank_account=&status=&from=&to=`` — newest first; ``bank_account``
  matches either side (a transfer shows on both accounts' pages).
- ``POST bank-transfers`` ``{from_account, to_account, date, amount, reference,
  override_reason}`` — writes and posts the transfer (F-06-T03): 201 with the transfer and its
  journal. Refused rules: 400 ``{code, detail}`` (``banking.transfer.same_account``,
  ``…amount_positive``, ``…cross_currency``, ``banking.account.archived``); the cash guard and
  journal rules as the journals API (409 blocked / 422 reason required by the negative-balance
  policy, 400 ``ledger.journal.invalid``); 409 lock dates.
- ``GET bank-transfers/presets`` — each preset (F-06-T05) with the accounts it pre-fills.
- ``GET bank-transfers/<id>``; ``POST bank-transfers/<id>/void`` ``{date}`` — reverses the
  journal (409 ``banking.transfer.voided`` when already voided).

Permissions ``accounting.banking.view`` (read) / ``accounting.banking.transfer`` (write);
features ``accounting.banking.read`` / ``.write`` (every package, as F-01).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.ledger.journals_api import _refused as journal_refused
from numo9.ledger.models import LedgerError
from numo9.ledger.policy import JournalRuleError
from numo9.orgsettings.locks import acting_user
from numo9.rbac.drf import requires_permission

from .api import override_of
from .models import BankAccount, BankTransfer, BankTransferStatus
from .permissions import BANKING_TRANSFER, BANKING_VIEW
from .transfer_presets import PRESETS, resolve_preset
from .transfers import record_transfer, void_transfer

READ = "accounting.banking.read"
WRITE = "accounting.banking.write"


def _error(error: DjangoValidationError, code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {
            "code": getattr(error, "code", None) or "invalid",
            "detail": " ".join(str(m) for m in error.messages),
        },
        status=code,
    )


def _side(bank: BankAccount | None) -> dict[str, Any] | None:
    if bank is None:
        return None
    return {"id": str(bank.public_id), "name": bank.display_name, "type": bank.type}


def transfer_row(transfer: BankTransfer) -> dict[str, Any]:
    entry = transfer.journal_entry
    return {
        "id": str(transfer.public_id),
        "from_account": _side(transfer.from_account),
        "to_account": _side(transfer.to_account),
        "date": transfer.date,
        "amount": f"{transfer.amount:.2f}",
        "currency": transfer.currency,
        "reference": transfer.reference,
        "status": transfer.status,
        "voided_at": transfer.voided_at,
        "journal": {"id": str(entry.public_id), "number": entry.number} if entry else None,
        "override": override_of(entry),
    }


def _transfers() -> Any:
    return BankTransfer.objects.select_related("from_account", "to_account", "journal_entry")


def _transfer(public_id: Any) -> BankTransfer:
    found: BankTransfer | None = _transfers().filter(public_id=public_id).first()
    if found is None:
        raise NotFound(_("That transfer doesn't exist."))
    return found


def _bank(public_id: Any, field: str) -> BankAccount:
    found: BankAccount | None = (
        BankAccount.objects.select_related("gl_account")
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise serializers.ValidationError({field: [_("That bank account doesn't exist.")]})
    return found


class TransferInputSerializer(serializers.Serializer[Any]):
    from_account = serializers.UUIDField()
    to_account = serializers.UUIDField()
    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    override_reason = serializers.CharField(required=False, allow_blank=True, default="")


class VoidInputSerializer(serializers.Serializer[Any]):
    date = serializers.DateField(required=False, allow_null=True, default=None)


class BankTransferListView(APIView):
    queryset = BankTransfer._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_transfers_list", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        items = _transfers()
        params = request.query_params
        if params.get("bank_account"):
            wanted = params["bank_account"]
            items = items.filter(
                Q(from_account__public_id=wanted) | Q(to_account__public_id=wanted)
            )
        if params.get("status"):
            items = items.filter(status=params["status"])
        if params.get("from"):
            items = items.filter(date__gte=params["from"])
        if params.get("to"):
            items = items.filter(date__lte=params["to"])
        return Response({"results": [transfer_row(t) for t in items[:500]]})

    @requires_permission(BANKING_TRANSFER.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_transfers_create",
        request=TransferInputSerializer,
        responses={201: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = TransferInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        source = _bank(data["from_account"], "from_account")
        target = _bank(data["to_account"], "to_account")
        try:
            transfer = record_transfer(
                source,
                target,
                date=data["date"],
                amount=data["amount"],
                reference=data.get("reference") or "",
                user=acting_user(),
                override_reason=data.get("override_reason") or "",
            )
        except JournalRuleError as error:
            return journal_refused(error)
        except LedgerError as error:
            return _error(error)
        return Response(transfer_row(_transfer(transfer.public_id)), status=201)


class BankTransferPresetsView(APIView):
    """``GET bank-transfers/presets`` — "Fund petty cash" and "Pay credit card" with the
    accounts each pre-fills (F-06-T05)."""

    queryset = BankTransfer._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_transfers_presets", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        results = []
        for key in PRESETS:
            found = resolve_preset(key)
            results.append(
                {
                    "key": key,
                    "label": str(found.preset.label),
                    "from_types": list(found.preset.from_types),
                    "to_types": list(found.preset.to_types),
                    "from_account": _side(found.from_account),
                    "to_account": _side(found.to_account),
                }
            )
        return Response({"results": results})


class BankTransferDetailView(APIView):
    queryset = BankTransfer._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_transfers_read", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(transfer_row(_transfer(public_id)))


class BankTransferVoidView(APIView):
    queryset = BankTransfer._base_manager.none()

    @requires_permission(BANKING_TRANSFER.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_transfers_void", request=VoidInputSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        payload = VoidInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        transfer = _transfer(public_id)
        if transfer.status == BankTransferStatus.VOIDED:
            return Response(
                {
                    "code": "banking.transfer.voided",
                    "detail": _("This transfer is already voided."),
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            void_transfer(transfer, date=payload.validated_data.get("date"), user=acting_user())
        except LedgerError as error:
            return _error(error)
        return Response(transfer_row(_transfer(public_id)))
