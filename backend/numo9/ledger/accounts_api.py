"""Chart of accounts API (C-01-T09), under ``/api/v1/o/<org>/``.

- ``GET accounts`` — the chart, by code: every field, the depth in the tree, whether it has
  sub-accounts, the GIFI code and description and the balance in each book (posted and reversed
  entries). Filters ``status`` (``active`` default, ``archived``, ``all``), ``type``, ``q`` (code or
  name). ``GET accounts/tree`` — the same rows nested under their parents.
- ``POST accounts`` — add an account; ``GET``/``PATCH``/``DELETE accounts/<id>`` — read, edit
  (a new ``code`` goes through the renumber service), delete (refused for system accounts and
  accounts with transactions: archive them).
- ``POST accounts/<id>/renumber`` ``{code}``; ``POST accounts/<id>/archive``; ``…/restore``.
- ``POST accounts/bulk`` ``{accounts: [ids], action, value}`` — ``archive``, ``restore``,
  ``set_gifi``, ``set_tax_default`` on many accounts; each account succeeds or fails on its own
  and the response lists every outcome with its reason.
- ``GET gifi`` ``?q=&type=`` — GIFI codes to map an account to (the drawer's picker).

Rules live in the model and the services (C-01-T02…T08); their refusals come back as
``{"detail", "code"}`` (400). Permissions ``accounting.accounts.view`` / ``.manage``; features
``accounting.chart_of_accounts.read`` / ``.write``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .archive import archive_account, restore_account
from .gifi import search as search_gifi
from .models import (
    LOCKED_STATUSES,
    Account,
    AccountStatus,
    AccountSubtype,
    AccountType,
    Book,
    GifiCode,
    JournalLine,
    SystemRole,
)
from .permissions import ACCOUNTS_MANAGE, ACCOUNTS_VIEW
from .renumber import acting_as, renumber_account

READ = "accounting.chart_of_accounts.read"
WRITE = "accounting.chart_of_accounts.write"
ZERO = Decimal("0.00")
BULK_ACTIONS = ("archive", "restore", "set_gifi", "set_tax_default")
MAX_BULK = 500


class Refused(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid"


def refused(error: DjangoValidationError) -> Refused:
    message = " ".join(str(m) for m in error.messages)
    return Refused(detail=message, code=getattr(error, "code", None) or "invalid")


# ---- reading -----------------------------------------------------------------------------------


def _balances(organisation: Any, ids: list[int] | None = None) -> dict[int, dict[str, Decimal]]:
    lines = JournalLine.objects.filter(entry__status__in=sorted(LOCKED_STATUSES))
    if ids is not None:
        lines = lines.filter(account_id__in=ids)
    found: dict[int, dict[str, Decimal]] = {}
    for row in (
        lines.values("account_id", "book")
        .annotate(net=Coalesce(Sum("debit"), ZERO) - Coalesce(Sum("credit"), ZERO))
        .order_by()
    ):
        sums = found.setdefault(row["account_id"], {Book.ACCOUNTING: ZERO, Book.TAX: ZERO})
        for book in (Book.ACCOUNTING, Book.TAX):
            if row["book"] in (Book.BOTH, book):
                sums[book] += row["net"]
    return found


def _depths(accounts: list[Account]) -> dict[int, int]:
    parents = {a.pk: a.parent_id for a in Account._base_manager.filter(organisation=current_org())}
    depths: dict[int, int] = {}
    for account in accounts:
        depth, cursor = 1, parents.get(account.pk)
        while cursor is not None and depth < 10:
            depth, cursor = depth + 1, parents.get(cursor)
        depths[account.pk] = depth
    return depths


def _row(
    account: Account,
    balances: dict[int, dict[str, Decimal]],
    depths: dict[int, int],
    parents_with_children: set[int],
) -> dict[str, Any]:
    sums = balances.get(account.pk, {Book.ACCOUNTING: ZERO, Book.TAX: ZERO})
    return {
        "id": str(account.public_id),
        "code": account.code,
        "name": account.name,
        "name_i18n": account.name_i18n,
        "description": account.description,
        "type": account.type,
        "type_label": str(AccountType(account.type).label),
        "subtype": account.subtype,
        "subtype_label": str(AccountSubtype(account.subtype).label),
        "parent": str(account.parent.public_id) if account.parent_id else None,  # type: ignore[union-attr]
        "depth": depths.get(account.pk, 1),
        "has_children": account.pk in parents_with_children,
        "system_role": account.system_role,
        "system_role_label": str(SystemRole(account.system_role).label)
        if account.system_role
        else "",
        "is_bank": account.is_bank,
        "gifi": {"code": account.gifi.code, "description": account.gifi.description}
        if account.gifi is not None
        else None,
        "require_contact": account.require_contact,
        "require_tracking": account.require_tracking,
        "require_attachment": account.require_attachment,
        "default_tax_key": account.default_tax_key,
        "status": account.status,
        "archived_at": account.archived_at,
        "balance": {book: f"{value:.2f}" for book, value in sums.items()},
    }


def _queryset() -> QuerySet[Account]:
    return (
        Account.objects.filter(deleted_at__isnull=True)
        .select_related("parent", "gifi")
        .order_by("code", "pk")
    )


def _rows(accounts: list[Account]) -> list[dict[str, Any]]:
    organisation = current_org()
    balances = _balances(organisation, [a.pk for a in accounts])
    depths = _depths(accounts)
    with_children = set(
        Account._base_manager.filter(
            organisation=organisation, parent__isnull=False, deleted_at__isnull=True
        )
        .exclude(status=AccountStatus.ARCHIVED)
        .values_list("parent_id", flat=True)
    )
    return [_row(a, balances, depths, with_children) for a in accounts]


def _filtered(params: Any) -> list[Account]:
    queryset = _queryset()
    wanted = params.get("status", "active")
    if wanted in (AccountStatus.ACTIVE, AccountStatus.ARCHIVED):
        queryset = queryset.filter(status=wanted)
    if params.get("type") in AccountType.values:
        queryset = queryset.filter(type=params["type"])
    text = (params.get("q") or "").strip()
    if text:
        queryset = queryset.filter(
            Q(code__istartswith=text)
            | Q(name_i18n__icontains=text)
            | Q(description__icontains=text)
        )
    return list(queryset)


def _one(public_id: Any, *, lock: bool = False) -> Account:
    queryset = _queryset().select_for_update(of=("self",)) if lock else _queryset()
    account = queryset.filter(public_id=public_id).first()
    if account is None:
        raise NotFound
    return account


# ---- writing -----------------------------------------------------------------------------------


class AccountWriteSerializer(serializers.Serializer[Any]):
    code = serializers.CharField(max_length=10, required=False)
    name = serializers.CharField(max_length=200, required=False)
    name_i18n = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    type = serializers.ChoiceField(choices=AccountType.choices, required=False)
    subtype = serializers.ChoiceField(choices=AccountSubtype.choices, required=False)
    parent = serializers.UUIDField(allow_null=True, required=False)  # type: ignore[assignment]
    system_role = serializers.ChoiceField(
        choices=[("", "")] + list(SystemRole.choices), allow_blank=True, required=False
    )
    is_bank = serializers.BooleanField(required=False)
    gifi = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    require_contact = serializers.BooleanField(required=False)
    require_tracking = serializers.BooleanField(required=False)
    require_attachment = serializers.BooleanField(required=False)
    default_tax_key = serializers.CharField(allow_blank=True, max_length=40, required=False)


def _apply(account: Account, data: dict[str, Any]) -> None:
    from .models import SUBTYPE_TYPE

    if "name" in data:
        account.name_i18n = {**(account.name_i18n or {}), "en-ca": data["name"]}
    if "name_i18n" in data:
        account.name_i18n = {k.lower(): v for k, v in data["name_i18n"].items()}
    for field in (
        "description",
        "system_role",
        "is_bank",
        "require_contact",
        "require_tracking",
        "require_attachment",
        "default_tax_key",
    ):
        if field in data:
            setattr(account, field, data[field])
    if "subtype" in data:
        account.subtype = data["subtype"]
        account.type = data.get("type") or SUBTYPE_TYPE[data["subtype"]]
    elif "type" in data:
        account.type = data["type"]
    if "parent" in data:
        if data["parent"] is None:
            account.parent = None
        else:
            parent = Account.objects.filter(public_id=data["parent"]).first()
            if parent is None:
                raise Refused(_("The parent account doesn't exist."), code="ledger.account.parent")
            account.parent = parent
    if "gifi" in data:
        code = (data["gifi"] or "").strip()
        account.gifi_id = code or None  # GifiCode's key is its code
        if code and not GifiCode.objects.filter(code=code).exists():
            raise Refused(
                _("GIFI %(code)s isn't in the CRA list.") % {"code": code},
                code="ledger.account.gifi_unknown",
            )


def _save(account: Account) -> None:
    try:
        with transaction.atomic():
            account.save()
    except DjangoValidationError as error:
        raise refused(error) from None
    except IntegrityError:
        holder = (
            Account._base_manager.filter(
                organisation_id=account.organisation_id, code__iexact=account.code
            )
            .exclude(pk=account.pk)
            .first()
        )
        if holder is None:
            raise
        raise Refused(
            _("%(account)s already has the code %(code)s.")
            % {"account": holder, "code": account.code},
            code="ledger.account.code_taken",
        ) from None


ORG_PARAM = OpenApiParameter("org", OpenApiTypes.UUID, OpenApiParameter.PATH)


class AccountListView(APIView):
    queryset = Account._base_manager.none()  # tenant sweep: rows of Account

    @requires_permission(ACCOUNTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="accounts_list",
        summary="The chart of accounts with balances",
        parameters=[
            OpenApiParameter("status", str, enum=["active", "archived", "all"]),
            OpenApiParameter("type", str, enum=list(AccountType.values)),
            OpenApiParameter("q", str),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        rows = _rows(_filtered(request.query_params))
        return Response({"results": rows, "count": len(rows)})

    @requires_permission(ACCOUNTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="accounts_create",
        summary="Add an account",
        request=AccountWriteSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = AccountWriteSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        data = dict(incoming.validated_data)
        if not data.get("code") or not (data.get("name") or data.get("name_i18n")):
            raise Refused(_("An account needs a code and a name."), code="ledger.account.required")
        if "subtype" not in data:
            raise Refused(_("Choose the account's type."), code="ledger.account.subtype_required")
        account = Account(organisation=current_org(), code=data.pop("code").strip())
        _apply(account, data)
        with acting_as(request.user), transaction.atomic():
            _save(account)
        return Response(_rows([_one(account.public_id)])[0], status=201)


class AccountTreeView(APIView):
    queryset = Account._base_manager.none()

    @requires_permission(ACCOUNTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="accounts_tree",
        summary="The chart of accounts as a tree",
        parameters=[OpenApiParameter("status", str, enum=["active", "archived", "all"])],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        rows = _rows(_filtered({"status": request.query_params.get("status", "active")}))
        by_id = {row["id"]: {**row, "children": []} for row in rows}
        roots: list[dict[str, Any]] = []
        for row in by_id.values():
            parent = by_id.get(row["parent"] or "")
            (parent["children"] if parent else roots).append(row)
        return Response({"results": roots, "count": len(rows)})


class AccountDetailView(APIView):
    queryset = Account._base_manager.none()

    @requires_permission(ACCOUNTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="accounts_get", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(_rows([_one(public_id)])[0])

    @requires_permission(ACCOUNTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="accounts_update",
        summary="Edit an account (a new code is a renumber)",
        request=AccountWriteSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        _one(public_id)  # 404 before anything about the body
        incoming = AccountWriteSerializer(data=request.data, partial=True)
        incoming.is_valid(raise_exception=True)
        data = dict(incoming.validated_data)
        with acting_as(request.user), transaction.atomic():
            account = _one(public_id, lock=True)
            code = data.pop("code", None)
            if code is not None and code.strip() != account.code:
                try:
                    renumber_account(account, code, actor=request.user)
                except DjangoValidationError as error:
                    raise refused(error) from None
                account = _one(public_id, lock=True)
            if data:
                _apply(account, data)
                _save(account)
        return Response(_rows([_one(public_id)])[0])

    @requires_permission(ACCOUNTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="accounts_delete",
        summary="Delete an account without transactions (others: archive)",
        responses={204: None},
    )
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        with acting_as(request.user), transaction.atomic():
            account = _one(public_id, lock=True)
            try:
                account.soft_delete()
            except DjangoValidationError as error:
                raise refused(error) from None
        return Response(status=204)


class RenumberSerializer(serializers.Serializer[Any]):
    code = serializers.CharField(max_length=20)


class AccountRenumberView(APIView):
    queryset = Account._base_manager.none()

    @requires_permission(ACCOUNTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="accounts_renumber",
        summary="Give an account a new code (every reference keeps pointing to it)",
        request=RenumberSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        account = _one(public_id)  # 404 before anything about the body
        incoming = RenumberSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        try:
            renumber_account(account, incoming.validated_data["code"], actor=request.user)
        except DjangoValidationError as error:
            raise refused(error) from None
        return Response(_rows([_one(public_id)])[0])


class AccountArchiveView(APIView):
    queryset = Account._base_manager.none()
    restore = False

    @requires_permission(ACCOUNTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="accounts_archive",
        summary="Archive (zero balance, not a system account) or restore an account",
        request=None,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        service = restore_account if self.restore else archive_account
        try:
            service(_one(public_id), actor=request.user)
        except DjangoValidationError as error:
            raise refused(error) from None
        return Response(_rows([_one(public_id)])[0])


class BulkSerializer(serializers.Serializer[Any]):
    accounts = serializers.ListField(
        child=serializers.UUIDField(), min_length=1, max_length=MAX_BULK
    )
    action = serializers.ChoiceField(choices=[(a, a) for a in BULK_ACTIONS])
    value = serializers.CharField(allow_blank=True, required=False, default="")


class AccountBulkView(APIView):
    @requires_permission(ACCOUNTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="accounts_bulk",
        summary="Archive, restore, set GIFI or set the tax default on many accounts",
        request=BulkSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = BulkSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        action, value = incoming.validated_data["action"], incoming.validated_data["value"]
        accounts = {
            a.public_id: a
            for a in _queryset().filter(public_id__in=incoming.validated_data["accounts"])
        }
        outcomes = []
        for public_id in incoming.validated_data["accounts"]:
            account = accounts.get(public_id)
            if account is None:
                outcomes.append({"id": str(public_id), "ok": False, "detail": _("Not found.")})
                continue
            try:
                with acting_as(request.user), transaction.atomic():
                    if action == "archive":
                        archive_account(account, actor=request.user)
                    elif action == "restore":
                        restore_account(account, actor=request.user)
                    else:
                        locked = _one(public_id, lock=True)
                        _apply(
                            locked,
                            {"gifi": value} if action == "set_gifi" else {"default_tax_key": value},
                        )
                        _save(locked)
                outcomes.append({"id": str(public_id), "code": account.code, "ok": True})
            except (DjangoValidationError, APIException) as error:
                detail = (
                    " ".join(str(m) for m in error.messages)
                    if isinstance(error, DjangoValidationError)
                    else str(error.detail)
                )
                outcomes.append(
                    {"id": str(public_id), "code": account.code, "ok": False, "detail": detail}
                )
        done = sum(1 for o in outcomes if o["ok"])
        return Response(
            {"action": action, "done": done, "failed": len(outcomes) - done, "results": outcomes}
        )


class GifiSearchView(APIView):
    @requires_permission(ACCOUNTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="gifi_search",
        summary="GIFI codes to map an account to (by number or description)",
        parameters=[
            OpenApiParameter("q", str),
            OpenApiParameter("type", str, enum=list(AccountType.values)),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        kind = request.query_params.get("type")
        rows = search_gifi(
            request.query_params.get("q", ""),
            account_type=kind if kind in AccountType.values else None,
        )
        return Response(
            {
                "results": [
                    {"code": g.code, "description": g.description, "section": g.section}
                    for g in rows
                ]
            }
        )
