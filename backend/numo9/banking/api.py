"""Banking API (F-01-T07), under ``/api/v1/o/<org>/``.

Bank accounts:

- ``GET bank-accounts`` ``?status=active|archived|all`` — every account with its **ledger
  balance** (F-01-T06; ``as_of`` optional), optional statement balance and date, type, masked
  number, ledger account (code, name), transaction count and last activity date.
- ``POST bank-accounts`` ``{type, display_name, institution, currency, account_last4,
  loan_current}`` — creates the account and its ledger account (F-01-T03). 201.
- ``GET bank-accounts/<id>/register`` — the transactions with their running balance and filters
  (F-01-T11); ``?export=csv|xlsx`` downloads them.
- ``GET`` / ``PATCH`` / ``DELETE bank-accounts/<id>`` — read; edit the name (the ledger account is
  renamed too), institution, last 4 digits, statement balance and date, reconciliation tracking,
  currency (refused once the account has transactions); delete — **409**
  ``banking.account.has_transactions`` with ``count`` when it has transactions (F-01-T04).
- ``POST bank-accounts/<id>/archive`` / ``…/restore``.

Bank transactions (spend money / receive money, F-01-T05):

- ``GET bank-transactions`` ``?bank_account=&kind=&status=&from=&to=`` — newest first.
- ``POST bank-transactions`` ``{kind, bank_account, date, contact, reference, tax_mode, lines:
  [{account, amount, description, tax_code, taxes: [{role, amount, recoverable}], tracking}],
  attachments, override_reason}`` — posts it (201 with the transaction and its journal).
- ``GET bank-transactions/<id>``; ``POST bank-transactions/<id>/void`` ``{date}`` — reverses the
  journal and marks it voided.

Errors: 400 ``{code, detail}`` for a refused rule; journal-rule problems as the journals API
(``ledger.journal.invalid`` with ``errors``; 409 cash guard); 409 lock dates.

Permissions ``accounting.banking.view`` / ``.manage`` / ``.transact``; features
``accounting.banking.read`` / ``.write`` (every package — banking is never gated, gap-27).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Max, QuerySet
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.contacts.models import Contact
from numo9.files.models import Document
from numo9.ledger.journals_api import _refused as journal_refused
from numo9.ledger.models import Account, JournalEntry, LedgerError
from numo9.ledger.policy import JournalRuleError
from numo9.ledger.renumber import acting_as
from numo9.orgsettings.locks import acting_user
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .balances import ledger_balance
from .lifecycle import (
    BankAccountInUse,
    archive_bank_account,
    delete_bank_account,
    restore_bank_account,
    transaction_count,
)
from .models import (
    BankAccount,
    BankAccountType,
    BankTransaction,
    BankTransactionKind,
    BankTransactionStatus,
    TaxMode,
)
from .permissions import BANKING_MANAGE, BANKING_TRANSACT, BANKING_VIEW
from .register import RegisterFilters, export_register, register
from .services import create_bank_account
from .transactions import (
    TAX_ROLES,
    MoneyLine,
    MoneySpec,
    TaxPortion,
    record_bank_transaction,
    void_bank_transaction,
)

READ = "accounting.banking.read"
WRITE = "accounting.banking.write"


def _error(error: DjangoValidationError, code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    body: dict[str, Any] = {
        "code": getattr(error, "code", None) or "invalid",
        "detail": " ".join(str(m) for m in error.messages),
    }
    if isinstance(error, BankAccountInUse):
        body["count"] = (error.params or {}).get("count")
        code = status.HTTP_409_CONFLICT
    return Response(body, status=code)


def _money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


# ---- bank accounts -----------------------------------------------------------------------------


def _activity(ids: list[int]) -> dict[int, dict[str, Any]]:
    from numo9.ledger.models import JournalLine

    rows = (
        JournalLine.objects.filter(account_id__in=ids)
        .values("account_id")
        .annotate(count=Count("entry_id", distinct=True), last=Max("entry__date"))
        .order_by()
    )
    return {row["account_id"]: row for row in rows}


def account_row(
    bank: BankAccount, activity: dict[str, Any] | None = None, as_of: dt.date | None = None
) -> dict[str, Any]:
    ledger = bank.gl_account
    seen = activity or {}
    return {
        "id": str(bank.public_id),
        "type": bank.type,
        "type_label": str(BankAccountType(bank.type).label),
        "display_name": bank.display_name,
        "institution": bank.institution,
        "currency": bank.currency,
        "masked_number": bank.masked_number,
        "ledger_account": {"id": str(ledger.public_id), "code": ledger.code, "name": ledger.name},
        "ledger_balance": _money(ledger_balance(bank, as_of)),
        "statement_balance": _money(bank.statement_balance),
        "statement_balance_date": bank.statement_balance_date,
        "is_reconciled_tracking": bank.is_reconciled_tracking,
        "is_liability": ledger.type == "liability",
        "archived_at": bank.archived_at,
        "transaction_count": seen.get("count", 0),
        "last_activity": seen.get("last"),
    }


def _bank(public_id: Any) -> BankAccount:
    found = (
        BankAccount.objects.select_related("gl_account")
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise NotFound(_("That bank account doesn't exist."))
    return found


class AccountInputSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=BankAccountType.choices)
    display_name = serializers.CharField(max_length=120)
    institution = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )
    currency = serializers.RegexField(r"^[A-Za-z]{3}$", required=False, default="CAD")
    account_last4 = serializers.RegexField(r"^\d{4}$", required=False, allow_blank=True, default="")
    loan_current = serializers.BooleanField(required=False, default=False)


class AccountPatchSerializer(serializers.Serializer[Any]):
    display_name = serializers.CharField(max_length=120, required=False)
    institution = serializers.CharField(max_length=120, required=False, allow_blank=True)
    currency = serializers.RegexField(r"^[A-Za-z]{3}$", required=False)
    account_last4 = serializers.RegexField(r"^\d{4}$", required=False, allow_blank=True)
    statement_balance = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, allow_null=True
    )
    statement_balance_date = serializers.DateField(required=False, allow_null=True)
    is_reconciled_tracking = serializers.BooleanField(required=False)


class BankAccountListView(APIView):
    queryset = BankAccount._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_accounts_list", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        accounts: QuerySet[BankAccount] = BankAccount.objects.select_related("gl_account").filter(
            deleted_at__isnull=True
        )
        wanted = request.query_params.get("status", "active")
        if wanted == "active":
            accounts = accounts.filter(archived_at__isnull=True)
        elif wanted == "archived":
            accounts = accounts.filter(archived_at__isnull=False)
        as_of_text = request.query_params.get("as_of")
        as_of = dt.date.fromisoformat(as_of_text) if as_of_text else None
        items = list(accounts)
        activity = _activity([bank.gl_account_id for bank in items])
        return Response(
            {"results": [account_row(b, activity.get(b.gl_account_id), as_of) for b in items]}
        )

    @requires_permission(BANKING_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_accounts_create", request=AccountInputSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        data = AccountInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            bank = create_bank_account(current_org(), user=acting_user(), **data.validated_data)  # type: ignore[arg-type]
        except LedgerError as error:
            return _error(error)
        return Response(account_row(bank), status=status.HTTP_201_CREATED)


class BankAccountDetailView(APIView):
    queryset = BankAccount._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_accounts_read", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        bank = _bank(public_id)
        return Response(account_row(bank, _activity([bank.gl_account_id]).get(bank.gl_account_id)))

    @requires_permission(BANKING_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_accounts_update", request=AccountPatchSerializer, responses={200: dict}
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        data = AccountPatchSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        changes = dict(data.validated_data)
        person = acting_user()
        try:
            with transaction.atomic(), acting_as(person):
                bank = BankAccount._base_manager.select_for_update().get(pk=_bank(public_id).pk)
                currency = changes.pop("currency", None)
                if currency and currency.upper() != bank.currency:
                    if transaction_count(bank):
                        raise LedgerError(
                            _("The currency is fixed once the account has transactions."),
                            code="banking.account.currency_fixed",
                        )
                    bank.currency = currency.upper()
                name = " ".join(changes.pop("display_name", bank.display_name).split())
                if not name:
                    raise LedgerError(
                        _("Give the account a name."), code="banking.account.name_required"
                    )
                if name.lower() != bank.display_name.lower() and (
                    BankAccount.objects.filter(display_name__iexact=name, deleted_at__isnull=True)
                    .exclude(pk=bank.pk)
                    .exists()
                ):
                    raise LedgerError(
                        _("There's already an account called “%(name)s”. Choose another name."),
                        code="banking.account.name_taken",
                        params={"name": name},
                    )
                if name != bank.display_name:
                    bank.display_name = name
                    ledger = Account._base_manager.get(pk=bank.gl_account_id)
                    ledger.set_name(name)
                    ledger.save()
                for field, value in changes.items():
                    setattr(bank, field, value.strip() if isinstance(value, str) else value)
                bank.save()
        except LedgerError as error:
            return _error(error)
        return self.get(request, org, public_id)

    @requires_permission(BANKING_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bank_accounts_delete", responses={204: None, 409: dict})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        try:
            delete_bank_account(_bank(public_id), actor=acting_user())
        except LedgerError as error:
            return _error(error)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BankAccountArchiveView(APIView):
    queryset = BankAccount._base_manager.none()
    restore = False

    @requires_permission(BANKING_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bank_accounts_archive", request=None, responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        change = restore_bank_account if self.restore else archive_bank_account
        bank = change(_bank(public_id), actor=acting_user())
        return Response(account_row(bank))


class BankAccountRestoreView(BankAccountArchiveView):
    restore = True

    @requires_permission(BANKING_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bank_accounts_restore", request=None, responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return super().post(request, org, public_id)


# ---- bank transactions -------------------------------------------------------------------------


class TaxPortionSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(choices=sorted(TAX_ROLES))
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    recoverable = serializers.BooleanField(required=False, default=True)


class MoneyLineSerializer(serializers.Serializer[Any]):
    account = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    tax_code = serializers.CharField(required=False, allow_blank=True, default="", max_length=60)
    taxes = TaxPortionSerializer(many=True, required=False, default=list)
    tracking = serializers.DictField(required=False, default=dict)


class TransactionInputSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=BankTransactionKind.choices)
    bank_account = serializers.UUIDField()
    date = serializers.DateField()
    contact = serializers.UUIDField(required=False, allow_null=True, default=None)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    tax_mode = serializers.ChoiceField(
        choices=TaxMode.choices, required=False, default=TaxMode.EXCLUSIVE
    )
    lines = MoneyLineSerializer(many=True)
    attachments = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    override_reason = serializers.CharField(required=False, allow_blank=True, default="")


class VoidInputSerializer(serializers.Serializer[Any]):
    date = serializers.DateField(required=False, allow_null=True, default=None)


def transaction_row(txn: BankTransaction, *, lines: bool = False) -> dict[str, Any]:
    entry: JournalEntry | None = txn.journal_entry
    row: dict[str, Any] = {
        "id": str(txn.public_id),
        "kind": txn.kind,
        "bank_account": {
            "id": str(txn.bank_account.public_id),
            "name": txn.bank_account.display_name,
        },
        "date": txn.date,
        "contact": {"id": str(txn.contact.public_id), "name": txn.contact.display_name}
        if txn.contact_id and txn.contact is not None
        else None,
        "reference": txn.reference,
        "tax_mode": txn.tax_mode,
        "subtotal": _money(txn.subtotal),
        "tax_total": _money(txn.tax_total),
        "total": _money(txn.total),
        "status": txn.status,
        "voided_at": txn.voided_at,
        "journal": {"id": str(entry.public_id), "number": entry.number} if entry else None,
    }
    if lines:
        row["lines"] = [
            {
                "line": line.line_no,
                "account": {"id": str(line.account.public_id), "code": line.account.code},
                "description": line.description,
                "amount": _money(line.amount),
                "net": _money(line.net),
                "tax_amount": _money(line.tax_amount),
                "tax_code": line.tax_code,
                "taxes": line.taxes,
            }
            for line in txn.lines.select_related("account").order_by("line_no")
        ]
    return row


def _txn(public_id: Any) -> BankTransaction:
    found: BankTransaction | None = (
        BankTransaction.objects.select_related("bank_account", "contact", "journal_entry")
        .filter(public_id=public_id)
        .first()
    )
    if found is None:
        raise NotFound(_("That bank transaction doesn't exist."))
    return found


def _spec(data: dict[str, Any]) -> tuple[MoneySpec, list[Document]]:
    bank = BankAccount.objects.filter(
        public_id=data["bank_account"], deleted_at__isnull=True
    ).first()
    if bank is None:
        raise serializers.ValidationError({"bank_account": [_("That bank account doesn't exist.")]})
    ids = {line["account"] for line in data["lines"]}
    accounts = {a.public_id: a for a in Account.objects.filter(public_id__in=ids)}
    problems = {
        str(n): {"account": [_("That account doesn't exist.")]}
        for n, line in enumerate(data["lines"])
        if line["account"] not in accounts
    }
    if problems:
        raise serializers.ValidationError({"lines": problems})
    contact = None
    if data.get("contact"):
        contact = Contact.objects.filter(public_id=data["contact"], deleted_at__isnull=True).first()
        if contact is None:
            raise serializers.ValidationError({"contact": [_("That contact doesn't exist.")]})
    documents = list(Document.objects.filter(public_id__in=data.get("attachments") or []))
    if len(documents) != len(set(data.get("attachments") or [])):
        raise serializers.ValidationError({"attachments": [_("That document doesn't exist.")]})
    spec = MoneySpec(
        kind=data["kind"],
        bank_account=bank,
        date=data["date"],
        contact=contact,
        reference=data.get("reference") or "",
        tax_mode=data["tax_mode"],
        lines=[
            MoneyLine(
                accounts[line["account"]],
                line["amount"],
                description=line.get("description") or "",
                tax_code=line.get("tax_code") or "",
                taxes=[TaxPortion(t["role"], t["amount"], t["recoverable"]) for t in line["taxes"]],
                tracking=line.get("tracking") or {},
            )
            for line in data["lines"]
        ],
    )
    return spec, documents


class BankTransactionListView(APIView):
    queryset = BankTransaction._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_transactions_list", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        items = BankTransaction.objects.select_related("bank_account", "contact", "journal_entry")
        params = request.query_params
        if params.get("bank_account"):
            items = items.filter(bank_account__public_id=params["bank_account"])
        for field in ("kind", "status"):
            if params.get(field):
                items = items.filter(**{field: params[field]})
        if params.get("from"):
            items = items.filter(date__gte=params["from"])
        if params.get("to"):
            items = items.filter(date__lte=params["to"])
        return Response({"results": [transaction_row(t) for t in items[:500]]})

    @requires_permission(BANKING_TRANSACT.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_transactions_create",
        request=TransactionInputSerializer,
        responses={201: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        data = TransactionInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        spec, documents = _spec(dict(data.validated_data))
        try:
            txn = record_bank_transaction(
                spec,
                user=acting_user(),
                attachments=documents,
                override_reason=data.validated_data.get("override_reason") or "",
            )
        except JournalRuleError as error:
            return journal_refused(error)
        except LedgerError as error:
            return _error(error)
        return Response(transaction_row(_txn(txn.public_id), lines=True), status=201)


class BankTransactionDetailView(APIView):
    queryset = BankTransaction._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_transactions_read", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(transaction_row(_txn(public_id), lines=True))


class BankTransactionVoidView(APIView):
    queryset = BankTransaction._base_manager.none()

    @requires_permission(BANKING_TRANSACT.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_transactions_void", request=VoidInputSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        data = VoidInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        txn = _txn(public_id)
        if txn.status == BankTransactionStatus.VOIDED:
            return Response(
                {
                    "code": "banking.transaction.voided",
                    "detail": _("This transaction is already voided."),
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            void_bank_transaction(txn, date=data.validated_data.get("date"), user=acting_user())
        except LedgerError as error:
            return _error(error)
        return Response(transaction_row(_txn(public_id), lines=True))


# ---- account register (F-01-T11) ---------------------------------------------------------------


class RegisterQuerySerializer(serializers.Serializer[Any]):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    contact = serializers.UUIDField(required=False)
    amount_min = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    amount_max = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    status = serializers.ChoiceField(choices=["posted", "reversed"], required=False)
    #: ``format`` is DRF's content-negotiation parameter: the download is ``export``.
    export = serializers.ChoiceField(choices=["csv", "xlsx"], required=False)


def _register_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "received": _money(row["received"]) if row["received"] else None,
        "spent": _money(row["spent"]) if row["spent"] else None,
        "balance": _money(row["balance"]),
    }


class BankAccountRegisterView(APIView):
    """``GET bank-accounts/<id>/register`` — the transactions with their running balance;
    ``?export=csv|xlsx`` downloads the same rows."""

    queryset = BankAccount._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="bank_accounts_register",
        parameters=[RegisterQuerySerializer],
        responses={200: dict},
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response | HttpResponse:
        query = RegisterQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = dict(query.validated_data)
        fmt = data.pop("export", None)
        if data.get("contact"):
            data["contact"] = str(data["contact"])
        bank = _bank(public_id)
        rows = register(bank, RegisterFilters(**data))
        if fmt in ("csv", "xlsx"):
            content, content_type, name = export_register(bank, rows, fmt)
            response = HttpResponse(content, content_type=content_type)
            response["Content-Disposition"] = f'attachment; filename="{name}"'
            return response
        return Response(
            {
                "account": account_row(bank),
                "results": [_register_row(row) for row in rows],
            }
        )
