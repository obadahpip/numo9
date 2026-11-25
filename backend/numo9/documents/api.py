"""Document calculation API (D-01-T09), under ``/api/v1/o/<org>/``:

- ``POST documents/<side>/calculate`` — stateless: the ``DocumentCalculator`` result for the
  lines as typed (every line, totals, tax per component with its name) and the side validator's
  ``problems`` (D-01-T06) for the editor to flag, without refusing, and document ``warnings``
  (``REGISTRATION_STOPPED``: dated after a GST/HST or QST stop with that registration's codes,
  G-03b-T12);
- ``POST documents/<side>/posting-preview`` — the journal the document will post (D-01-T08);
  lines that don't fit are refused: 400 ``documents.lines.invalid`` with ``problems`` naming each
  line and field.

``<side>`` is ``sales`` (quotes, invoices, credit notes — ``kind`` defaults to ``invoice``) or
``purchases`` (bills, purchase orders, supplier credits — ``bill``). Body: ``{kind, date,
tax_mode, discount_type, discount_value, contact, lines: [{account, quantity, unit_price,
discount_type, discount_value, tax_code, description}]}`` — ``account``, ``tax_code`` (a code
version's id) and ``contact`` are public ids.

Permissions ``sales.document.view`` / ``purchases.document.view``; every package (core).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE, requires_feature
from numo9.contacts.models import Contact
from numo9.ledger.models import Account, LedgerError
from numo9.rbac.drf import requires_permission
from numo9.tax.models import TaxCode

from .calculator import AMOUNT, NONE, PERCENT, CalculationError, DocumentResult
from .models import TaxMode
from .permissions import PURCHASE_DOCUMENTS_VIEW, SALES_DOCUMENTS_VIEW
from .posting import PreviewLine, preview, result_for
from .validation import SIDES, DocumentInvalid, LineCheck, problems

DISCOUNTS = (NONE, AMOUNT, PERCENT)
DEFAULT_KIND = {"sales": "invoice", "purchase": "bill"}


class LineSerializer(serializers.Serializer[Any]):
    account = serializers.UUIDField(required=False, allow_null=True, default=None)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("1"))
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default=NONE)
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    tax_code = serializers.UUIDField(required=False, allow_null=True, default=None)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class DocumentSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=sorted(SIDES), required=False)
    date = serializers.DateField()
    tax_mode = serializers.ChoiceField(choices=TaxMode.choices, default=TaxMode.EXCLUSIVE)
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default=NONE)
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    contact = serializers.UUIDField(required=False, allow_null=True, default=None)
    lines = LineSerializer(many=True, max_length=500)  # type: ignore[call-arg]


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _rate(value: Decimal) -> str:
    text = f"{value.normalize():f}"
    return text


def _parse(side: str, request: Request) -> tuple[str, dict[str, Any], list[PreviewLine], Any]:
    data = DocumentSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    values = dict(data.validated_data)
    kind = values.get("kind") or DEFAULT_KIND[side]
    if SIDES[kind] != side:
        raise serializers.ValidationError(
            {"kind": [_("%(kind)s isn't a document of this side.") % {"kind": kind}]}
        )
    lines = values["lines"]
    account_ids = {line["account"] for line in lines if line["account"]}
    code_ids = {line["tax_code"] for line in lines if line["tax_code"]}
    accounts = {a.public_id: a for a in Account.objects.filter(public_id__in=account_ids)}
    codes = {
        c.public_id: c
        for c in TaxCode.objects.filter(public_id__in=code_ids).prefetch_related(
            "components__component"
        )
    }
    missing: dict[str, Any] = {}
    for number, line in enumerate(lines):
        if line["account"] and line["account"] not in accounts:
            missing.setdefault(str(number), {})["account"] = [_("That account doesn't exist.")]
        if line["tax_code"] and line["tax_code"] not in codes:
            missing.setdefault(str(number), {})["tax_code"] = [_("That tax code doesn't exist.")]
    if missing:
        raise serializers.ValidationError({"lines": missing})
    contact = None
    if values.get("contact"):
        contact = Contact.objects.filter(
            public_id=values["contact"], deleted_at__isnull=True
        ).first()
        if contact is None:
            raise serializers.ValidationError({"contact": [_("That contact doesn't exist.")]})
    parsed = [
        PreviewLine(
            account=accounts.get(line["account"]) if line["account"] else None,
            quantity=line["quantity"],
            unit_price=line["unit_price"],
            discount_type=line["discount_type"],
            discount_value=line["discount_value"],
            tax_code=codes.get(line["tax_code"]) if line["tax_code"] else None,
            description=line["description"],
        )
        for line in lines
    ]
    return kind, values, parsed, contact


def result_dict(result: DocumentResult, names: dict[str, str]) -> dict[str, Any]:
    return {
        "tax_mode": result.tax_mode,
        "lines": [
            {
                "gross": _money(line.gross),
                "line_discount": _money(line.line_discount),
                "net": _money(line.net),
                "discount_share": _money(line.discount_share),
                "taxable": _money(line.taxable),
                "exclusive": _money(line.exclusive),
                "tax": _money(line.tax),
                "taxes": [
                    {"key": t.key, "rate": _rate(t.rate), "amount": _money(t.amount)}
                    for t in line.taxes
                ],
            }
            for line in result.lines
        ],
        "subtotal": _money(result.subtotal),
        "discount_total": _money(result.discount_total),
        "tax_total": _money(result.tax_total),
        "total": _money(result.total),
        "net_total": _money(result.net_total),
        "tax_included": result.tax_included,
        "tax_by_component": [
            {"key": key, "name": names.get(key, key), "amount": _money(amount)}
            for key, amount in result.tax_by_component.items()
        ],
    }


def document_warnings(date: Any, lines: list[PreviewLine]) -> list[dict[str, Any]]:
    """Document-level warnings shown in the editor, never blocking: ``REGISTRATION_STOPPED`` —
    the date falls after a GST/HST or QST stop and a line uses that registration's tax codes
    (G-03b-T12)."""
    from numo9.tax.post_stop import stop_warning
    from numo9.tenancy.context import current_org

    organisation = current_org()
    if organisation is None:
        return []
    found = stop_warning(organisation, date, [line.tax_code for line in lines])
    return [found] if found else []


def _names(lines: list[PreviewLine]) -> dict[str, str]:
    names: dict[str, str] = {}
    for line in lines:
        if line.tax_code is not None:
            for link in line.tax_code.components.all():
                names.setdefault(link.component.key, link.component.name)
    return names


def _refused(error: Exception) -> Response:
    if isinstance(error, DocumentInvalid):
        return Response(
            {
                "code": error.code,
                "detail": error.messages[0],
                "problems": [p.as_dict() for p in error.problems],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    code = getattr(error, "code", "documents.calculation.invalid")
    detail = error.messages[0] if isinstance(error, LedgerError) else str(error)
    return Response({"code": code, "detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class _Calculate(APIView):
    side = "sales"

    def _calculate(self, request: Request) -> Response:
        kind, values, lines, _contact = _parse(self.side, request)
        found = problems(
            kind,
            values["date"],
            [LineCheck(line.account, line.tax_code) for line in lines],
            tax_mode=values["tax_mode"],
        )
        try:
            result = result_for(
                kind,
                lines,
                tax_mode=values["tax_mode"],
                discount_type=values["discount_type"],
                discount_value=values["discount_value"],
            )
        except (CalculationError, LedgerError) as error:
            return _refused(error)
        return Response(
            {
                "kind": kind,
                **result_dict(result, _names(lines)),
                "problems": [p.as_dict() for p in found],
                "warnings": document_warnings(values["date"], lines),
            }
        )


class _Preview(APIView):
    side = "sales"

    def _preview(self, request: Request) -> Response:
        kind, values, lines, contact = _parse(self.side, request)
        try:
            found = preview(
                kind,
                values["date"],
                lines,
                tax_mode=values["tax_mode"],
                discount_type=values["discount_type"],
                discount_value=values["discount_value"],
                contact=contact,
            )
        except (CalculationError, LedgerError) as error:
            return _refused(error)
        return Response(
            {"kind": kind, **result_dict(found.result, _names(lines)), "journal": found.as_dict()}
        )


class SalesCalculateView(_Calculate):
    queryset = TaxCode._base_manager.none()
    side = "sales"

    @requires_permission(SALES_DOCUMENTS_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="documents_sales_calculate", request=DocumentSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        return self._calculate(request)


class PurchaseCalculateView(_Calculate):
    queryset = TaxCode._base_manager.none()
    side = "purchase"

    @requires_permission(PURCHASE_DOCUMENTS_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="documents_purchases_calculate",
        request=DocumentSerializer,
        responses={200: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        return self._calculate(request)


class SalesPreviewView(_Preview):
    queryset = TaxCode._base_manager.none()
    side = "sales"

    @requires_permission(SALES_DOCUMENTS_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="documents_sales_posting_preview",
        request=DocumentSerializer,
        responses={200: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        return self._preview(request)


class PurchasePreviewView(_Preview):
    queryset = TaxCode._base_manager.none()
    side = "purchase"

    @requires_permission(PURCHASE_DOCUMENTS_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="documents_purchases_posting_preview",
        request=DocumentSerializer,
        responses={200: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        return self._preview(request)
