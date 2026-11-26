"""Recurring invoices API (D-04-T07), under ``/api/v1/o/<org>/``. The invoices' feature keys
(``accounting.sales_invoices.read`` / ``.write`` — recurring invoices are never product-gated
within Accounting) and permissions (``sales.invoices.view`` / ``.write``; a template that
approves, or approves and sends, its invoices also needs ``sales.invoices.approve`` /
``.send``: it approves on its author's behalf).

- ``GET recurring-invoices`` — the templates: ``status`` (``active`` / ``paused`` / ``ended``,
  one or comma-separated), ``customer``, ``q`` (name, reference, customer); each with its next
  and last run, status and the number of invoices generated and dates skipped; ``counts`` per
  status (the list tabs);
- ``POST recurring-invoices`` — a template: the invoice's header and ``lines`` (the shared grid),
  ``name``, the schedule (``rrule``, ``start_date``, ``end_date``), ``mode`` (``draft`` /
  ``approve`` / ``approve_send``), ``prorate`` with ``service_start`` / ``service_end``,
  ``paused``. The first run is the first occurrence from today on (a schedule that started in
  the past doesn't bill the months before it);
- ``GET`` / ``PATCH`` / ``DELETE recurring-invoices/<id>`` — read, edit (409 when the ``version``
  sent isn't the template's; every edit bumps it and applies to future occurrences only; a
  changed schedule recomputes the next run from today), delete (soft; its invoices stay);
- ``POST recurring-invoices/<id>/pause`` · ``/resume`` — a paused template's dates are recorded
  as skipped; resuming starts again from today;
- ``GET recurring-invoices/<id>/preview?date=`` — the next invoice (or that occurrence's) exactly
  as the generator will make it — built with the generator's own code in a transaction that is
  rolled back — with the placeholders resolved, the period and its proration, the skip rule that
  would apply, and the next dates;
- ``GET recurring-invoices/<id>/history?page=`` — the runs, newest first: date, created or
  skipped (with the reason), the invoice (number, status, total) and the template version;
- ``POST recurring-invoices/schedule`` ``{rrule, start_date, end_date, count}`` — the next dates
  of an unsaved schedule (the editor's schedule panel; the generator's engine).

Errors: 400 with the field's messages (and ``code``), ``sales.recurring.*`` refusals.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.documents.models import RecurringRunStatus, TaxMode
from numo9.ledger import recurring as engine
from numo9.orgsettings.locks import local_date
from numo9.rbac.drf import requires_permission
from numo9.rbac.resolver import has_perm
from numo9.tenancy.context import current_org

from . import recurring_invoices as recurring
from .invoices_api import (
    DISCOUNTS,
    PAGE_SIZE,
    READ,
    WRITE,
    InvoiceLineSerializer,
    _money,
    _person,
    _resolve,
    _uuid,
    invoice_url,
    line_row,
)
from .models import (
    RecurringInvoiceLine,
    RecurringInvoiceMode,
    RecurringInvoiceRun,
    RecurringInvoiceTemplate,
)
from .permissions import INVOICES_APPROVE, INVOICES_SEND, INVOICES_VIEW, INVOICES_WRITE

STATUSES = ("active", "paused", "ended")
PREVIEW_DATES = 6
SCHEDULE_MAX = 24


def _today() -> dt.date:
    organisation = current_org()
    assert organisation is not None  # noqa: S101 — RequiresPermission answered 404 otherwise
    return local_date(organisation, timezone.now())


def template_url(template: RecurringInvoiceTemplate) -> str:
    return f"/o/{template.organisation.public_id}/sales/recurring-invoices/{template.public_id}"


def status_of(template: RecurringInvoiceTemplate) -> str:
    if template.next_run is None:
        return "ended"
    return "paused" if template.paused else "active"


def _status_filter(text: str | None) -> list[str]:
    wanted = [s.strip() for s in (text or "").split(",") if s.strip()]
    return [s for s in wanted if s in STATUSES]


def _by_status(items: Any, wanted: list[str]) -> Any:
    match = Q()
    for name in wanted:
        if name == "ended":
            match |= Q(next_run__isnull=True)
        elif name == "paused":
            match |= Q(next_run__isnull=False, paused=True)
        else:
            match |= Q(next_run__isnull=False, paused=False)
    return items.filter(match)


def _counts(template: RecurringInvoiceTemplate) -> dict[str, int]:
    rows = dict(
        RecurringInvoiceRun.objects.filter(template=template)
        .values_list("status")
        .annotate(n=Count("pk"))
        .values_list("status", "n")
    )
    return {key: rows.get(key, 0) for key in RecurringRunStatus.values}


def template_row(template: RecurringInvoiceTemplate) -> dict[str, Any]:
    generated = getattr(template, "generated", None)
    skipped = getattr(template, "skipped", None)
    if generated is None or skipped is None:
        counts = _counts(template)
        generated, skipped = counts["created"], counts["skipped"]
    return {
        "id": str(template.public_id),
        "name": template.name,
        "status": status_of(template),
        "customer": {"id": str(template.contact.public_id), "name": template.contact.display_name},
        "reference": template.reference,
        "mode": template.mode,
        "rrule": template.rrule,
        "start_date": template.start_date.isoformat(),
        "end_date": template.end_date.isoformat() if template.end_date else None,
        "next_run": template.next_run.isoformat() if template.next_run else None,
        "last_run": template.last_run.isoformat() if template.last_run else None,
        "paused": template.paused,
        "generated": generated,
        "skipped": skipped,
        "url": template_url(template),
    }


def template_detail(template: RecurringInvoiceTemplate) -> dict[str, Any]:
    from .placeholders import unknown

    lines = template.lines.select_related("account", "tax_code", "item").order_by("position", "pk")
    texts = [template.reference, template.notes, *(line.description for line in lines)]
    return {
        **template_row(template),
        "terms": str(template.terms.public_id) if template.terms_id and template.terms else None,
        "currency": template.currency,
        "tax_mode": template.tax_mode,
        "ship_to_country": template.ship_to_country,
        "ship_to_province": template.ship_to_province,
        "discount_type": template.discount_type,
        "discount_value": f"{template.discount_value:.4f}",
        "notes": template.notes,
        "prorate": template.prorate,
        "service_start": template.service_start.isoformat() if template.service_start else None,
        "service_end": template.service_end.isoformat() if template.service_end else None,
        "version": template.version,
        "created_by": template.created_by.name if template.created_by is not None else "",
        "unknown_placeholders": sorted({name for text in texts for name in unknown(text)}),
        "lines": [{k: v for k, v in line_row(line).items() if k not in _FIGURES} for line in lines],
    }


#: A template line has no figures of its own: the preview calculates them for a date.
_FIGURES = ("net", "tax_amount", "amount")


def _template(public_id: Any) -> RecurringInvoiceTemplate:
    found: RecurringInvoiceTemplate | None = (
        RecurringInvoiceTemplate.objects.select_related(
            "contact", "organisation", "terms", "created_by"
        )
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise NotFound(_("There's no recurring invoice with this id in this organisation."))
    return found


def _invalid(error: DjangoValidationError) -> Response:
    errors: dict[str, Any] = {}
    items = error.error_dict.items() if hasattr(error, "error_dict") else [("detail", error)]
    for name, found in items:
        found = found if isinstance(found, list) else found.error_list
        errors[name] = [str(m) for item in found for m in item.messages]
        code = next((item.code for item in found if item.code), None)
        if code:
            errors.setdefault("code", code)
    return Response(errors, status=status.HTTP_400_BAD_REQUEST)


class RecurringInvoiceSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200)
    customer = serializers.UUIDField()
    terms = serializers.UUIDField(required=False, allow_null=True, default=None)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    tax_mode = serializers.ChoiceField(choices=TaxMode.choices, default=TaxMode.EXCLUSIVE)
    ship_to_country = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=2
    )
    ship_to_province = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=2
    )
    discount_type = serializers.ChoiceField(choices=DISCOUNTS, default="none")
    discount_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    rrule = serializers.CharField(max_length=500)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True, default=None)
    mode = serializers.ChoiceField(
        choices=RecurringInvoiceMode.choices, default=RecurringInvoiceMode.DRAFT
    )
    prorate = serializers.BooleanField(required=False, default=False)
    service_start = serializers.DateField(required=False, allow_null=True, default=None)
    service_end = serializers.DateField(required=False, allow_null=True, default=None)
    paused = serializers.BooleanField(required=False, default=False)
    lines = InvoiceLineSerializer(many=True, max_length=500)  # type: ignore[call-arg]
    version = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start, end = attrs.get("service_start"), attrs.get("service_end")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"service_end": [_("The service ends before it starts.")]}
            )
        return attrs


class ScheduleSerializer(serializers.Serializer[Any]):
    rrule = serializers.CharField(max_length=500)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True, default=None)
    count = serializers.IntegerField(
        required=False, default=PREVIEW_DATES, min_value=1, max_value=SCHEDULE_MAX
    )


HEADER = (
    "name",
    "reference",
    "tax_mode",
    "ship_to_country",
    "ship_to_province",
    "discount_type",
    "discount_value",
    "notes",
    "rrule",
    "start_date",
    "end_date",
    "mode",
    "prorate",
    "service_start",
    "service_end",
)
SCHEDULE = ("rrule", "start_date", "end_date", "service_end")


def _mode_refused(request: Request, mode: str) -> Response | None:
    """A template that approves (and sends) its invoices needs the people's own rights."""
    organisation = current_org()
    needed = []
    if mode in (RecurringInvoiceMode.APPROVE, RecurringInvoiceMode.APPROVE_SEND):
        needed.append(INVOICES_APPROVE.key)
    if mode == RecurringInvoiceMode.APPROVE_SEND:
        needed.append(INVOICES_SEND.key)
    if all(has_perm(request.user, organisation, key) for key in needed):  # type: ignore[arg-type]
        return None
    return Response(
        {
            "code": "sales.recurring.mode_not_allowed",
            "detail": _(
                "You can't approve or send invoices, so a recurring invoice you set up can only "
                "save drafts."
            ),
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def next_run_from(template: RecurringInvoiceTemplate, today: dt.date) -> dt.date | None:
    """The first occurrence from ``today`` on, after the latest date that already ran."""
    after = today - dt.timedelta(days=1)
    done = (
        RecurringInvoiceRun.objects.filter(template=template)
        .order_by("-occurrence_date")
        .values_list("occurrence_date", flat=True)
        .first()
    )
    if done is not None:
        after = max(after, done)
    upcoming = recurring.GENERATOR.schedule(template, after=after, limit=1)
    return upcoming[0] if upcoming else None


def _save(
    template: RecurringInvoiceTemplate, values: dict[str, Any], records: dict[str, Any]
) -> RecurringInvoiceTemplate:
    before = {name: getattr(template, name) for name in SCHEDULE}
    adding = template.pk is None
    template.contact = records["customer"]
    template.terms = records["terms"]
    for field in HEADER:
        setattr(template, field, values[field])
    template.name = template.name.strip()
    template.paused = values["paused"]
    template.full_clean(exclude=["organisation", "created_by", "next_run", "contact", "terms"])
    if adding:
        template.next_run = None
        template.save()  # next_run below, from today on
        template.next_run = next_run_from(template, _today())
        template.save(update_fields=["next_run", "updated_at"])
    else:
        template.version += 1
        if any(before[name] != getattr(template, name) for name in SCHEDULE):
            template.next_run = next_run_from(template, _today())
        template.save()
    template.lines.all().delete()
    for position, line in enumerate(records["lines"]):
        RecurringInvoiceLine(
            organisation=template.organisation,
            document=template,
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
    return template


class RecurringView(APIView):
    queryset = RecurringInvoiceTemplate._base_manager.none()


class RecurringInvoiceListView(RecurringView):
    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="recurring_invoices_list",
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
        items = RecurringInvoiceTemplate.objects.filter(deleted_at__isnull=True).select_related(
            "contact", "organisation"
        )
        counts = {name: _by_status(items, [name]).count() for name in STATUSES}
        wanted = _status_filter(query.get("status"))
        if wanted:
            items = _by_status(items, wanted)
        customer = _uuid(query.get("customer"))
        if customer:
            items = items.filter(contact__public_id=customer)
        text = (query.get("q") or "").strip()
        if text:
            items = items.filter(
                Q(name__icontains=text)
                | Q(reference__icontains=text)
                | Q(contact__display_name__icontains=text)
            )
        items = items.annotate(
            generated=Count("runs", filter=Q(runs__status=RecurringRunStatus.CREATED)),
            skipped=Count("runs", filter=Q(runs__status=RecurringRunStatus.SKIPPED)),
        )
        raw = str(query.get("page") or "1")
        page = int(raw) if raw.isdigit() and int(raw) > 0 else 1
        total = items.count()
        chunk = items.order_by("name", "pk")[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        return Response(
            {
                "count": total,
                "page": page,
                "pages": max(1, -(-total // PAGE_SIZE)),
                "counts": counts,
                "results": [template_row(t) for t in chunk],
            }
        )

    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="recurring_invoices_create",
        request=RecurringInvoiceSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = RecurringInvoiceSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        refused = _mode_refused(request, values["mode"])
        if refused is not None:
            return refused
        records = _resolve(values)
        try:
            with transaction.atomic():
                template = RecurringInvoiceTemplate(
                    organisation=current_org(), created_by=_person(request.user)
                )
                _save(template, values, records)
        except DjangoValidationError as error:
            return _invalid(error)
        return Response(template_detail(_template(template.public_id)), status=201)


class RecurringInvoiceDetailView(RecurringView):
    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="recurring_invoices_detail", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(template_detail(_template(public_id)))

    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="recurring_invoices_update",
        request=RecurringInvoiceSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        template = _template(public_id)
        incoming = RecurringInvoiceSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        if values.get("version") is not None and values["version"] != template.version:
            return Response(
                {
                    "code": "sales.recurring.stale",
                    "detail": _(
                        "Someone else saved this recurring invoice: reload it to see their changes."
                    ),
                    "version": template.version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        refused = _mode_refused(request, values["mode"])
        if refused is not None:
            return refused
        records = _resolve(values)
        try:
            with transaction.atomic():
                locked = RecurringInvoiceTemplate.objects.select_for_update().get(pk=template.pk)
                _save(locked, values, records)
        except DjangoValidationError as error:
            return _invalid(error)
        return Response(template_detail(_template(public_id)))

    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="recurring_invoices_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        _template(public_id).soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class _PauseView(RecurringView):
    pause = True

    def act(self, public_id: Any) -> Response:
        with transaction.atomic():
            template = RecurringInvoiceTemplate.objects.select_for_update().get(
                pk=_template(public_id).pk
            )
            template.paused = self.pause
            if not self.pause and template.next_run is not None:
                template.next_run = next_run_from(template, _today())
            template.save()
        return Response(template_detail(_template(public_id)))


class RecurringInvoicePauseView(_PauseView):
    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="recurring_invoices_pause", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.act(public_id)


class RecurringInvoiceResumeView(_PauseView):
    pause = False

    @requires_permission(INVOICES_WRITE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="recurring_invoices_resume", request=None, responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.act(public_id)


def preview(template: RecurringInvoiceTemplate, day: dt.date) -> dict[str, Any]:
    """The invoice of the occurrence on ``day`` as the generator makes it (its own
    ``build_invoice``), rolled back: nothing is kept, no number is used."""
    from .proration import for_template

    start, end = recurring.period_of(template, day)
    share = for_template(template, start, end)
    skip = recurring.GENERATOR.skip_reason(template, day)
    with transaction.atomic():
        invoice = recurring.build_invoice(template, day)
        lines = invoice.lines.select_related("account", "tax_code", "item").order_by("position")
        body = {
            "date": invoice.date.isoformat(),
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "customer": {
                "id": str(invoice.contact.public_id),
                "name": invoice.contact.display_name,
            },
            "reference": invoice.reference,
            "notes": invoice.notes,
            "tax_mode": invoice.tax_mode,
            "discount_type": invoice.discount_type,
            "discount_value": f"{invoice.discount_value:.4f}",
            "subtotal": _money(invoice.subtotal),
            "discount_total": _money(invoice.discount_total),
            "tax_total": _money(invoice.tax_total),
            "total": _money(invoice.total),
            "lines": [{k: v for k, v in line_row(line).items() if k != "id"} for line in lines],
        }
        transaction.set_rollback(True)
    return {
        **body,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "proration": {"covered": share.covered, "days": share.days, "full": share.full},
        "skip": None if skip is None else {"code": skip.code, "message": skip.message},
    }


class RecurringInvoicePreviewView(RecurringView):
    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="recurring_invoices_preview",
        parameters=[OpenApiParameter("date", OpenApiTypes.DATE)],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        template = _template(public_id)
        raw = request.query_params.get("date")
        if raw:
            day = serializers.DateField().to_internal_value(raw)
            found = recurring.GENERATOR.schedule(
                template, after=day - dt.timedelta(days=1), limit=1
            )
            if found != [day]:
                return Response(
                    {
                        "code": "sales.recurring.not_an_occurrence",
                        "detail": _("%(date)s isn't one of the schedule's dates.")
                        % {"date": day.isoformat()},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            day = template.next_run  # type: ignore[assignment]
        after = (template.next_run or _today()) - dt.timedelta(days=1)
        dates = [
            d.isoformat()
            for d in recurring.GENERATOR.schedule(template, after=after, limit=PREVIEW_DATES)
        ]
        if day is None:
            return Response({"invoice": None, "dates": dates, "status": status_of(template)})
        return Response(
            {"invoice": preview(template, day), "dates": dates, "status": status_of(template)}
        )


class RecurringInvoiceHistoryView(RecurringView):
    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="recurring_invoices_history",
        parameters=[OpenApiParameter("page", int)],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        template = _template(public_id)
        runs = RecurringInvoiceRun.objects.filter(template=template).select_related(
            "document", "document__organisation"
        )
        raw = str(request.query_params.get("page") or "1")
        page = int(raw) if raw.isdigit() and int(raw) > 0 else 1
        total = runs.count()
        chunk = runs.order_by("-occurrence_date", "-pk")[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        return Response(
            {
                "count": total,
                "page": page,
                "pages": max(1, -(-total // PAGE_SIZE)),
                "counts": _counts(template),
                "results": [
                    {
                        "date": run.occurrence_date.isoformat(),
                        "status": run.status,
                        "code": run.code,
                        "message": run.message,
                        "version": run.template_version,
                        "invoice": None
                        if run.document is None
                        else {
                            "id": str(run.document.public_id),
                            "number": run.document.number,
                            "status": run.document.status,
                            "total": _money(run.document.total),
                            "url": invoice_url(run.document),
                        },
                    }
                    for run in chunk
                ],
            }
        )


class RecurringScheduleView(RecurringView):
    @requires_permission(INVOICES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="recurring_invoices_schedule",
        request=ScheduleSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = ScheduleSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        data = incoming.validated_data
        start, end = data["start_date"], data.get("end_date")
        if end is not None and end < start:
            return Response(
                {
                    "end_date": [_("The end date is before the start date.")],
                    "code": "sales.recurring.end_before_start",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            dates = engine.occurrences(
                data["rrule"],
                start,
                end,
                after=max(_today(), start) - dt.timedelta(days=1),
                limit=data["count"],
            )
        except DjangoValidationError as error:
            return _invalid(error)
        return Response({"dates": [d.isoformat() for d in dates]})
