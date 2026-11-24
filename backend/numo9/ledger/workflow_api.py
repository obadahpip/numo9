"""Journal workflow API (C-04-T07), under ``/api/v1/o/<org>/``.

Approval (C-04-T02 rules, server-side whatever the screen shows):

- ``POST journals/<id>/submit`` — Draft → Awaiting approval (``accounting.journals.post``).
- ``POST journals/<id>/approve`` — approve and post (``accounting.journals.approve``; feature
  ``accounting.journals.approve``): 409 ``ledger.journal.self_approval`` for its author or
  submitter, 403 ``approval.limit_exceeded`` (with ``limit`` and the ``approvers`` who may) above
  the approver's limit; every posting rule applies (lock dates, cash guard…).
- ``POST journals/<id>/reject`` ``{reason}`` — back to Draft with the reason (≥ 3 characters).
- ``POST journals/<id>/withdraw`` — the author takes it back to Draft.

Recurring journals (C-04-T04…T06):

- ``GET`` / ``POST journals/recurring`` — the templates (``?status=active|paused|all``) / a new
  one: ``{name, narration, journal_type, lines, rrule, start_date, end_date, mode}``; its first
  run is the first occurrence from today (a start date in the past doesn't post the missed
  occurrences).
- ``GET`` / ``PATCH`` / ``DELETE journals/recurring/<id>`` — read, edit (``paused`` pauses and
  resumes; any other change bumps ``version`` and recomputes ``next_run``), delete (soft).
- ``GET journals/recurring/<id>/preview?count=6`` — the next occurrences from today (the editor's
  "next 6 dates") and the last runs (created or skipped, with the reason).
- ``POST journals/recurring/preview`` ``{rrule, start_date, end_date, count}`` — the same dates
  for an unsaved schedule; the editor and this endpoint use the one generator.

Errors: 400 with the field's message and ``code`` (``ledger.recurring.*``).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.orgsettings.locks import acting_user, local_date
from numo9.rbac.approvals import ApprovalLimitExceeded
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .api import JournalDetailSerializer
from .approvals import approve, reject, submit_for_approval, withdraw
from .journals_api import _detail, _refused
from .models import (
    SELECTABLE_CATEGORIES,
    JournalCategory,
    JournalEntry,
    LedgerError,
    RecurringJournalRun,
    RecurringJournalTemplate,
    RecurringMode,
)
from .permissions import JOURNALS_APPROVE, JOURNALS_POST, JOURNALS_VIEW
from .recurring import occurrences

READ = "accounting.journals.read"
WRITE = "accounting.journals.write"
APPROVE = "accounting.journals.approve"
PREVIEW_MAX = 24


def _entry(public_id: Any) -> JournalEntry:
    entry: JournalEntry | None = JournalEntry.objects.filter(
        public_id=public_id, deleted_at__isnull=True
    ).first()
    if entry is None:
        raise NotFound(_("There's no journal with this id in this organisation."))
    return entry


def _limit_refused(refused: ApprovalLimitExceeded) -> Response:
    extra = refused.extra or {}
    return Response(
        {
            "code": "approval.limit_exceeded",
            "detail": str(getattr(refused, "detail", "") or refused),
            "limit": extra.get("limit"),
            "approvers": extra.get("approvers", []),
        },
        status=status.HTTP_403_FORBIDDEN,
    )


class ReasonSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class _Action(APIView):
    queryset = JournalEntry._base_manager.none()

    def act(self, entry: JournalEntry, data: dict[str, Any]) -> JournalEntry:
        raise NotImplementedError

    def run(self, request: Request, org: Any, public_id: Any) -> Response:
        payload = ReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            entry = self.act(_entry(public_id), dict(payload.validated_data))
        except ApprovalLimitExceeded as refused:
            return _limit_refused(refused)
        except LedgerError as error:
            return _refused(error)
        return _detail(request, org, entry, status.HTTP_200_OK)


class JournalSubmitView(_Action):
    def act(self, entry: JournalEntry, data: dict[str, Any]) -> JournalEntry:
        return submit_for_approval(entry, acting_user())

    @requires_permission(JOURNALS_POST.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="journals_submit",
        summary="Submit a draft for approval",
        request=None,
        responses=JournalDetailSerializer,
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, org, public_id)


class JournalApproveView(_Action):
    def act(self, entry: JournalEntry, data: dict[str, Any]) -> JournalEntry:
        return approve(entry, acting_user())

    @requires_permission(JOURNALS_APPROVE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="journals_approve",
        summary="Approve a journal and post it",
        request=None,
        responses=JournalDetailSerializer,
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, org, public_id)


class JournalRejectView(_Action):
    def act(self, entry: JournalEntry, data: dict[str, Any]) -> JournalEntry:
        return reject(entry, acting_user(), data.get("reason") or "")

    @requires_permission(JOURNALS_APPROVE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="journals_reject",
        summary="Send a journal back to draft with a reason",
        request=ReasonSerializer,
        responses=JournalDetailSerializer,
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, org, public_id)


class JournalWithdrawView(_Action):
    def act(self, entry: JournalEntry, data: dict[str, Any]) -> JournalEntry:
        return withdraw(entry, acting_user())

    @requires_permission(JOURNALS_POST.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="journals_withdraw",
        summary="Take a journal back to draft",
        request=None,
        responses=JournalDetailSerializer,
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self.run(request, org, public_id)


# ---- recurring journals --------------------------------------------------------------------


class RecurringLineSerializer(serializers.Serializer[Any]):
    account = serializers.UUIDField()
    debit = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=Decimal("0")
    )
    credit = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=Decimal("0")
    )
    book = serializers.CharField(required=False, default="both")
    contact = serializers.UUIDField(required=False, allow_null=True, default=None)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class RecurringInputSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200)
    narration = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    journal_type = serializers.ChoiceField(
        choices=[(c, JournalCategory(c).label) for c in SELECTABLE_CATEGORIES], required=False
    )
    lines = RecurringLineSerializer(many=True)
    rrule = serializers.CharField(max_length=500)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    mode = serializers.ChoiceField(choices=RecurringMode.choices, required=False)
    paused = serializers.BooleanField(required=False)


class PreviewInputSerializer(serializers.Serializer[Any]):
    rrule = serializers.CharField(max_length=500)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True, default=None)
    count = serializers.IntegerField(required=False, default=6, min_value=1, max_value=PREVIEW_MAX)


def _today() -> dt.date:
    organisation = current_org()
    assert organisation is not None  # noqa: S101 - RequiresPermission answered 404 otherwise
    return local_date(organisation, timezone.now())


def _upcoming(
    rule: str, start: dt.date, end: dt.date | None, count: int, after: dt.date | None = None
) -> list[str]:
    since = after if after is not None else _today() - dt.timedelta(days=1)
    return [d.isoformat() for d in occurrences(rule, start, end, after=since, limit=count)]


def _row(template: RecurringJournalTemplate) -> dict[str, Any]:
    return {
        "id": str(template.public_id),
        "name": template.name,
        "narration": template.narration,
        "journal_type": template.journal_type,
        "lines": template.lines,
        "rrule": template.rrule,
        "start_date": template.start_date,
        "end_date": template.end_date,
        "mode": template.mode,
        "next_run": template.next_run,
        "paused": template.paused,
        "version": template.version,
        "created_by": template.created_by.name if template.created_by is not None else "",
        "updated_at": template.updated_at,
    }


def _runs(template: RecurringJournalTemplate, limit: int = 12) -> list[dict[str, Any]]:
    runs = RecurringJournalRun.objects.filter(template=template).select_related("entry")
    return [
        {
            "date": run.occurrence_date,
            "status": run.status,
            "code": run.code,
            "message": run.message,
            "version": run.template_version,
            "journal": {"id": str(run.entry.public_id), "status": run.entry.status}
            if run.entry is not None
            else None,
        }
        for run in runs.order_by("-occurrence_date")[:limit]
    ]


def _template(public_id: Any) -> RecurringJournalTemplate:
    found: RecurringJournalTemplate | None = (
        RecurringJournalTemplate.objects.filter(public_id=public_id, deleted_at__isnull=True)
        .select_related("created_by")
        .first()
    )
    if found is None:
        raise NotFound(_("There's no recurring journal with this id in this organisation."))
    return found


def _invalid(error: DjangoValidationError) -> Response:
    errors: dict[str, Any] = {}
    for name, items in error.error_dict.items():
        errors[name] = [str(m) for item in items for m in item.messages]
        code = next((item.code for item in items if item.code), None)
        if code:
            errors.setdefault("code", code)
    return Response(errors, status=status.HTTP_400_BAD_REQUEST)


def _lines_json(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "account": str(line["account"]),
            "debit": f"{line.get('debit') or 0:.2f}",
            "credit": f"{line.get('credit') or 0:.2f}",
            "book": line.get("book") or "both",
            "contact": str(line["contact"]) if line.get("contact") else None,
            "description": line.get("description") or "",
        }
        for line in lines
    ]


class RecurringListView(APIView):
    queryset = RecurringJournalTemplate._base_manager.none()

    @requires_permission(JOURNALS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="recurring_journals_list", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        items = RecurringJournalTemplate.objects.filter(deleted_at__isnull=True).select_related(
            "created_by"
        )
        wanted = request.query_params.get("status", "all")
        if wanted == "active":
            items = items.filter(paused=False)
        elif wanted == "paused":
            items = items.filter(paused=True)
        return Response({"results": [_row(t) for t in items.order_by("name", "pk")[:500]]})

    @requires_permission(JOURNALS_POST.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="recurring_journals_create",
        request=RecurringInputSerializer,
        responses={201: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = RecurringInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        person = acting_user()
        template = RecurringJournalTemplate(
            organisation=current_org(),
            name=data["name"].strip(),
            narration=data.get("narration") or "",
            journal_type=data.get("journal_type") or JournalCategory.GENERAL,
            lines=_lines_json(data["lines"]),
            rrule=data["rrule"].strip(),
            start_date=data["start_date"],
            end_date=data.get("end_date"),
            mode=data.get("mode") or RecurringMode.DRAFT,
            paused=bool(data.get("paused")),
            created_by=person if getattr(person, "is_authenticated", False) else None,
        )
        try:
            template.full_clean(exclude=["organisation", "created_by", "next_run"])
        except DjangoValidationError as error:
            return _invalid(error)
        # From today on: a schedule that started in the past doesn't post the missed months.
        upcoming = occurrences(
            template.rrule,
            template.start_date,
            template.end_date,
            after=_today() - dt.timedelta(days=1),
            limit=1,
        )
        template.next_run = upcoming[0] if upcoming else None
        template.save()
        return Response(_row(template), status=status.HTTP_201_CREATED)


class RecurringDetailView(APIView):
    queryset = RecurringJournalTemplate._base_manager.none()

    @requires_permission(JOURNALS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="recurring_journals_get", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        template = _template(public_id)
        return Response({**_row(template), "runs": _runs(template)})

    @requires_permission(JOURNALS_POST.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="recurring_journals_update",
        request=RecurringInputSerializer,
        responses={200: dict},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        payload = RecurringInputSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        with transaction.atomic():
            template = RecurringJournalTemplate.objects.select_for_update().get(
                pk=_template(public_id).pk
            )
            schedule_changed = False
            for field in ("name", "narration", "journal_type", "mode"):
                if field in data:
                    setattr(template, field, data[field])
            if "lines" in data:
                template.lines = _lines_json(data["lines"])
            for field in ("rrule", "start_date", "end_date"):
                if field in data:
                    setattr(template, field, data[field])
                    schedule_changed = True
            edited = set(data) - {"paused"}
            if "paused" in data:
                template.paused = data["paused"]
            try:
                template.full_clean(exclude=["organisation", "created_by", "next_run"])
            except DjangoValidationError as error:
                transaction.set_rollback(True)
                return _invalid(error)
            if edited:
                template.version += 1
            if schedule_changed or ("paused" in data and not data["paused"]):
                # From today on: past occurrences already ran (or are skipped on purpose).
                after = _today() - dt.timedelta(days=1)
                done = (
                    RecurringJournalRun.objects.filter(template=template)
                    .order_by("-occurrence_date")
                    .values_list("occurrence_date", flat=True)
                    .first()
                )
                if done is not None:
                    after = max(after, done)
                upcoming = occurrences(
                    template.rrule, template.start_date, template.end_date, after=after, limit=1
                )
                template.next_run = upcoming[0] if upcoming else None
            template.save()
        return Response({**_row(template), "runs": _runs(template)})

    @requires_permission(JOURNALS_POST.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="recurring_journals_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        _template(public_id).soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecurringPreviewView(APIView):
    queryset = RecurringJournalTemplate._base_manager.none()

    @requires_permission(JOURNALS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="recurring_journals_preview", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        template = _template(public_id)
        try:
            count = min(max(int(request.query_params.get("count", 6)), 1), PREVIEW_MAX)
        except ValueError:
            count = 6
        after = None
        if template.next_run is not None:
            after = template.next_run - dt.timedelta(days=1)
        dates = (
            _upcoming(template.rrule, template.start_date, template.end_date, count, after)
            if template.next_run is not None
            else []
        )
        return Response({"dates": dates, "paused": template.paused, "runs": _runs(template)})


class RecurringSchedulePreviewView(APIView):
    queryset = RecurringJournalTemplate._base_manager.none()

    @requires_permission(JOURNALS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="recurring_journals_schedule_preview",
        request=PreviewInputSerializer,
        responses={200: dict},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = PreviewInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        if data.get("end_date") and data["end_date"] < data["start_date"]:
            return Response(
                {
                    "end_date": [_("The end date is before the start date.")],
                    "code": "ledger.recurring.end_before_start",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            start = data["start_date"]
            since = max(_today(), start) - dt.timedelta(days=1)
            dates = _upcoming(data["rrule"], start, data.get("end_date"), data["count"], since)
        except DjangoValidationError as error:
            return _invalid(error)
        return Response({"dates": dates})
