"""Bills API (E-02-T10), under ``/api/v1/o/<org>/``. Feature keys ``accounting.bills.read`` /
``.write`` / ``.approve``; permissions ``purchases.bills.view`` / ``.write`` / ``.approve``.

- ``GET bills`` — the list: ``tab`` (all, draft, awaiting_approval, awaiting_payment, overdue,
  paid, void — ``overview.tab_filter``), ``status`` (one or comma-separated), ``supplier``, ``q``
  (number, supplier invoice number, reference, supplier name), ``page``; 50 a page, newest first,
  with counts per status and the count and amount of every tab (``tabs``: the same query as the
  overview tiles, E-02-T15);
- ``GET bills/overview`` — the purchases overview (E-02-T15): ``tiles`` (Draft, Awaiting approval,
  Awaiting payment, Overdue — count and amount, the tabs' own numbers), ``aging`` (what is owed by
  age) and ``top_suppliers``; ``section=tiles|aging|suppliers`` answers one card only;
- ``POST bills`` — a draft: ``supplier``, ``date``, ``due_date``, ``supplier_invoice_no``,
  ``reference``, ``terms``, ``tax_mode``, discount, ``department``, ``notes``, holdback, ``lines``
  and an optional ``document`` (a file of the documents inbox, attached: the editor's split view,
  E-02-T11); 400 ``purchases.bill.duplicate_number`` for a supplier invoice number already used;
- ``GET`` / ``PATCH`` / ``DELETE bills/<id>`` — a bill; edit and delete drafts only (409 when the
  ``version`` sent isn't the bill's: someone else saved first); a deleted draft is kept (soft);
- ``GET bills/<id>/preview`` — the journal it posts, the ITC split per line, the routing
  explanation, duplicate suspects and the PO match panel (the editor's side panels);
- ``POST bills/<id>/submit`` · ``/approve`` (``with_variance``) · ``/void`` (``date``, ``reason``)
  · ``/release-holdback`` (``amount``, ``date``);
- ``POST bills/from-po`` — ``purchase_order`` (and ``receipt``): the draft bill of what was
  received and isn't billed (E-02-T08);
- ``GET bills/duplicates`` — the duplicate review list (E-02-T03);
- ``GET bills/check-number?supplier=<contact id>&number=<supplier invoice no>&exclude=<bill id>``
  — the live supplier-invoice-number check of the bill editor (E-02-T02, gap-24): ``available``
  and, when taken, the bill that has it (``number``, ``date``, ``url``) with the message the
  editor shows ("Already used on BILL-0042 (12 Sep 2026)").
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.documents.calculator import AMOUNT, NONE, PERCENT
from numo9.documents.formatting import format_date
from numo9.documents.models import TaxMode
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from . import overview
from .models import Bill, BillLine, BillStatus, HoldbackType
from .permissions import BILLS_APPROVE, BILLS_VIEW, BILLS_WRITE
from .uniqueness import normalise, number_conflict

READ = "accounting.bills.read"
WRITE = "accounting.bills.write"
APPROVE = "accounting.bills.approve"


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


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


# ---- payloads ------------------------------------------------------------------------------

PAGE_SIZE = 50
DISCOUNTS = (NONE, AMOUNT, PERCENT)


def _money(value: Any) -> str:
    return f"{Decimal(value):.2f}"


def line_row(line: BillLine) -> dict[str, Any]:
    return {
        "id": str(line.public_id),
        "position": line.position,
        "description": line.description,
        "quantity": f"{line.quantity:.4f}",
        "unit_price": f"{line.unit_price:.4f}",
        "discount_type": line.discount_type,
        "discount_value": f"{line.discount_value:.4f}",
        "account": None
        if line.account is None
        else {
            "id": str(line.account.public_id),
            "code": line.account.code,
            "name": line.account.name,
        },
        "tax_code": None
        if line.tax_code is None
        else {"id": str(line.tax_code.public_id), "code": line.tax_code.code},
        "tracking": dict(line.tracking or {}),
        "po_line": str(line.po_line.public_id) if line.po_line_id and line.po_line else None,
        "net": _money(line.net),
        "tax_amount": _money(line.tax_amount),
        "amount": _money(line.amount),
    }


def bill_row(bill: Bill) -> dict[str, Any]:
    return {
        "id": str(bill.public_id),
        "number": bill.number,
        "status": bill.status,
        "status_label": str(BillStatus(bill.status).label),
        "supplier": {"id": str(bill.contact.public_id), "name": bill.contact.display_name},
        "supplier_invoice_no": bill.supplier_invoice_no,
        "reference": bill.reference,
        "date": bill.date.isoformat(),
        "due_date": bill.due_date.isoformat() if bill.due_date else None,
        "total": _money(bill.total),
        "amount_due": _money(bill.amount_due),
        "url": bill_url(bill),
    }


def bill_detail(bill: Bill) -> dict[str, Any]:
    lines = bill.lines.select_related("account", "tax_code", "po_line").order_by("position", "pk")
    return {
        **bill_row(bill),
        "terms": str(bill.terms.public_id) if bill.terms_id and bill.terms else None,
        "currency": bill.currency,
        "tax_mode": bill.tax_mode,
        "discount_type": bill.discount_type,
        "discount_value": f"{bill.discount_value:.4f}",
        "department": bill.department,
        "notes": bill.notes,
        "holdback_type": bill.holdback_type,
        "holdback_value": f"{bill.holdback_value:.4f}",
        "holdback_amount": _money(bill.holdback_amount),
        "holdback_released": _money(bill.holdback_released),
        "holdback_outstanding": _money(bill.holdback_outstanding),
        "subtotal": _money(bill.subtotal),
        "discount_total": _money(bill.discount_total),
        "tax_total": _money(bill.tax_total),
        "amount_paid": _money(bill.amount_paid),
        "version": bill.version,
        "purchase_order": None
        if bill.purchase_order is None
        else {"id": str(bill.purchase_order.public_id), "number": bill.purchase_order.number},
        "journal": None
        if bill.journal_entry is None
        else f"/o/{bill.organisation.public_id}/accounting/journals/{bill.journal_entry.public_id}",
        "submitted_at": bill.submitted_at.isoformat() if bill.submitted_at else None,
        "approved_at": bill.approved_at.isoformat() if bill.approved_at else None,
        "approved_by": bill.approved_by.get_full_name() if bill.approved_by else "",
        "lines": [line_row(line) for line in lines],
    }


def _refused(error: Any) -> Response:
    messages = getattr(error, "messages", None) or [str(error)]
    return Response(
        {"code": getattr(error, "code", "invalid"), "detail": " ".join(str(m) for m in messages)},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _bill(public_id: Any) -> Bill:
    found: Bill | None = (
        Bill.objects.select_related("contact", "organisation", "purchase_order", "journal_entry")
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise NotFound(_("There's no bill with this id in this organisation."))
    return found


class BillLineSerializer(serializers.Serializer[Any]):
    description = serializers.CharField(required=False, allow_blank=True, default="")
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("1"))
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default=NONE)
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    account = serializers.UUIDField(required=False, allow_null=True, default=None)
    tax_code = serializers.UUIDField(required=False, allow_null=True, default=None)
    tracking = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    po_line = serializers.UUIDField(required=False, allow_null=True, default=None)


class BillSerializer(serializers.Serializer[Any]):
    supplier = serializers.UUIDField()
    date = serializers.DateField()
    due_date = serializers.DateField(required=False, allow_null=True, default=None)
    supplier_invoice_no = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=100
    )
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    terms = serializers.UUIDField(required=False, allow_null=True, default=None)
    tax_mode = serializers.ChoiceField(choices=TaxMode.choices, default=TaxMode.EXCLUSIVE)
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default=NONE)
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    department = serializers.CharField(required=False, allow_blank=True, default="", max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    holdback_type = serializers.ChoiceField(choices=HoldbackType.choices, default=HoldbackType.NONE)
    holdback_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    lines = BillLineSerializer(many=True, max_length=500)  # type: ignore[call-arg]
    document = serializers.UUIDField(required=False, allow_null=True, default=None)
    version = serializers.IntegerField(required=False, allow_null=True, default=None)


def _resolve(values: dict[str, Any]) -> dict[str, Any]:
    """Public ids → records (the supplier, terms, accounts, tax codes, PO lines)."""
    from numo9.contacts.models import Contact, PaymentTerm
    from numo9.ledger.models import Account
    from numo9.tax.models import TaxCode

    from .models import PurchaseOrderLine

    errors: dict[str, Any] = {}
    supplier = Contact.objects.filter(public_id=values["supplier"], deleted_at__isnull=True).first()
    if supplier is None:
        errors["supplier"] = [_("That supplier doesn't exist.")]
    terms = None
    if values.get("terms"):
        terms = PaymentTerm.objects.filter(public_id=values["terms"]).first()
        if terms is None:
            errors["terms"] = [_("Those payment terms don't exist.")]
    lines = values["lines"]
    accounts = {
        a.public_id: a
        for a in Account.objects.filter(public_id__in={x["account"] for x in lines if x["account"]})
    }
    codes = {
        c.public_id: c
        for c in TaxCode.objects.filter(
            public_id__in={x["tax_code"] for x in lines if x["tax_code"]}
        )
    }
    po_lines = {
        p.public_id: p
        for p in PurchaseOrderLine.objects.filter(
            public_id__in={x["po_line"] for x in lines if x["po_line"]}
        )
    }
    for number, line in enumerate(lines):
        for field, found in (("account", accounts), ("tax_code", codes), ("po_line", po_lines)):
            if line[field] and line[field] not in found:
                errors.setdefault("lines", {}).setdefault(str(number), {})[field] = [
                    _("That %(field)s doesn't exist.") % {"field": field.replace("_", " ")}
                ]
    if errors:
        raise serializers.ValidationError(errors)
    if values.get("due_date") and values["due_date"] < values["date"]:
        raise serializers.ValidationError(
            {"due_date": [_("The due date is before the bill date.")]}
        )
    return {
        "supplier": supplier,
        "terms": terms,
        "lines": [
            {
                **line,
                "account": accounts.get(line["account"]),
                "tax_code": codes.get(line["tax_code"]),
                "po_line": po_lines.get(line["po_line"]),
            }
            for line in lines
        ],
    }


HEADER = (
    "date",
    "due_date",
    "supplier_invoice_no",
    "reference",
    "tax_mode",
    "discount_type",
    "discount_value",
    "department",
    "notes",
    "holdback_type",
    "holdback_value",
)


def _save(bill: Bill, values: dict[str, Any], records: dict[str, Any]) -> Bill:
    from .bills import recalculate

    taken = number_conflict(
        records["supplier"], values["supplier_invoice_no"], exclude=bill if bill.pk else None
    )
    if taken is not None:
        raise serializers.ValidationError(
            {
                "code": "purchases.bill.duplicate_number",
                "supplier_invoice_no": [
                    _("Already used on %(bill)s (%(date)s)")
                    % {"bill": taken.number or _("a draft bill"), "date": format_date(taken.date)}
                ],
            }
        )
    bill.contact = records["supplier"]
    bill.terms = records["terms"]
    for field in HEADER:
        setattr(bill, field, values[field])
    bill.supplier_invoice_no = normalise(values["supplier_invoice_no"])
    if bill.due_date is None:
        from numo9.documents.due_dates import document_terms, due_date

        chosen = document_terms("purchase", bill.contact, bill.organisation)
        bill.due_date = due_date(bill.date, chosen.terms_type, chosen.days)
    if bill.pk:
        bill.version += 1
    bill.save()
    bill.lines.all().delete()
    for position, line in enumerate(records["lines"]):
        BillLine(
            organisation=bill.organisation,
            document=bill,
            position=position,
            description=line["description"],
            quantity=line["quantity"],
            unit_price=line["unit_price"],
            discount_type=line["discount_type"],
            discount_value=line["discount_value"],
            account=line["account"],
            tax_code=line["tax_code"],
            tracking=dict(line["tracking"] or {}),
            po_line=line["po_line"],
        ).save()
    return recalculate(bill)


def overview_tabs() -> tuple[str, ...]:
    return overview.TABS


def _status_filter(text: str | None) -> list[str]:
    wanted = [s.strip() for s in (text or "").split(",") if s.strip()]
    return [s for s in wanted if s in BillStatus.values]


class BillListView(APIView):
    @requires_permission(BILLS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="bills_list",
        parameters=[
            OpenApiParameter("tab", str, enum=list(overview_tabs())),
            OpenApiParameter("status", str),
            OpenApiParameter("supplier", OpenApiTypes.UUID),
            OpenApiParameter("q", str),
            OpenApiParameter("page", int),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        from numo9.contacts.models import organisation_today

        query = request.query_params
        today = organisation_today(current_org())
        bills = overview.live_bills().select_related("contact", "organisation")
        counts = dict(
            bills.values_list("status").annotate(n=Count("pk")).values_list("status", "n")
        )
        tabs = overview.tab_counts(bills, today)
        tab = query.get("tab") or "all"
        if tab not in overview.TABS:
            return Response(
                {
                    "code": "purchases.bill.bad_tab",
                    "detail": _("There's no %(tab)s tab on the bills list.") % {"tab": tab[:40]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        bills = bills.filter(overview.tab_filter(tab, today))
        statuses = _status_filter(query.get("status"))
        if statuses:
            bills = bills.filter(status__in=statuses)
        supplier = _uuid(query.get("supplier"))
        if supplier:
            bills = bills.filter(contact__public_id=supplier)
        text = (query.get("q") or "").strip()
        if text:
            bills = bills.filter(
                Q(number__icontains=text)
                | Q(supplier_invoice_no__icontains=text)
                | Q(reference__icontains=text)
                | Q(contact__display_name__icontains=text)
            )
        page = int(query.get("page") or 1) if str(query.get("page") or "1").isdigit() else 1
        total = bills.count()
        chunk = bills.order_by("-date", "-pk")[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        return Response(
            {
                "count": total,
                "page": page,
                "pages": max(1, -(-total // PAGE_SIZE)),
                "counts": {key: counts.get(key, 0) for key in BillStatus.values},
                "tab": tab,
                "tabs": [
                    {
                        "key": key,
                        "label": str(overview.TAB_LABELS[key]),
                        "count": tabs[key]["count"],
                        "amount": _money(tabs[key]["amount"]),
                    }
                    for key in overview.TABS
                ],
                "results": [bill_row(bill) for bill in chunk],
            }
        )

    @requires_permission(BILLS_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bills_create", request=BillSerializer, responses={201: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = BillSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        records = _resolve(values)
        try:
            with transaction.atomic():
                draft = Bill(organisation=current_org(), created_by=_person(request.user))
                bill = _save(draft, values, records)
                if values.get("document"):
                    _attach(bill, values["document"], request.user)
        except DjangoValidationError as error:
            from numo9.contacts.api import drf_errors

            raise drf_errors(error) from None
        return Response(bill_detail(bill), status=status.HTTP_201_CREATED)


def _attach(bill: Bill, document_id: Any, user: Any) -> None:
    from numo9.files.attachments import attach
    from numo9.files.models import Document

    document = Document.objects.filter(public_id=document_id, deleted_at__isnull=True).first()
    if document is None:
        raise serializers.ValidationError({"document": [_("That document doesn't exist.")]})
    attach(document, "purchases.Bill", bill.public_id, user=user)


class BillDetailView(APIView):
    @requires_permission(BILLS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bills_detail", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(bill_detail(_bill(public_id)))

    @requires_permission(BILLS_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bills_update", request=BillSerializer, responses={200: OpenApiTypes.OBJECT}
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        bill = _bill(public_id)
        if bill.status != BillStatus.DRAFT:
            return Response(
                {
                    "code": "purchases.bill.not_editable",
                    "detail": _("Only a draft bill can be edited: void it to correct it."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        incoming = BillSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        if values.get("version") is not None and values["version"] != bill.version:
            return Response(
                {
                    "code": "purchases.bill.stale",
                    "detail": _("Someone else saved this bill: reload it to see their changes."),
                    "version": bill.version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        records = _resolve(values)
        with transaction.atomic():
            locked = Bill._base_manager.select_for_update().get(pk=bill.pk)
            saved = _save(locked, values, records)
        return Response(bill_detail(saved))

    @requires_permission(BILLS_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bills_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        bill = _bill(public_id)
        if bill.status != BillStatus.DRAFT:
            return Response(
                {
                    "code": "purchases.bill.not_deletable",
                    "detail": _("Only a draft bill can be deleted: void a posted bill."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        bill.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BillPreviewView(APIView):
    @requires_permission(BILLS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bills_preview", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        from numo9.ledger.models import LedgerError

        from .bill_from_po import match_panel
        from .bill_posting import bill_spec
        from .bills import bill_preview, itc_split
        from .duplicates import suspects_for
        from .routing import route

        bill = _bill(public_id)
        journal: dict[str, Any] | None = None
        try:
            shown = bill_preview(bill)
            spec = bill_spec(bill, shown)
            journal = {
                "lines": [
                    {
                        "account": getattr(line.account, "code", ""),
                        "name": getattr(line.account, "name", ""),
                        "debit": _money(line.debit),
                        "credit": _money(line.credit),
                        "description": line.description,
                    }
                    for line in spec.lines
                ],
                "complete": shown.complete,
            }
        except LedgerError as error:
            journal = {"lines": [], "complete": False, "problem": " ".join(error.messages)}
        locale = getattr(request, "LANGUAGE_CODE", None)
        return Response(
            {
                "journal": journal,
                "itc": itc_split(bill),
                "routing": route(bill, locale=locale).as_dict(),
                "duplicates": suspects_for(bill),
                "match": match_panel(bill),
            }
        )


class _ActionView(APIView):
    def act(self, bill: Bill, request: Request) -> Bill:
        raise NotImplementedError

    def run(self, request: Request, public_id: Any) -> Response:
        from numo9.ledger.models import LedgerError

        from .bill_from_po import BillFromOrderRefused

        bill = _bill(public_id)
        try:
            done = self.act(bill, request)
        except (LedgerError, BillFromOrderRefused) as error:
            return _refused(error)
        return Response(bill_detail(_bill(done.public_id)))


class BillSubmitView(_ActionView):
    @requires_permission(BILLS_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bills_submit", request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, bill: Bill, request: Request) -> Bill:
        from .routing import submit

        return submit(bill, request.user)


class BillApproveView(_ActionView):
    @requires_permission(BILLS_APPROVE.key)
    @requires_feature(APPROVE)
    @extend_schema(operation_id="bills_approve", request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, bill: Bill, request: Request) -> Bill:
        from numo9.tax.returns import late_adjustments

        from .bill_posting import approve

        data = request.data if isinstance(request.data, dict) else {}
        # ``late_adjustment``: a bill dated in a filed tax period, reported on the next return.
        with late_adjustments(bool(data.get("late_adjustment"))):
            return approve(bill, request.user, with_variance=bool(data.get("with_variance")))


class BillVoidView(_ActionView):
    @requires_permission(BILLS_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bills_void", request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, bill: Bill, request: Request) -> Bill:
        from .bill_posting import void

        data = request.data if isinstance(request.data, dict) else {}
        day = (
            serializers.DateField(allow_null=True).to_internal_value(data["date"])
            if data.get("date")
            else None
        )
        return void(bill, request.user, date=day, reason=str(data.get("reason") or ""))


class BillReleaseHoldbackView(_ActionView):
    @requires_permission(BILLS_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bills_release_holdback", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, bill: Bill, request: Request) -> Bill:
        from .bill_posting import release_holdback

        data = request.data if isinstance(request.data, dict) else {}
        amount = (
            serializers.DecimalField(max_digits=18, decimal_places=2).to_internal_value(
                data["amount"]
            )
            if data.get("amount") not in (None, "")
            else None
        )
        day = serializers.DateField().to_internal_value(data["date"]) if data.get("date") else None
        return release_holdback(bill, request.user, amount=amount, date=day)


class BillFromOrderView(APIView):
    @requires_permission(BILLS_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bills_from_po", request=None, responses={201: OpenApiTypes.OBJECT})
    def post(self, request: Request, org: Any) -> Response:
        from .bill_from_po import BillFromOrderRefused, bill_from_purchase_order
        from .models import GoodsReceipt, PurchaseOrder

        data = request.data if isinstance(request.data, dict) else {}
        order = PurchaseOrder.objects.filter(public_id=_uuid(data.get("purchase_order"))).first()
        if order is None:
            raise NotFound(_("There's no such purchase order."))
        receipt = None
        if data.get("receipt"):
            receipt = GoodsReceipt.objects.filter(public_id=_uuid(data.get("receipt"))).first()
            if receipt is None:
                raise NotFound(_("There's no such goods receipt."))
        try:
            bill = bill_from_purchase_order(order, request.user, receipt=receipt)
        except BillFromOrderRefused as error:
            return _refused(error)
        return Response(bill_detail(_bill(bill.public_id)), status=status.HTTP_201_CREATED)


class BillDuplicatesView(APIView):
    @requires_permission(BILLS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bills_duplicates", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any) -> Response:
        from .duplicates import review_list

        return Response({"results": review_list()})


OVERVIEW_SECTIONS = ("tiles", "aging", "suppliers")


class BillOverviewView(APIView):
    """The purchases overview (E-02-T15): tiles = the list tabs' numbers (one query source)."""

    @requires_permission(BILLS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="bills_overview",
        parameters=[OpenApiParameter("section", str, enum=list(OVERVIEW_SECTIONS))],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        from numo9.contacts.models import organisation_today

        organisation = current_org()
        today = organisation_today(organisation)
        section = request.query_params.get("section") or ""
        if section and section not in OVERVIEW_SECTIONS:
            return Response(
                {
                    "code": "purchases.overview.bad_section",
                    "detail": _("Ask for the tiles, aging or suppliers section."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        bills = overview.live_bills()
        list_url = f"/o/{organisation.public_id}/purchases/bills" if organisation else ""
        body: dict[str, Any] = {"as_of": today.isoformat()}
        if section in ("", "tiles"):
            tabs = overview.tab_counts(bills, today)
            body["tiles"] = [
                {
                    "key": key,
                    "label": str(overview.TAB_LABELS[key]),
                    "count": tabs[key]["count"],
                    "amount": _money(tabs[key]["amount"]),
                    "href": f"{list_url}?tab={key}",
                }
                for key in overview.TILES
            ]
        if section in ("", "aging"):
            body["aging"] = [
                {**bucket, "amount": _money(bucket["amount"])}
                for bucket in overview.aging(bills, today)
            ]
        if section in ("", "suppliers"):
            body["top_suppliers"] = [
                {**row, "owed": _money(row["owed"]), "overdue": _money(row["overdue"])}
                for row in overview.top_suppliers(bills, today)
            ]
        return Response(body)
