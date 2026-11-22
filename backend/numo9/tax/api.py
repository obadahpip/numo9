"""Tax codes and rates API (G-01-T11), under ``/api/v1/o/<org>/tax/``.

- ``GET tax/components`` ``?key=&date=&expired=1`` — component versions (rate, range, kind,
  authority, recoverable, side, control accounts).
- ``POST tax/components`` — add a component version (a new key or the next version of one);
  ``PATCH tax/components/<id>`` — rename (en / fr), end it, or correct the rate while no posted
  line used it (409 otherwise). Every change is audited, attributed to the person (G-01-T16).
- ``GET tax/codes`` ``?side=sales|purchase&date=YYYY-MM-DD&expired=1&q=`` — the code versions
  **in force on the date** (today by default) for the side: what a picker offers — a sales list
  never holds purchase codes; ``expired=1`` adds ended versions (the "Show expired" toggle);
  archived codes only with ``archived=1``. Each row: type and badge label, components with
  rates, range, version, claimable %, and how many posted journal lines used the code.
- ``POST tax/codes`` — define a code (version 1) with its components.
- ``GET tax/codes/<id>`` — one version with every version of its code (the timeline);
  ``PATCH`` renames it (en / fr).
- ``POST tax/codes/<id>/versions`` ``{effective_from, components, name}`` — revise (G-01-T10).
- ``POST tax/codes/<id>/archive`` / ``…/restore`` — every version of the code; ``DELETE`` only
  while no posted line used it (409 otherwise: archive it).
- ``POST tax/calculate`` ``{code, amount, inclusive, account}`` — the calculator (G-01-T06) for
  the editor's live example.

Reading is part of every package (CORE: every document needs tax codes; the plan's
``tax.core``); writing needs ``tax.codes.write``. Permissions ``tax.codes.view`` / ``tax.manage``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE, requires_feature
from numo9.ledger.models import Account, JournalLine
from numo9.orgsettings.locks import local_date
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .calculator import calculate
from .codes import define_code, revise_code
from .models import (
    ComponentSide,
    TaxAuthority,
    TaxCode,
    TaxCodeType,
    TaxComponent,
    TaxKind,
    TaxSide,
)
from .permissions import TAX_MANAGE, TAX_VIEW
from .resolver import active_q
from .seed import ensure_tax_table

WRITE = "tax.codes.write"


def _refused(error: DjangoValidationError, code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {
            "code": getattr(error, "code", None) or "invalid",
            "detail": " ".join(str(m) for m in error.messages),
        },
        status=code,
    )


def _today() -> dt.date:
    organisation = current_org()
    if organisation is None:
        return timezone.localdate()
    return local_date(organisation, timezone.now())


def _money(value: Any) -> str:
    return f"{value:.2f}"


def _rate(value: Any) -> str:
    return f"{value.normalize():f}"


def component_row(component: TaxComponent) -> dict[str, Any]:
    return {
        "id": str(component.public_id),
        "key": component.key,
        "name": component.name,
        "name_i18n": component.name_i18n,
        "kind": component.kind,
        "authority": component.authority.code,
        "rate": _rate(component.rate),
        "effective_from": component.effective_from,
        "effective_to": component.effective_to,
        "recoverable": component.recoverable,
        "side": component.side,
        "control_account_sales": component.control_account_sales.code
        if component.control_account_sales
        else None,
        "control_account_purchase": component.control_account_purchase.code
        if component.control_account_purchase
        else None,
    }


def code_row(code: TaxCode, usage: dict[str, int], today: dt.date) -> dict[str, Any]:
    parts = list(code.components.select_related("component").order_by("position"))
    return {
        "id": str(code.public_id),
        "code": code.code,
        "version": code.version,
        "name": code.name,
        "name_i18n": code.name_i18n,
        "side": code.side,
        "type": code.type,
        "type_label": str(TaxCodeType(code.type).label),
        "province": code.province,
        "effective_from": code.effective_from,
        "effective_to": code.effective_to,
        "expired": code.effective_to is not None and code.effective_to < today,
        "archived_at": code.archived_at,
        "itc_restriction_pct": None
        if code.itc_restriction_pct is None
        else _rate(code.itc_restriction_pct),
        "rate": _rate(sum((p.component.rate for p in parts), Decimal("0"))),
        "components": [
            {
                "id": str(p.component.public_id),
                "key": p.component.key,
                "name": p.component.name,
                "kind": p.component.kind,
                "rate": _rate(p.component.rate),
                "recoverable_pct": None if p.recoverable_pct is None else _rate(p.recoverable_pct),
            }
            for p in parts
        ],
        "usage_count": usage.get(code.code, 0),
    }


def _usage(keys: set[str]) -> dict[str, int]:
    rows = (
        JournalLine.objects.filter(tax_code__in=sorted(keys))
        .values("tax_code")
        .annotate(n=Count("pk"))
        .order_by()
    )
    return {row["tax_code"]: row["n"] for row in rows}


def _date(request: Request) -> dt.date:
    text = request.query_params.get("date")
    if not text:
        return _today()
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise serializers.ValidationError(
            {"date": [_("Use the date format YYYY-MM-DD.")]}
        ) from None


def _code(public_id: Any) -> TaxCode:
    found: TaxCode | None = TaxCode.objects.filter(public_id=public_id).first()
    if found is None:
        raise NotFound(_("That tax code doesn't exist."))
    return found


# ---- components --------------------------------------------------------------------------------


class ComponentInputSerializer(serializers.Serializer[Any]):
    key = serializers.RegexField(r"^[a-z][a-z0-9_]{1,39}$")
    name = serializers.CharField(max_length=120)
    name_fr = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    kind = serializers.ChoiceField(choices=TaxKind.choices)
    authority = serializers.CharField(max_length=10)
    rate = serializers.DecimalField(max_digits=7, decimal_places=4, min_value=0, max_value=100)
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True, default=None)
    recoverable = serializers.BooleanField(required=False, default=True)
    side = serializers.ChoiceField(
        choices=ComponentSide.choices, required=False, default=ComponentSide.BOTH
    )


class ComponentPatchSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=120, required=False)
    name_fr = serializers.CharField(max_length=120, required=False, allow_blank=True)
    rate = serializers.DecimalField(
        max_digits=7, decimal_places=4, min_value=0, max_value=100, required=False
    )
    effective_to = serializers.DateField(required=False, allow_null=True)


def _component_used(component: TaxComponent) -> int:
    keys = set(component.codes.values_list("tax_code__code", flat=True))
    return sum(_usage(keys).values()) if keys else 0


class TaxComponentDetailView(APIView):
    """``PATCH tax/components/<id>`` — rename (en / fr), correct the rate of a component no
    posted line used yet, or end it (``effective_to``); every change is audited, attributed to
    the person (old and new values)."""

    queryset = TaxComponent._base_manager.none()

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="tax_components_update",
        request=ComponentPatchSerializer,
        responses={200: dict},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        component: TaxComponent | None = TaxComponent.objects.filter(public_id=public_id).first()
        if component is None:
            raise NotFound(_("That tax component doesn't exist."))
        data = ComponentPatchSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        if "rate" in values and values["rate"] != component.rate:
            used = _component_used(component)
            if used:
                return Response(
                    {
                        "code": "tax.component.in_use",
                        "detail": _(
                            "%(component)s is used on %(count)d posted lines: add a new version "
                            "from a date instead of changing its rate."
                        )
                        % {"component": component.key, "count": used},
                        "count": used,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            component.rate = values["rate"]
        names = dict(component.name_i18n or {})
        if values.get("name"):
            names["en-ca"] = values["name"]
        if "name_fr" in values:
            names["fr-ca"] = values["name_fr"]
        component.name_i18n = names
        if "effective_to" in values:
            component.effective_to = values["effective_to"]
        try:
            component.save()
        except DjangoValidationError as error:
            return _refused(error)
        return Response(component_row(component))


class TaxComponentListView(APIView):
    queryset = TaxComponent._base_manager.none()

    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_components_list", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        ensure_tax_table(current_org())
        items = TaxComponent.objects.select_related(
            "authority", "control_account_sales", "control_account_purchase"
        )
        if request.query_params.get("key"):
            items = items.filter(key=request.query_params["key"])
        if request.query_params.get("expired") != "1":
            items = items.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=_date(request)))
        return Response({"results": [component_row(c) for c in items]})

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="tax_components_create",
        request=ComponentInputSerializer,
        responses={201: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        data = ComponentInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        organisation = current_org()
        ensure_tax_table(organisation)
        authority = TaxAuthority.objects.filter(code=values.pop("authority").upper()).first()
        if authority is None:
            raise serializers.ValidationError({"authority": [_("Unknown tax authority.")]})
        names = {"en-ca": values.pop("name")}
        if values.get("name_fr"):
            names["fr-ca"] = values["name_fr"]
        values.pop("name_fr", None)
        component = TaxComponent(
            organisation=organisation, authority=authority, name_i18n=names, **values
        )
        try:
            component.save()
        except DjangoValidationError as error:
            return _refused(error)
        return Response(component_row(component), status=status.HTTP_201_CREATED)


# ---- codes -------------------------------------------------------------------------------------


class CodeComponentSerializer(serializers.Serializer[Any]):
    component = serializers.UUIDField()
    recoverable_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, allow_null=True
    )


class CodeInputSerializer(serializers.Serializer[Any]):
    code = serializers.RegexField(r"^[a-z][A-Za-z0-9_.]{1,59}$")
    name = serializers.CharField(max_length=150)
    name_fr = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    side = serializers.ChoiceField(choices=TaxSide.choices)
    type = serializers.ChoiceField(choices=TaxCodeType.choices)
    province = serializers.CharField(max_length=2, required=False, allow_blank=True, default="")
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True, default=None)
    itc_restriction_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, allow_null=True
    )
    components = CodeComponentSerializer(many=True, required=False, default=list)


class VersionInputSerializer(serializers.Serializer[Any]):
    effective_from = serializers.DateField()
    name = serializers.CharField(max_length=150, required=False)
    components = CodeComponentSerializer(many=True)


def _components(rows: list[dict[str, Any]]) -> list[tuple[TaxComponent, Any]]:
    ids = [row["component"] for row in rows]
    found = {c.public_id: c for c in TaxComponent.objects.filter(public_id__in=ids)}
    missing = [str(i) for i in ids if i not in found]
    if missing:
        raise serializers.ValidationError({"components": [_("Unknown tax component.")]})
    return [(found[row["component"]], row.get("recoverable_pct")) for row in rows]


class TaxCodeListView(APIView):
    queryset = TaxCode._base_manager.none()

    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_codes_list", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        ensure_tax_table(current_org())
        params = request.query_params
        day = _date(request)
        items = TaxCode.objects.all()
        if params.get("side"):
            if params["side"] not in TaxSide.values:
                raise serializers.ValidationError({"side": [_("Use sales or purchase.")]})
            items = items.filter(side=params["side"])
        if params.get("archived") != "1":
            items = items.filter(archived_at__isnull=True)
        if params.get("expired") == "1":
            items = items.filter(effective_from__lte=day)
        else:
            items = items.filter(active_q(day))
        if params.get("q"):
            q = params["q"]
            items = items.filter(Q(code__icontains=q) | Q(name_i18n__icontains=q))
        rows = list(items.order_by("side", "code", "-version"))
        usage = _usage({c.code for c in rows})
        today = _today()
        return Response({"date": day, "results": [code_row(c, usage, today) for c in rows]})

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="tax_codes_create", request=CodeInputSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        data = CodeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        organisation = current_org()
        ensure_tax_table(organisation)
        if TaxCode.objects.filter(code=values["code"]).exists():
            return Response(
                {
                    "code": "tax.code.exists",
                    "detail": _("%(code)s already exists: add a version to it instead.")
                    % {"code": values["code"]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        components = _components(values.pop("components"))
        try:
            code = define_code(organisation, components=components, version=1, **values)  # type: ignore[arg-type]
        except DjangoValidationError as error:
            return _refused(error)
        return Response(code_row(code, {}, _today()), status=status.HTTP_201_CREATED)


class CodePatchSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=150, required=False)
    name_fr = serializers.CharField(max_length=150, required=False, allow_blank=True)


class TaxCodeDetailView(APIView):
    queryset = TaxCode._base_manager.none()

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="tax_codes_update", request=CodePatchSerializer, responses={200: dict}
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        """Rename a version (English / French): names never change a calculation."""
        code = _code(public_id)
        data = CodePatchSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        names = dict(code.name_i18n or {})
        if data.validated_data.get("name"):
            names["en-ca"] = data.validated_data["name"]
        if "name_fr" in data.validated_data:
            names["fr-ca"] = data.validated_data["name_fr"]
        code.name_i18n = names
        code.save(update_fields=["name_i18n", "updated_at"])
        return Response(code_row(code, _usage({code.code}), _today()))

    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_codes_read", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        code = _code(public_id)
        versions = list(TaxCode.objects.filter(code=code.code).order_by("version"))
        usage = _usage({code.code})
        today = _today()
        return Response(
            {
                **code_row(code, usage, today),
                "versions": [code_row(v, usage, today) for v in versions],
            }
        )

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="tax_codes_delete", responses={204: None, 409: dict})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        code = _code(public_id)
        used = _usage({code.code}).get(code.code, 0)
        if used:
            return Response(
                {
                    "code": "tax.code.in_use",
                    "detail": _("%(code)s is used on %(count)d posted lines: archive it instead.")
                    % {"code": code.code, "count": used},
                    "count": used,
                },
                status=status.HTTP_409_CONFLICT,
            )
        TaxCode.objects.filter(code=code.code).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TaxCodeVersionView(APIView):
    queryset = TaxCode._base_manager.none()

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="tax_codes_version", request=VersionInputSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        current = _code(public_id)  # another organisation's id: 404 before any validation
        data = VersionInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        try:
            code = revise_code(
                current,
                effective_from=values["effective_from"],
                components=_components(values["components"]),
                name=values.get("name"),
            )
        except DjangoValidationError as error:
            return _refused(error)
        return Response(code_row(code, {}, _today()), status=status.HTTP_201_CREATED)


class TaxCodeArchiveView(APIView):
    queryset = TaxCode._base_manager.none()
    restore = False

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="tax_codes_archive", request=None, responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        code = _code(public_id)
        when = None if self.restore else timezone.now()
        for version in TaxCode.objects.filter(code=code.code):
            version.archived_at = when
            version.save(update_fields=["archived_at", "updated_at"])
        code.refresh_from_db()
        return Response(code_row(code, _usage({code.code}), _today()))


class TaxCodeRestoreView(TaxCodeArchiveView):
    restore = True

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="tax_codes_restore", request=None, responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return super().post(request, org, public_id)


class CalculateInputSerializer(serializers.Serializer[Any]):
    code = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    inclusive = serializers.BooleanField(required=False, default=False)
    account = serializers.UUIDField(required=False, allow_null=True, default=None)


class TaxCalculateView(APIView):
    queryset = TaxCode._base_manager.none()

    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_calculate", request=CalculateInputSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        data = CalculateInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        code = _code(values["code"])
        account = None
        if values.get("account"):
            account = Account.objects.filter(public_id=values["account"]).first()
        out = calculate(code, values["amount"], inclusive=values["inclusive"], account=account)
        return Response(
            {
                "net": _money(out.net),
                "tax": _money(out.tax),
                "gross": _money(out.gross),
                "claimable": _money(out.claimable),
                "cost": _money(out.cost),
                "components": [
                    {
                        "key": c.key,
                        "name": c.link.component.name,
                        "rate": _rate(c.rate),
                        "amount": _money(c.amount),
                        "claimable": _money(c.claimable),
                        "cost": _money(c.cost),
                    }
                    for c in out.components
                ],
            }
        )
