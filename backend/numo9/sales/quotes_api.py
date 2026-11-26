"""Quotes API (D-02-T11), under ``/api/v1/o/<org>/``. Feature keys
``accounting.sales_quotes.read`` / ``.write`` (the catalogue's quotes area); permissions
``sales.quotes.view`` / ``.manage``.

- ``GET quotes`` — the list: ``status`` (one or comma-separated, the ``QuoteStatus`` values;
  or ``tab``: ``sent`` shows sent and viewed quotes), ``customer``, ``q`` (number, title,
  reference, customer name, total), ``page``; 50 a page, newest first, with ``counts`` per
  status — **the same enum and the same function** (``quotes.status_counts``) as the overview
  card (gap-05) — and ``tabs`` (All / Draft / Sent / Accepted / Declined / Expired / Invoiced:
  Sent counts sent and viewed quotes);
- ``POST quotes`` — a draft (``QU-0001`` taken at once, D-02-T02): ``customer``, ``date``,
  ``expiry_date`` (default 30 days after the date), ``title``, ``summary``, ``reference``,
  ``tax_mode``, discount, ``deposit_type`` / ``deposit_value``, ``notes``, ``lines`` (each with
  ``is_optional``, ``alternative_group``, ``selected``); lines are checked for the sales side
  (D-01-T06) and the figures are the server's (totals of the counted lines, D-02-T03);
- ``GET`` / ``PATCH`` / ``DELETE quotes/<id>`` — a quote; only a draft is edited (409 on a stale
  ``version``) or deleted (soft); a sent quote is changed by ``revise``;
- actions ``POST quotes/<id>/…``: ``send`` ``{to, message}`` (emailed with the PDF and the link,
  D-02-T15; ``{email: false}`` marks it sent and makes a link to share), ``link`` (a new public
  link; ``DELETE link`` revokes every link: 410 from then on), ``accept`` (the customer said yes
  another way), ``decline`` ``{reason}``, ``invoice`` ``{date}`` (an accepted quote becomes a
  draft invoice with identical lines and the deposit deducted, D-02-T09; 201), ``copy``
  ``{to: quote | invoice}`` (D-03a-T10; 201), ``revise`` (a new draft quote that supersedes this
  one — an accepted quote is never changed; its old link says "superseded"; 201);
- ``GET quotes/<id>/pdf`` — the PDF (D-02-T10).

Public, without signing in (the signed token is the credential; exempt from the tenant sweep —
the token names one quote — and declared ``@public``): ``GET q/<token>`` (``api.py``, counts the
view), ``POST q/<token>/preview`` ``{selections}`` (the totals for the options ticked, nothing
saved — the page recalculates live), ``POST q/<token>/accept`` ``{typed_name, signature,
selections}`` (D-02-T07 evidence; ``signature`` a ``data:image/png;base64,…`` URL or empty: the
typed name alone is the accessible way), ``POST q/<token>/decline`` ``{reason}``,
``GET q/<token>/pdf``. An unknown token is 404, a revoked link **410**; a refusal (expired,
already declined…) is 400 ``{code, detail}``.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import datetime as dt
from collections.abc import Callable
from decimal import Decimal
from typing import Any, TypeVar

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.documents.calculator import AMOUNT, NONE, PERCENT
from numo9.documents.models import TaxMode
from numo9.ledger.models import LedgerError
from numo9.rbac.drf import PUBLIC, RequiresPermission, requires_permission
from numo9.tenancy.context import current_org, org_context

from .invoices_api import (
    InvoiceLineSerializer,
    _money,
    _person,
    _ref,
    _refused,
    _uuid,
    invoice_url,
    line_row,
)
from .models import DepositType, Quote, QuoteLine, QuoteLink, QuoteStatus
from .permissions import QUOTES_MANAGE, QUOTES_VIEW

READ = "accounting.sales_quotes.read"
WRITE = "accounting.sales_quotes.write"
PAGE_SIZE = 50
DISCOUNTS = (NONE, AMOUNT, PERCENT)
VALID_DAYS = 30


def quote_url(quote: Quote) -> str:
    return f"/o/{quote.organisation.public_id}/sales/quotes/{quote.public_id}"


def quote_line_row(line: QuoteLine, counted: bool) -> dict[str, Any]:
    return {
        **line_row(line),  # type: ignore[arg-type]  # same document line base as invoices
        "is_optional": line.is_optional,
        "alternative_group": line.alternative_group,
        "selected": line.selected,
        "counted": counted,
    }


def quote_row(quote: Quote) -> dict[str, Any]:
    return {
        "id": str(quote.public_id),
        "number": quote.number,
        "status": quote.status,
        "status_label": str(QuoteStatus(quote.status).label),
        "title": quote.title,
        "customer": {"id": str(quote.contact.public_id), "name": quote.contact.display_name},
        "reference": quote.reference,
        "date": quote.date.isoformat(),
        "expiry_date": quote.expiry_date.isoformat(),
        "total": _money(quote.total),
        "url": quote_url(quote),
    }


def _active_link(quote: Quote) -> QuoteLink | None:
    link: QuoteLink | None = (
        QuoteLink.objects.filter(quote=quote, revoked_at__isnull=True)
        .order_by("-created_at", "-pk")
        .first()
    )
    return link


def _acceptance(quote: Quote) -> dict[str, Any] | None:
    from .models import QuoteAcceptance

    row = QuoteAcceptance.objects.filter(quote=quote).first()
    if row is None:
        return None
    return {
        "typed_name": row.typed_name,
        "signed": bool(row.signature_key),
        "ip": row.ip,
        "user_agent": row.user_agent,
        "accepted_at": row.accepted_at.isoformat(),
        "pdf_sha256": row.pdf_sha256,
    }


def quote_detail(quote: Quote) -> dict[str, Any]:
    from .pdf import deposit_amount
    from .quote_email import quote_link_url
    from .quote_links import link_token
    from .quotes import counted

    organisation = quote.organisation
    lines = list(
        quote.lines.select_related("account", "tax_code", "item").order_by("position", "pk")
    )
    flags = counted(lines)
    link = _active_link(quote)
    deposit_invoice = quote.deposit_invoice
    later = quote.revisions.filter(deleted_at__isnull=True).order_by("-pk").first()
    return {
        **quote_row(quote),
        "summary": quote.summary,
        "currency": quote.currency,
        "tax_mode": quote.tax_mode,
        "ship_to_country": quote.ship_to_country,
        "ship_to_province": quote.ship_to_province,
        "discount_type": quote.discount_type,
        "discount_value": f"{quote.discount_value:.4f}",
        "deposit_type": quote.deposit_type,
        "deposit_value": f"{quote.deposit_value:.4f}",
        "deposit_amount": _money(deposit_amount(quote)),
        "notes": quote.notes,
        "subtotal": _money(quote.subtotal),
        "discount_total": _money(quote.discount_total),
        "tax_total": _money(quote.tax_total),
        "version": quote.version,
        "sent_at": quote.sent_at.isoformat() if quote.sent_at else None,
        "viewed_at": quote.viewed_at.isoformat() if quote.viewed_at else None,
        "accepted_at": quote.accepted_at.isoformat() if quote.accepted_at else None,
        "declined_at": quote.declined_at.isoformat() if quote.declined_at else None,
        "decline_reason": quote.decline_reason,
        "expired_at": quote.expired_at.isoformat() if quote.expired_at else None,
        "invoiced_at": quote.invoiced_at.isoformat() if quote.invoiced_at else None,
        "invoice": None
        if quote.invoice is None
        else _ref(quote.invoice, number=quote.invoice.number, url=invoice_url(quote.invoice)),
        "deposit_invoice": None
        if deposit_invoice is None
        else _ref(
            deposit_invoice,
            number=deposit_invoice.number,
            status=deposit_invoice.status,
            total=_money(deposit_invoice.total),
            url=invoice_url(deposit_invoice),
        ),
        "revises": None
        if quote.revises is None
        else _ref(quote.revises, number=quote.revises.number, url=quote_url(quote.revises)),
        "superseded_by": None
        if later is None
        else _ref(later, number=later.number, url=quote_url(later)),
        "link": None
        if link is None
        else {
            "url": quote_link_url(link_token(link)),
            "views": link.views,
            "last_viewed_at": link.last_viewed_at.isoformat() if link.last_viewed_at else None,
        },
        "acceptance": _acceptance(quote),
        "pdf": f"/api/v1/o/{organisation.public_id}/quotes/{quote.public_id}/pdf",
        "lines": [quote_line_row(line, take) for line, take in zip(lines, flags, strict=True)],
    }


def _quote(public_id: Any) -> Quote:
    found: Quote | None = (
        Quote.objects.select_related(
            "contact", "organisation", "invoice", "deposit_invoice", "revises"
        )
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise NotFound(_("There's no quote with this id in this organisation."))
    return found


class QuoteLineSerializer(InvoiceLineSerializer):
    is_optional = serializers.BooleanField(required=False, default=False)
    alternative_group = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=40
    )
    selected = serializers.BooleanField(required=False, allow_null=True, default=None)


class QuoteSerializer(serializers.Serializer[Any]):
    customer = serializers.UUIDField()
    date = serializers.DateField()
    expiry_date = serializers.DateField(required=False, allow_null=True, default=None)
    title = serializers.CharField(required=False, allow_blank=True, default="", max_length=200)
    summary = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
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
    deposit_type = serializers.ChoiceField(choices=DepositType.choices, default=DepositType.NONE)
    deposit_value = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), default=Decimal("0")
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = QuoteLineSerializer(many=True, max_length=500)  # type: ignore[call-arg]
    version = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get("expiry_date") is None:
            attrs["expiry_date"] = attrs["date"] + dt.timedelta(days=VALID_DAYS)
        if attrs["expiry_date"] < attrs["date"]:
            raise serializers.ValidationError(
                {"expiry_date": [_("The expiry date is before the quote date.")]}
            )
        if attrs["discount_type"] == PERCENT and attrs["discount_value"] > 100:
            raise serializers.ValidationError(
                {"discount_value": [_("A discount can't be more than 100 %.")]}
            )
        if attrs["deposit_type"] == DepositType.PERCENT and attrs["deposit_value"] > 100:
            raise serializers.ValidationError(
                {"deposit_value": [_("A deposit percentage can't be more than 100 %.")]}
            )
        if attrs["deposit_type"] == DepositType.NONE:
            attrs["deposit_value"] = Decimal("0")
        for number, line in enumerate(attrs["lines"]):
            group = (line.get("alternative_group") or "").strip()
            line["alternative_group"] = group
            if line["is_optional"] and group:
                raise serializers.ValidationError(
                    {
                        "lines": {
                            str(number): {
                                "alternative_group": [
                                    _("A line is optional or an alternative, not both.")
                                ]
                            }
                        }
                    }
                )
            if line["selected"] is None:  # an optional line starts unticked (D-02-T01)
                line["selected"] = not line["is_optional"]
        return attrs


HEADER = (
    "date",
    "expiry_date",
    "title",
    "summary",
    "reference",
    "tax_mode",
    "ship_to_country",
    "ship_to_province",
    "discount_type",
    "discount_value",
    "deposit_type",
    "deposit_value",
    "notes",
)


def _resolve(values: dict[str, Any]) -> dict[str, Any]:
    """Public ids → records, then the side check of every line (D-01-T06: no purchase codes or
    expense accounts on a quote, codes in force on the quote date)."""
    from numo9.documents.validation import LineCheck, validate_lines

    from .invoices_api import _resolve as resolve_invoice

    records = resolve_invoice({**values, "terms": None, "due_date": None})
    validate_lines(
        "quote",
        values["date"],
        [LineCheck(line["account"], line["tax_code"]) for line in records["lines"]],
        tax_mode=values["tax_mode"],
    )
    return records


def _save(quote: Quote, values: dict[str, Any], records: dict[str, Any]) -> Quote:
    from .quotes import create_quote, recalculate

    header = {field: values[field] for field in HEADER}
    if quote.pk is None:
        quote = create_quote(
            current_org(), contact=records["customer"], created_by=quote.created_by, **header
        )
    else:
        quote.contact = records["customer"]
        for field, value in header.items():
            setattr(quote, field, value)
        quote.version += 1
        quote.save()
        quote.lines.all().delete()
    for position, (raw, line) in enumerate(zip(values["lines"], records["lines"], strict=True)):
        QuoteLine(
            organisation=quote.organisation,
            document=quote,
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
            is_optional=raw["is_optional"],
            alternative_group=raw["alternative_group"],
            selected=raw["selected"],
        ).save()
    return recalculate(quote)


def _invalid(error: LedgerError) -> Response:
    body: dict[str, Any] = {
        "code": getattr(error, "code", None) or "invalid",
        "detail": " ".join(str(m) for m in error.messages),
    }
    found = getattr(error, "problems", None)
    if found:
        body["problems"] = [problem.as_dict() for problem in found]
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def _tab_filter(query: Any) -> list[str]:
    from .quotes import TABS

    tab = (query.get("tab") or "").strip()
    if tab in TABS:
        return list(TABS[tab])
    wanted = [s.strip() for s in (query.get("status") or "").split(",") if s.strip()]
    return [s for s in wanted if s in QuoteStatus.values]


class QuoteView(APIView):
    queryset = Quote._base_manager.none()


class QuoteListView(QuoteView):
    @requires_permission(QUOTES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="quotes_list",
        parameters=[
            OpenApiParameter(
                "tab",
                str,
                enum=["all", "draft", "sent", "accepted", "declined", "expired", "invoiced"],
            ),
            OpenApiParameter("status", str),
            OpenApiParameter("customer", OpenApiTypes.UUID),
            OpenApiParameter("q", str),
            OpenApiParameter("page", int),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        from .quotes import status_counts, tab_counts

        query = request.query_params
        quotes = Quote.objects.filter(deleted_at__isnull=True).select_related(
            "contact", "organisation"
        )
        counts = status_counts()
        statuses = _tab_filter(query)
        if statuses:
            quotes = quotes.filter(status__in=statuses)
        customer = _uuid(query.get("customer"))
        if customer:
            quotes = quotes.filter(contact__public_id=customer)
        text = (query.get("q") or "").strip()
        if text:
            match = (
                Q(number__icontains=text)
                | Q(title__icontains=text)
                | Q(reference__icontains=text)
                | Q(contact__display_name__icontains=text)
            )
            with contextlib.suppress(ArithmeticError):
                match |= Q(total=Decimal(text.replace(",", "").replace("$", "")))
            quotes = quotes.filter(match)
        raw = str(query.get("page") or "1")
        page = int(raw) if raw.isdigit() and int(raw) > 0 else 1
        total = quotes.count()
        chunk = quotes.order_by("-date", "-pk")[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        return Response(
            {
                "count": total,
                "page": page,
                "pages": max(1, -(-total // PAGE_SIZE)),
                "counts": counts,
                "tabs": tab_counts(counts),
                "results": [quote_row(quote) for quote in chunk],
            }
        )

    @requires_permission(QUOTES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="quotes_create", request=QuoteSerializer, responses={201: OpenApiTypes.OBJECT}
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = QuoteSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        try:
            records = _resolve(values)
            with transaction.atomic():
                quote = _save(Quote(created_by=_person(request.user)), values, records)
        except LedgerError as error:
            return _invalid(error)
        return Response(quote_detail(_quote(quote.public_id)), status=201)


class QuoteDetailView(QuoteView):
    @requires_permission(QUOTES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="quotes_detail", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(quote_detail(_quote(public_id)))

    @requires_permission(QUOTES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="quotes_update", request=QuoteSerializer, responses={200: OpenApiTypes.OBJECT}
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        quote = _quote(public_id)
        if quote.status != QuoteStatus.DRAFT:
            return Response(
                {
                    "code": "sales.quote.not_editable",
                    "detail": _(
                        "Only a draft quote can be edited: revise it to send a new version."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        incoming = QuoteSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = dict(incoming.validated_data)
        if values.get("version") is not None and values["version"] != quote.version:
            return Response(
                {
                    "code": "sales.quote.stale",
                    "detail": _("Someone else saved this quote: reload it to see their changes."),
                    "version": quote.version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            records = _resolve(values)
            with transaction.atomic():
                locked = Quote._base_manager.select_for_update().get(pk=quote.pk)
                saved = _save(locked, values, records)
        except LedgerError as error:
            return _invalid(error)
        return Response(quote_detail(_quote(saved.public_id)))

    @requires_permission(QUOTES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="quotes_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        quote = _quote(public_id)
        if quote.status != QuoteStatus.DRAFT:
            return Response(
                {
                    "code": "sales.quote.not_deletable",
                    "detail": _("Only a draft quote can be deleted."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        quote.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _data(request: Request) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


def _date(value: Any) -> dt.date | None:
    return serializers.DateField().to_internal_value(value) if value else None


class _ActionView(QuoteView):
    created = False

    def act(self, quote: Quote, request: Request) -> Any:
        raise NotImplementedError

    def run(self, request: Request, public_id: Any) -> Response:
        quote = _quote(public_id)
        try:
            done = self.act(quote, request)
        except LedgerError as error:
            return _refused(error)
        if isinstance(done, Response):
            return done
        return Response(quote_detail(_quote(done.public_id)), status=201 if self.created else 200)


F = TypeVar("F", bound=Callable[..., Any])


def _action(name: str, *, created: bool = False, summary: str = "") -> Callable[[F], F]:
    """The decorators of a quote action: ``sales.quotes.manage`` and the write feature."""

    def wrap(method: F) -> F:
        method = extend_schema(
            operation_id=f"quotes_{name}",
            summary=summary or None,
            request=None,
            responses={201 if created else 200: OpenApiTypes.OBJECT},
        )(method)
        method = requires_feature(WRITE)(method)
        return requires_permission(QUOTES_MANAGE.key)(method)

    return wrap


class QuoteSendView(_ActionView):
    @_action("send", summary="Email the quote with its PDF and link, or mark it sent")
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, quote: Quote, request: Request) -> Any:
        from .quote_email import send_quote
        from .quote_links import issue_link
        from .quotes import send

        data = _data(request)
        if data.get("email") is False:
            with transaction.atomic():
                sent = send(quote, request.user)
                issue_link(sent, request.user)
            return sent
        to = data.get("to")
        recipients = [str(x) for x in to] if isinstance(to, list) else None
        send_quote(quote, request.user, to=recipients, message=str(data.get("message") or ""))
        return quote


class QuoteLinkView(_ActionView):
    @_action("link", summary="A new public link to the quote")
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    @requires_permission(QUOTES_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="quotes_link_revoke", responses={200: OpenApiTypes.OBJECT})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        from .quote_links import revoke_link

        quote = _quote(public_id)
        for link in QuoteLink.objects.filter(quote=quote, revoked_at__isnull=True):
            revoke_link(link)
        return Response(quote_detail(quote))

    def act(self, quote: Quote, request: Request) -> Any:
        from .quote_links import issue_link
        from .quotes import QuoteRefused

        if quote.status == QuoteStatus.DRAFT:
            raise QuoteRefused(
                _("Send the quote before sharing its link."), code="sales.quote.not_sent"
            )
        issue_link(quote, request.user)
        return quote


class QuoteAcceptView(_ActionView):
    @_action("accept", summary="Record that the customer accepted the quote")
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, quote: Quote, request: Request) -> Any:
        from .quotes import accept

        return accept(quote, user=request.user)


class QuoteDeclineView(_ActionView):
    @_action("decline", summary="Record that the customer declined the quote")
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, quote: Quote, request: Request) -> Any:
        from .quotes import decline

        return decline(quote, str(_data(request).get("reason") or ""))


class QuoteInvoiceView(_ActionView):
    @_action("invoice", created=True, summary="Turn the accepted quote into a draft invoice")
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, quote: Quote, request: Request) -> Any:
        from .quote_invoicing import convert_to_invoice

        invoice = convert_to_invoice(quote, request.user, date=_date(_data(request).get("date")))
        return Response(
            {
                "id": str(invoice.public_id),
                "status": invoice.status,
                "total": _money(invoice.total),
                "url": invoice_url(invoice),
            },
            status=status.HTTP_201_CREATED,
        )


class QuoteCopyView(_ActionView):
    @_action("copy", created=True, summary="Copy the quote to a new quote or invoice")
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, quote: Quote, request: Request) -> Any:
        from .copying import copy_document

        data = _data(request)
        to = str(data.get("to") or "quote")
        if to not in ("invoice", "quote"):
            raise serializers.ValidationError({"to": [_("Copy to an invoice or a quote.")]})
        copy = copy_document(quote, to, request.user, date=_date(data.get("date")))
        if to == "quote":
            self.created = True
            return copy
        return Response(
            {"id": str(copy.public_id), "status": copy.status, "url": invoice_url(copy)},
            status=status.HTTP_201_CREATED,
        )


class QuoteReviseView(_ActionView):
    created = True

    @_action("revise", created=True, summary="A new draft version that supersedes this quote")
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, public_id)

    def act(self, quote: Quote, request: Request) -> Any:
        from .copying import copy_document
        from .quotes import QuoteRefused

        if quote.status in (QuoteStatus.DRAFT, QuoteStatus.INVOICED):
            raise QuoteRefused(
                _("A draft is edited, and an invoiced quote stays as it was: copy it instead."),
                code="sales.quote.not_revisable",
            )
        with transaction.atomic():
            copy: Quote = copy_document(quote, "quote", request.user)
            copy.revises = quote
            copy.save(update_fields=["revises", "updated_at"])
        return copy


def _pdf(data: bytes, name: str) -> HttpResponse:
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{name}"'
    return response


class QuotePdfView(QuoteView):
    @requires_permission(QUOTES_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="quotes_pdf", responses={(200, "application/pdf"): bytes})
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse:
        from .pdf import render_quote_pdf

        quote = _quote(public_id)
        return _pdf(render_quote_pdf(quote), f"{quote.number}.pdf")


# ---- public, through the link's token ----------------------------------------------------------


class _PublicView(APIView):
    permission_classes = [RequiresPermission, AllowAny]
    authentication_classes: list[Any] = []

    def quote(self, token: str) -> Quote | Response:
        from .quote_links import find_link

        link = find_link(token)
        if link is None:
            raise NotFound(_("This quote link isn't valid."))
        if link.revoked_at is not None:
            return Response(
                {"code": "sales.quote.link_revoked", "detail": _("This quote link was withdrawn.")},
                status=status.HTTP_410_GONE,
            )
        return link.quote


def _selections(data: dict[str, Any]) -> dict[str, bool]:
    raw = data.get("selections")
    if not isinstance(raw, dict):
        return {}
    return {str(key): bool(value) for key, value in raw.items()}


def _signature(text: Any) -> bytes | None:
    if not text:
        return None
    value = str(text)
    if value.startswith("data:"):
        value = value.split(",", 1)[-1]
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return b"invalid"


class PublicQuotePreviewView(_PublicView):
    @requires_permission(PUBLIC)  # the signed token is the credential
    @extend_schema(
        operation_id="quote_public_preview",
        summary="The quote's totals for the options ticked (nothing saved)",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT, 410: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, token: str) -> Response:
        from .quotes import selection_totals

        found = self.quote(token)
        if isinstance(found, Response):
            return found
        return Response(selection_totals(found, _selections(_data(request))))


class PublicQuoteAcceptView(_PublicView):
    @requires_permission(PUBLIC)  # the signed token is the credential
    @extend_schema(
        operation_id="quote_public_accept",
        summary="Accept the quote: typed name, optional drawn signature, the options chosen",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 410: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, token: str) -> Response:
        from numo9.audit.context import client_ip

        from .quote_links import AcceptanceRefused, accept_with_evidence, public_quote

        found = self.quote(token)
        if isinstance(found, Response):
            return found
        data = _data(request)
        try:
            accept_with_evidence(
                found,
                typed_name=str(data.get("typed_name") or ""),
                signature_png=_signature(data.get("signature")),
                selections=_selections(data),
                ip=client_ip(request),
                user_agent=str(request.META.get("HTTP_USER_AGENT", "")),
            )
        except AcceptanceRefused as error:
            return Response(
                {"code": error.code, "detail": str(error)}, status=status.HTTP_400_BAD_REQUEST
            )
        except LedgerError as error:
            return _refused(error)
        with org_context(found.organisation):
            fresh = Quote._base_manager.select_related("contact", "organisation").get(pk=found.pk)
        return Response(public_quote(fresh))


class PublicQuoteDeclineView(_PublicView):
    @requires_permission(PUBLIC)  # the signed token is the credential
    @extend_schema(
        operation_id="quote_public_decline",
        summary="Decline the quote, with an optional reason",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT, 410: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, token: str) -> Response:
        from .quote_links import public_quote
        from .quotes import decline

        found = self.quote(token)
        if isinstance(found, Response):
            return found
        reason = public_quote(found)["reason"]
        if reason is not None:  # expired, superseded, already decided: nothing to decline
            return Response(
                {
                    "code": f"sales.quote.{reason}",
                    "detail": _("This quote can't be declined any more."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with org_context(found.organisation):
                declined = decline(found, str(_data(request).get("reason") or ""))
        except LedgerError as error:
            return _refused(error)
        return Response(public_quote(declined))


class PublicQuotePdfView(_PublicView):
    @requires_permission(PUBLIC)  # the signed token is the credential
    @extend_schema(
        operation_id="quote_public_pdf",
        summary="The quote's PDF through its public link",
        responses={(200, "application/pdf"): OpenApiTypes.BINARY, 410: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, token: str) -> HttpResponse | Response:
        from .pdf import render_quote_pdf

        found = self.quote(token)
        if isinstance(found, Response):
            return found
        with org_context(found.organisation):
            data = render_quote_pdf(found)
        return _pdf(data, f"{found.number}.pdf")
