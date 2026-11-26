"""Invoices API (D-03a-T11), under ``/api/v1/o/<org>/``. Feature keys
``accounting.sales_invoices.read`` / ``.write`` / ``.approve``; permissions
``sales.invoices.view`` / ``.write`` / ``.approve`` (and ``.send`` for email, D-03a-T12).

- ``GET invoices`` — the list: ``status`` (one or comma-separated), ``customer``, ``q`` (number,
  reference, customer name, total), ``page``; 50 a page, newest first, with counts per status
  (the list tabs);
- ``POST invoices`` — a draft: ``customer``, ``date``, ``due_date``, ``reference``, ``terms``,
  ``tax_mode``, ``ship_to_country`` / ``ship_to_province``, discount, ``notes``, ``lines`` and
  optional ``attachments`` (files of the documents inbox); the figures are the server's;
- ``GET`` / ``PATCH`` / ``DELETE invoices/<id>`` — an invoice; drafts are edited (409 when the
  ``version`` sent isn't the invoice's: someone else saved first) and deleted (soft);
- ``GET invoices/<id>/preview`` — the journal approval posts (Dr Accounts receivable, Cr revenue,
  Cr each tax control account), the period ribbon (the AR lock, the GST/HST period and whether
  it is filed), the credit check and the duplicate suspects (the editor's drawer and ribbon);
- ``POST invoices/<id>/approve`` — approve and post, or send to Awaiting approval when the rule
  needs it (D-03a-T05); an invoice awaiting approval is approved by an approver;
  ``late_adjustment``: dated in a filed tax period, reported on the next return (G-03-T08);
- ``POST invoices/<id>/void`` ``{date, reason}`` (D-03a-T07) · ``/copy`` ``{to: invoice | quote,
  date}`` (D-03a-T10, 201);
- ``POST invoices/<id>/email`` sends, ``GET invoices/<id>/pdf`` the PDF (``api.py``).

A refusal is a ``400`` ``{code, detail}`` (``sales.invoice.locked``, ``.filed_period``,
``.not_draft``…); a lock refused by the posting engine is its ``409`` (``lock.violation``).
"""

from __future__ import annotations

import contextlib
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
from numo9.documents.models import TaxMode
from numo9.ledger.models import LedgerError
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .models import Invoice, InvoiceLine, InvoiceStatus
from .permissions import INVOICES_APPROVE, INVOICES_VIEW, INVOICES_WRITE

READ = "accounting.sales_invoices.read"
WRITE = "accounting.sales_invoices.write"
APPROVE = "accounting.sales_invoices.approve"
PAGE_SIZE = 50
DISCOUNTS = (NONE, AMOUNT, PERCENT)


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _money(value: Any) -> str:
    return f"{Decimal(value or 0):.2f}"


def _uuid(value: Any) -> str | None:
    import uuid

    try:
        return str(uuid.UUID(str(value))) if value else None
    except ValueError:
        return None


def invoice_url(invoice: Invoice) -> str:
    return f"/o/{invoice.organisation.public_id}/sales/invoices/{invoice.public_id}"


def _ref(obj: Any, **extra: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    return {"id": str(obj.public_id), **extra}


def line_row(line: InvoiceLine) -> dict[str, Any]:
    return {
        "id": str(line.public_id),
        "position": line.position,
        "item": _ref(line.item, name=getattr(line.item, "name", "")),
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
        "tax_code": _ref(line.tax_code, code=getattr(line.tax_code, "code", "")),
        "tax_overridden": line.tax_overridden,
        "tracking": dict(line.tracking or {}),
        "net": _money(line.net),
        "tax_amount": _money(line.tax_amount),
        "amount": _money(line.amount),
    }


def invoice_row(invoice: Invoice) -> dict[str, Any]:
    return {
        "id": str(invoice.public_id),
        "number": invoice.number,
        "status": invoice.status,
        "status_label": str(InvoiceStatus(invoice.status).label),
        "customer": {"id": str(invoice.contact.public_id), "name": invoice.contact.display_name},
        "reference": invoice.reference,
        "date": invoice.date.isoformat(),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "total": _money(invoice.total),
        "amount_paid": _money(invoice.amount_paid),
        "amount_due": _money(invoice.total - invoice.amount_paid),
        "url": invoice_url(invoice),
    }


def invoice_detail(invoice: Invoice) -> dict[str, Any]:
    lines = invoice.lines.select_related("account", "tax_code", "item").order_by("position", "pk")
    organisation = invoice.organisation
    return {
        **invoice_row(invoice),
        "terms": str(invoice.terms.public_id) if invoice.terms_id and invoice.terms else None,
        "currency": invoice.currency,
        "tax_mode": invoice.tax_mode,
        "ship_to_country": invoice.ship_to_country,
        "ship_to_province": invoice.ship_to_province,
        "discount_type": invoice.discount_type,
        "discount_value": f"{invoice.discount_value:.4f}",
        "notes": invoice.notes,
        "subtotal": _money(invoice.subtotal),
        "discount_total": _money(invoice.discount_total),
        "tax_total": _money(invoice.tax_total),
        "version": invoice.version,
        "journal": None
        if invoice.journal_entry is None
        else f"/o/{organisation.public_id}/accounting/journals/{invoice.journal_entry.public_id}",
        "submitted_at": invoice.submitted_at.isoformat() if invoice.submitted_at else None,
        "approved_at": invoice.approved_at.isoformat() if invoice.approved_at else None,
        "approved_by": invoice.approved_by.get_full_name() if invoice.approved_by else "",
        "sent_at": invoice.sent_at.isoformat() if invoice.sent_at else None,
        "voided_at": invoice.voided_at.isoformat() if invoice.voided_at else None,
        "pdf": f"/api/v1/o/{organisation.public_id}/invoices/{invoice.public_id}/pdf",
        "attachments": _attachments(invoice),
        "lines": [line_row(line) for line in lines],
    }


def _attachments(invoice: Invoice) -> list[dict[str, Any]]:
    from numo9.files.attachments import attachments_of

    return [
        {"id": str(row.document.public_id), "name": row.document.name}
        for row in attachments_of("sales.Invoice", invoice.public_id)
    ]


def _refused(error: Any) -> Response:
    messages = getattr(error, "messages", None) or [str(error)]
    return Response(
        {
            "code": getattr(error, "code", None) or "invalid",
            "detail": " ".join(str(m) for m in messages),
            **({"params": error.params} if getattr(error, "params", None) else {}),
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _invoice(public_id: Any) -> Invoice:
    found: Invoice | None = (
        Invoice.objects.select_related("contact", "organisation", "journal_entry", "terms")
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise NotFound(_("There's no invoice with this id in this organisation."))
    return found


class InvoiceLineSerializer(serializers.Serializer[Any]):
    item = serializers.UUIDField(required=False, allow_null=True, default=None)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("1"))
    unit_price = serializers.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default=NONE)
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    account = serializers.UUIDField(required=False, allow_null=True, default=None)
    tax_code = serializers.UUIDField(required=False, allow_null=True, default=None)
    tax_overridden = serializers.BooleanField(required=False, default=False)
    tracking = serializers.DictField(child=serializers.CharField(), required=False, default=dict)


class InvoiceSerializer(serializers.Serializer[Any]):
    customer = serializers.UUIDField()
    date = serializers.DateField()
    due_date = serializers.DateField(required=False, allow_null=True, default=None)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    terms = serializers.UUIDField(required=False, allow_null=True, default=None)
    tax_mode = serializers.ChoiceField(choices=TaxMode.choices, default=TaxMode.EXCLUSIVE)
    ship_to_country = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=2
    )
    ship_to_province = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=2
    )
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default=NONE)
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = InvoiceLineSerializer(many=True, max_length=500)  # type: ignore[call-arg]
    attachments = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list, max_length=20
    )
    version = serializers.IntegerField(required=False, allow_null=True, default=None)


def _resolve(values: dict[str, Any]) -> dict[str, Any]:
    """Public ids → records (the customer, terms, items, accounts, tax codes)."""
    from numo9.contacts.models import Contact, PaymentTerm
    from numo9.items.models import Item
    from numo9.ledger.models import Account
    from numo9.tax.models import TaxCode

    errors: dict[str, Any] = {}
    customer = Contact.objects.filter(public_id=values["customer"], deleted_at__isnull=True).first()
    if customer is None:
        errors["customer"] = [_("That customer doesn't exist.")]
    terms = None
    if values.get("terms"):
        terms = PaymentTerm.objects.filter(public_id=values["terms"]).first()
        if terms is None:
            errors["terms"] = [_("Those payment terms don't exist.")]
    lines = values["lines"]

    def found(model: Any, field: str) -> dict[Any, Any]:
        wanted = {x[field] for x in lines if x[field]}
        return {r.public_id: r for r in model.objects.filter(public_id__in=wanted)}

    records = {"item": found(Item, "item"), "account": found(Account, "account")}
    records["tax_code"] = found(TaxCode, "tax_code")
    for number, line in enumerate(lines):
        for field, rows in records.items():
            if line[field] and line[field] not in rows:
                errors.setdefault("lines", {}).setdefault(str(number), {})[field] = [
                    _("That %(field)s doesn't exist.") % {"field": field.replace("_", " ")}
                ]
    if errors:
        raise serializers.ValidationError(errors)
    if values.get("due_date") and values["due_date"] < values["date"]:
        raise serializers.ValidationError(
            {"due_date": [_("The due date is before the invoice date.")]}
        )
    return {
        "customer": customer,
        "terms": terms,
        "lines": [
            {**line, **{field: rows.get(line[field]) for field, rows in records.items()}}
            for line in lines
        ],
    }


HEADER = (
    "date",
    "due_date",
    "reference",
    "tax_mode",
    "ship_to_country",
    "ship_to_province",
    "discount_type",
    "discount_value",
    "notes",
)


def _save(invoice: Invoice, values: dict[str, Any], records: dict[str, Any]) -> Invoice:
    from .posting import recalculate

    invoice.contact = records["customer"]
    invoice.terms = records["terms"]
    for field in HEADER:
        setattr(invoice, field, values[field])
    if invoice.due_date is None:
        from numo9.documents.due_dates import document_terms, due_date

        chosen = document_terms("sales", invoice.contact, invoice.organisation)
        invoice.due_date = due_date(invoice.date, chosen.terms_type, chosen.days)
    if invoice.pk:
        invoice.version += 1
    invoice.save()
    invoice.lines.all().delete()
    for position, line in enumerate(records["lines"]):
        InvoiceLine(
            organisation=invoice.organisation,
            document=invoice,
            position=position,
            item=line["item"],
            description=line["description"],
            quantity=line["quantity"],
            unit_price=line["unit_price"],
            discount_type=line["discount_type"],
            discount_value=line["discount_value"],
            account=line["account"],
            tax_code=line["tax_code"],
            tax_overridden=line["tax_overridden"],
            tracking=dict(line["tracking"] or {}),
        ).save()
    return recalculate(invoice)


def _attach(invoice: Invoice, documents: list[Any], user: Any) -> None:
    from numo9.files.attachments import attach
    from numo9.files.models import Document

    for document_id in documents:
        document = Document.objects.filter(public_id=document_id, deleted_at__isnull=True).first()
        if document is None:
            raise serializers.ValidationError({"attachments": [_("That document doesn't exist.")]})
        attach(document, "sales.Invoice", invoice.public_id, user=user)


def _status_filter(text: str | None) -> list[str]:
    wanted = [s.strip() for s in (text or "").split(",") if s.strip()]
    return [s for s in wanted if s in InvoiceStatus.values]


class InvoiceView(APIView):
    queryset = Invoice._base_manager.none()


class InvoiceListView(InvoiceView):
    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="invoices_list",
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("customer", OpenApiTypes.UUID),
            OpenApiParameter("q", str),
            OpenApiParameter("page", int),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        query = request.query_params
        invoices = Invoice.objects.filter(deleted_at__isnull=True).select_related(
            "contact", "organisation"
        )
        counts = dict(
            invoices.values_list("status").annotate(n=Count("pk")).values_list("status", "n")
        )
        statuses = _status_filter(query.get("status"))
        if statuses:
            invoices = invoices.filter(status__in=statuses)
        customer = _uuid(query.get("customer"))
        if customer:
            invoices = invoices.filter(contact__public_id=customer)
        text = (query.get("q") or "").strip()
        if text:
            match = (
                Q(number__icontains=text)
                | Q(reference__icontains=text)
                | Q(contact__display_name__icontains=text)
            )
            with contextlib.suppress(ArithmeticError):
                match |= Q(total=Decimal(text.replace(",", "").replace("$", "")))
            invoices = invoices.filter(match)
        raw = str(query.get("page") or "1")
        page = int(raw) if raw.isdigit() and int(raw) > 0 else 1
        total = invoices.count()
        chunk = invoices.order_by("-date", "-pk")[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        return Response(
            {
                "count": total,
                "page": page,
                "pages": max(1, -(-total // PAGE_SIZE)),
                "counts": {key: counts.get(key, 0) for key in InvoiceStatus.values},
                "results": [invoice_row(invoice) for invoice in chunk],
            }
        )

    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="invoices_create",
        request=InvoiceSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = InvoiceSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        records = _resolve(values)
        try:
            with transaction.atomic():
                draft = Invoice(organisation=current_org(), created_by=_person(request.user))
                invoice = _save(draft, values, records)
                _attach(invoice, values["attachments"], request.user)
        except DjangoValidationError as error:
            from numo9.contacts.api import drf_errors

            raise drf_errors(error) from None
        return Response(invoice_detail(_invoice(invoice.public_id)), status=201)


class InvoiceDetailView(InvoiceView):
    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="invoices_detail", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(invoice_detail(_invoice(public_id)))

    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="invoices_update",
        request=InvoiceSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        invoice = _invoice(public_id)
        if invoice.status != InvoiceStatus.DRAFT:
            return Response(
                {
                    "code": "sales.invoice.not_editable",
                    "detail": _(
                        "Only a draft invoice can be edited: revise or void a posted invoice."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        incoming = InvoiceSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        if values.get("version") is not None and values["version"] != invoice.version:
            return Response(
                {
                    "code": "sales.invoice.stale",
                    "detail": _("Someone else saved this invoice: reload it to see their changes."),
                    "version": invoice.version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        records = _resolve(values)
        with transaction.atomic():
            locked = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
            saved = _save(locked, values, records)
            _attach(saved, values["attachments"], request.user)
        return Response(invoice_detail(_invoice(saved.public_id)))

    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="invoices_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        invoice = _invoice(public_id)
        if invoice.status != InvoiceStatus.DRAFT:
            return Response(
                {
                    "code": "sales.invoice.not_deletable",
                    "detail": _("Only a draft invoice can be deleted: void a posted invoice."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        invoice.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def period_ribbon(invoice: Invoice, user: Any) -> dict[str, Any]:
    """What the editor's period ribbon shows for the invoice's date: the AR lock date (and
    whether it stops this person), the GST/HST filing period and whether it is filed."""
    from numo9.orgsettings.locks import check_lock
    from numo9.orgsettings.models import LockDate, LockModule
    from numo9.tax.models import FilingPeriod

    lock = (
        LockDate.objects.filter(module=LockModule.AR, deleted_at__isnull=True, date__isnull=False)
        .order_by("-date")
        .first()
    )
    stopped = check_lock(invoice.organisation, LockModule.AR, invoice.date, user)
    period = (
        FilingPeriod.objects.filter(
            registration__type="rt",
            registration__deleted_at__isnull=True,
            start__lte=invoice.date,
            end__gte=invoice.date,
        )
        .order_by("start")
        .first()
    )
    return {
        "date": invoice.date.isoformat(),
        "ar_lock": lock.date.isoformat() if lock and lock.date else None,
        "locked": stopped is not None,
        "lock": stopped.as_dict() if stopped else None,
        "tax_period": None
        if period is None
        else {
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
            "status": period.status,
            "filed": period.status in ("filed", "paid"),
            "due_date": period.due_date.isoformat(),
        },
    }


class InvoicePreviewView(InvoiceView):
    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="invoices_preview", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        from .approvals import approval_needed
        from .credit import invoice_credit
        from .duplicates import possible_duplicates
        from .posting import invoice_preview

        invoice = _invoice(public_id)
        journal: dict[str, Any]
        if invoice.journal_entry is not None:  # posted: what was posted
            rows = invoice.journal_entry.lines.select_related("account").order_by("line_no")
            journal = {
                "posted": True,
                "complete": True,
                "lines": [
                    {
                        "account": row.account.code,
                        "name": row.account.name,
                        "debit": _money(row.debit),
                        "credit": _money(row.credit),
                        "description": row.description,
                    }
                    for row in rows
                ],
            }
        else:
            try:
                shown = invoice_preview(invoice)
                journal = {
                    "posted": False,
                    "complete": shown.complete,
                    "lines": [
                        {
                            "account": getattr(line.account, "code", ""),
                            "name": getattr(line.account, "name", ""),
                            "debit": _money(line.debit),
                            "credit": _money(line.credit),
                            "description": line.description,
                        }
                        for line in shown.lines
                    ],
                }
            except LedgerError as error:
                journal = {
                    "posted": False,
                    "complete": False,
                    "lines": [],
                    "problem": " ".join(str(m) for m in error.messages),
                }
        credit = invoice_credit(invoice)
        return Response(
            {
                "journal": journal,
                "period": period_ribbon(invoice, request.user),
                "approval": approval_needed(invoice, request.user)
                if invoice.status == InvoiceStatus.DRAFT
                else None,
                "credit": {"outcome": credit.outcome, "message": credit.message},
                "duplicates": possible_duplicates(invoice)
                if invoice.status == InvoiceStatus.DRAFT
                else [],
            }
        )


class _ActionView(InvoiceView):
    def act(self, invoice: Invoice, request: Request) -> Invoice:
        raise NotImplementedError

    def run(self, request: Request, public_id: Any, *, created: bool = False) -> Response:
        invoice = _invoice(public_id)
        try:
            done = self.act(invoice, request)
        except LedgerError as error:
            return _refused(error)
        body = invoice_detail(_invoice(done.public_id))
        warning = getattr(done, "credit_warning", "")
        if warning:
            body["credit_warning"] = warning
        return Response(body, status=201 if created else 200)


def _data(request: Request) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


class InvoiceApproveView(_ActionView):
    @requires_permission(INVOICES_APPROVE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="invoices_approve", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, invoice: Invoice, request: Request) -> Invoice:
        from numo9.tax.returns import late_adjustments

        from .approvals import approve_waiting, submit_or_approve

        with late_adjustments(bool(_data(request).get("late_adjustment"))):
            if invoice.status == InvoiceStatus.AWAITING_APPROVAL:
                return approve_waiting(invoice, request.user)
            return submit_or_approve(invoice, request.user)


class InvoiceVoidView(_ActionView):
    @requires_permission(INVOICES_APPROVE.key)
    @requires_feature(APPROVE)
    @extend_schema(operation_id="invoices_void", request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, invoice: Invoice, request: Request) -> Invoice:
        from .posting import void

        data = _data(request)
        day = serializers.DateField().to_internal_value(data["date"]) if data.get("date") else None
        return void(invoice, request.user, date=day, reason=str(data.get("reason") or ""))


class InvoiceCopyView(_ActionView):
    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="invoices_copy", request=None, responses={201: OpenApiTypes.OBJECT})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        to = str(_data(request).get("to") or "invoice")
        if to not in ("invoice", "quote"):
            raise serializers.ValidationError({"to": [_("Copy to an invoice or a quote.")]})
        if to == "quote":
            return self._to_quote(request, public_id)
        return self.run(request, public_id, created=True)

    def _to_quote(self, request: Request, public_id: Any) -> Response:
        from .copying import copy_document

        data = _data(request)
        day = serializers.DateField().to_internal_value(data["date"]) if data.get("date") else None
        quote = copy_document(_invoice(public_id), "quote", request.user, date=day)
        return Response(
            {
                "id": str(quote.public_id),
                "number": quote.number,
                "url": f"/o/{quote.organisation.public_id}/sales/quotes/{quote.public_id}",
            },
            status=status.HTTP_201_CREATED,
        )

    def act(self, invoice: Invoice, request: Request) -> Invoice:
        from .copying import copy_document

        data = _data(request)
        day = serializers.DateField().to_internal_value(data["date"]) if data.get("date") else None
        copied: Invoice = copy_document(invoice, "invoice", request.user, date=day)
        return copied
