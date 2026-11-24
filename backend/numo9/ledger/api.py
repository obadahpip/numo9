"""Journals read API (C-02-T15), under ``/api/v1/o/<org>/`` (writing: ``journals_api``, C-03).

- ``GET journals`` — the organisation's journal entries, newest first: number, date, type,
  status, narration, source, books, totals. Filters ``status`` (several, comma-separated;
  default: posted and reversed), ``from``/``to`` (dates), ``type``, ``source_type`` +
  ``source_id`` (the entries of one document), ``account`` (public id: entries with a line on it),
  ``book`` (``accounting``/``tax``: entries in that book), ``q`` (narration or number); pages of
  ``limit`` (1–200, 50) from ``offset``.
- ``GET journals/<id>`` — one entry: header, every line (account, debit, credit, book, contact,
  description, tax code, tracking), totals per book it touches, source, the reversal links both
  ways, who posted it and when, and its audit trail (action, by, when).

Permission ``accounting.journals.view``; feature ``accounting.journals.read``. Read-only: entries
are written by the posting service only (C-02-T08, T14).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db.models import Count, Exists, OuterRef, Q, QuerySet, Sum
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.audit.models import AuditEvent
from numo9.catalogue.drf import requires_feature
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .models import Book, JournalCategory, JournalEntry, JournalLine, JournalStatus
from .permissions import JOURNALS_VIEW
from .sequence import format_journal_number
from .validation import BOOKS_OF_LINE

READ = "accounting.journals.read"
VISIBLE = (JournalStatus.POSTED, JournalStatus.REVERSED)
MAX_LIMIT, DEFAULT_LIMIT = 200, 50


class JournalSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    number = serializers.CharField(allow_blank=True)
    date = serializers.DateField()
    type = serializers.CharField()
    journal_type = serializers.CharField(help_text="general, adjusting, reclass, tax_adjustment…")
    journal_type_label = serializers.CharField()
    auto_reverse_on = serializers.DateField(allow_null=True)
    status = serializers.CharField()
    narration = serializers.CharField(allow_blank=True)
    source = serializers.DictField(allow_null=True)  # type: ignore[assignment]
    book_scope = serializers.CharField()
    total = serializers.DecimalField(max_digits=18, decimal_places=2)
    lines = serializers.IntegerField()
    reversal_of = serializers.DictField(allow_null=True)
    reversed_by = serializers.DictField(allow_null=True)


class JournalPageSerializer(serializers.Serializer[Any]):
    results = JournalSummarySerializer(many=True)
    count = serializers.IntegerField()
    next_offset = serializers.IntegerField(allow_null=True)


class JournalLineSerializer(serializers.Serializer[Any]):
    line = serializers.IntegerField()
    account = serializers.DictField()
    debit = serializers.DecimalField(max_digits=18, decimal_places=2)
    credit = serializers.DecimalField(max_digits=18, decimal_places=2)
    book = serializers.CharField()
    contact = serializers.DictField(allow_null=True)
    description = serializers.CharField(allow_blank=True)
    tax_code = serializers.CharField(allow_blank=True)
    tracking = serializers.DictField()


class JournalDetailSerializer(JournalSummarySerializer):
    lines = JournalLineSerializer(many=True)  # type: ignore[assignment]
    books = serializers.DictField()
    posted_by = serializers.DictField(allow_null=True)
    posted_at = serializers.DateTimeField(allow_null=True)
    overrides = serializers.ListField(
        child=serializers.DictField(), help_text="Advisers' reasons for posting past the cash guard"
    )
    audit = serializers.ListField(child=serializers.DictField())
    created_by = serializers.DictField(allow_null=True)
    approval = serializers.DictField(
        allow_null=True, help_text="The latest approval round (C-04): submitted, decided, reason"
    )
    viewer = serializers.DictField(
        help_text="What the signed-in person may do with it (C-04-T10): is_author, can_approve"
    )


def _person(user: Any) -> dict[str, str] | None:
    return {"id": str(user.public_id), "name": user.name} if user is not None else None


def _approval(entry: JournalEntry, user: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """The latest approval round and the viewer's standing (author? may approve?)."""
    from numo9.rbac.approvals import effective_limit
    from numo9.rbac.inbox import blocked_reason
    from numo9.rbac.models import ApprovalDocumentType
    from numo9.rbac.resolver import has_perm

    from .approvals import journal_total, latest_round

    round_ = latest_round(entry)
    authors = {pk for pk in (entry.created_by_id, round_.submitted_by_id if round_ else None) if pk}
    is_author = getattr(user, "pk", None) in authors
    blocked: str | None = "not_waiting"
    if entry.status == "awaiting_approval":
        if not has_perm(user, entry.organisation, "accounting.journals.approve"):
            blocked = "permission"
        else:
            limit = effective_limit(
                user, ApprovalDocumentType.JOURNAL, organisation=entry.organisation
            )
            blocked = blocked_reason(user, authors, limit, journal_total(entry))
    approval = (
        {
            "decision": round_.decision,
            "submitted_by": _person(round_.submitted_by),
            "submitted_at": round_.submitted_at,
            "decided_by": _person(round_.decided_by),
            "decided_at": round_.decided_at,
            "reason": round_.reason,
        }
        if round_ is not None
        else None
    )
    return approval, {"is_author": is_author, "can_approve": blocked is None, "blocked": blocked}


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _org_number(entry: JournalEntry | None) -> dict[str, str] | None:
    if entry is None:
        return None
    return {
        "id": str(entry.public_id),
        "number": format_journal_number(entry.organisation, entry.number),
    }


def _summary(entry: JournalEntry) -> dict[str, Any]:
    reversed_by = getattr(entry, "reversed_by", None)
    return {
        "id": str(entry.public_id),
        "number": format_journal_number(entry.organisation, entry.number),
        "date": entry.date,
        "type": entry.type,
        "journal_type": entry.journal_type,
        "journal_type_label": str(JournalCategory(entry.journal_type).label),
        "auto_reverse_on": entry.auto_reverse_on,
        "status": entry.status,
        "narration": entry.narration,
        "source": {"type": entry.source_type, "id": entry.source_id} if entry.source_type else None,
        "book_scope": entry.book_scope,
        "total": _money(getattr(entry, "total_debit", None) or Decimal("0")),
        "lines": getattr(entry, "line_count", 0),
        "reversal_of": _org_number(entry.reversal_of),
        "reversed_by": _org_number(reversed_by),
    }


def _date(params: Any, name: str) -> dt.date | None:
    raw = params.get(name)
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise ValidationError({name: [_("Use a date like 2026-03-31.")]}) from None


def _int(params: Any, name: str, default: int, low: int, high: int) -> int:
    raw = params.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError({name: [_("Use a whole number.")]}) from None
    return max(low, min(high, value))


def _filtered(params: Any) -> QuerySet[JournalEntry]:
    rows = JournalEntry.objects.filter(deleted_at__isnull=True)
    statuses = [s for s in (params.get("status") or "").split(",") if s]
    if any(s not in JournalStatus.values for s in statuses):
        raise ValidationError({"status": [_("Unknown status.")]})
    rows = rows.filter(status__in=statuses or VISIBLE)
    if (start := _date(params, "from")) is not None:
        rows = rows.filter(date__gte=start)
    if (end := _date(params, "to")) is not None:
        rows = rows.filter(date__lte=end)
    if journal_type := params.get("type"):
        rows = rows.filter(type=journal_type)
    if category := params.get("journal_type"):
        rows = rows.filter(journal_type=category)
    if source_type := params.get("source_type"):
        rows = rows.filter(source_type=source_type)
        if source_id := params.get("source_id"):
            rows = rows.filter(source_id=source_id)
    if account := params.get("account"):
        rows = rows.filter(
            Exists(JournalLine.objects.filter(entry=OuterRef("pk"), account__public_id=account))
        )
    if book := params.get("book"):
        if book not in (Book.ACCOUNTING, Book.TAX):
            raise ValidationError({"book": [_("Use accounting or tax.")]})
        rows = rows.filter(book_scope__in=(Book.BOTH, book))
    if text := (params.get("q") or "").strip():
        query = Q(narration__icontains=text)
        digits = text.upper().removeprefix("JE-").lstrip("0")
        if digits.isdigit():
            query |= Q(number=int(digits))
        rows = rows.filter(query)
    return rows


LIST_PARAMETERS = [
    OpenApiParameter("status", OpenApiTypes.STR, description="Statuses (default posted,reversed)"),
    OpenApiParameter("from", OpenApiTypes.DATE, description="First date"),
    OpenApiParameter("to", OpenApiTypes.DATE, description="Last date"),
    OpenApiParameter("type", OpenApiTypes.STR, description="What posted it (manual, sales…)"),
    OpenApiParameter("journal_type", OpenApiTypes.STR, description="General, adjusting…"),
    OpenApiParameter("source_type", OpenApiTypes.STR, description="Source document type"),
    OpenApiParameter("source_id", OpenApiTypes.STR, description="Source document id"),
    OpenApiParameter("account", OpenApiTypes.UUID, description="Entries with a line on it"),
    OpenApiParameter("book", OpenApiTypes.STR, description="accounting or tax"),
    OpenApiParameter("q", OpenApiTypes.STR, description="Narration or number"),
    OpenApiParameter("limit", OpenApiTypes.INT, description="1–200 (50)"),
    OpenApiParameter("offset", OpenApiTypes.INT, description="Rows to skip"),
]


class JournalListView(APIView):
    queryset = JournalEntry._base_manager.none()  # tenant sweep: rows of JournalEntry

    @requires_permission(JOURNALS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="journals_list",
        summary="The organisation's journal entries, newest first",
        parameters=LIST_PARAMETERS,
        responses=JournalPageSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        params = request.query_params
        rows = _filtered(params)
        count = rows.count()
        limit = _int(params, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
        offset = _int(params, "offset", 0, 0, 10**9)
        page = list(
            rows.select_related("organisation", "reversal_of", "reversed_by")
            .annotate(total_debit=Sum("lines__debit"), line_count=Count("lines"))
            .order_by("-date", "-number", "-pk")[offset : offset + limit]
        )
        return Response(
            {
                "results": [_summary(entry) for entry in page],
                "count": count,
                "next_offset": offset + limit if offset + limit < count else None,
            }
        )


def _books(lines: list[JournalLine]) -> dict[str, dict[str, str]]:
    totals: dict[str, list[Decimal]] = {}
    for line in lines:
        for book in BOOKS_OF_LINE[line.book]:
            pair = totals.setdefault(str(book), [Decimal("0"), Decimal("0")])
            pair[0] += line.debit
            pair[1] += line.credit
    return {
        book: {"debit": f"{d:.2f}", "credit": f"{c:.2f}"} for book, (d, c) in sorted(totals.items())
    }


def _line(line: JournalLine) -> dict[str, Any]:
    account = line.account
    contact = line.contact
    return {
        "line": line.line_no,
        "account": {"id": str(account.public_id), "code": account.code, "name": account.name},
        "debit": _money(line.debit),
        "credit": _money(line.credit),
        "book": line.book,
        "contact": {"id": str(contact.public_id), "name": contact.display_name}
        if contact is not None
        else None,
        "description": line.description,
        "tax_code": line.tax_code,
        "tracking": line.tracking or {},
    }


def _audit(entry: JournalEntry) -> list[dict[str, Any]]:
    events = AuditEvent.objects.filter(
        object_type=JournalEntry._meta.label, object_id=str(entry.public_id)
    ).order_by("created_at", "id")
    return [
        {"action": e.action, "by": e.actor_label, "at": e.created_at.isoformat()} for e in events
    ]


class JournalDetailView(APIView):
    queryset = JournalEntry._base_manager.none()

    @requires_permission(JOURNALS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="journals_get",
        summary="One journal entry with its lines, books, source, reversal links and audit",
        responses=JournalDetailSerializer,
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        entry = (
            JournalEntry.objects.filter(public_id=public_id, deleted_at__isnull=True)
            .select_related("organisation", "reversal_of", "reversed_by", "posted_by", "created_by")
            .first()
        )
        if entry is None:
            raise NotFound(_("There's no journal with this id in this organisation."))
        lines = list(entry.lines.order_by("line_no").select_related("account", "contact"))
        body = _summary(entry)
        body.update(
            total=_money(sum((line.debit for line in lines), Decimal("0"))),
            lines=[_line(line) for line in lines],
            books=_books(lines),
            posted_by={"id": str(entry.posted_by.public_id), "name": entry.posted_by.name}
            if entry.posted_by is not None
            else None,
            posted_at=entry.posted_at,
            overrides=[
                {
                    "reason": o.reason,
                    "by": o.user.name if o.user is not None else "",
                    "at": o.at.isoformat(),
                    "shortfalls": o.shortfalls,
                }
                for o in entry.overrides.select_related("user")
            ],
            audit=_audit(entry),
            created_by=_person(entry.created_by),
        )
        body["approval"], body["viewer"] = _approval(entry, request.user)
        assert current_org() is not None  # noqa: S101 - RequiresPermission answered 404 otherwise
        return Response(body)
