"""Manual journals write API (C-03-T10), under ``/api/v1/o/<org>/``.

- ``POST journals`` — write a manual journal and post it (``"post": false`` keeps it a draft):
  ``date``, ``journal_type`` (General / Adjusting / Reclass / Tax adjustment — the system types
  are never accepted here), ``narration``, ``auto_reverse_on``, ``lines`` (``account``,
  ``debit``, ``credit``, ``book``, ``contact``, ``description``, ``tracking``), ``attachments``
  (document ids) and ``override_reason`` (an adviser posting past the cash guard). 201 with the
  journal (the read API's detail shape).
- ``POST journals/check`` — the same body, nothing written: every problem the journal would
  meet (``errors``), the bank and cash accounts it would take below zero (``shortfalls``, with
  the screen's message "Petty Cash would be −994.17 on 15 Jun 2026"), whether the person is an
  adviser (``adviser``: may post anyway with a reason) and what it still needs
  (``needs.attachment``, ``needs.contact_lines``) — what the journal screen shows as you type.
- ``POST journals/<id>/post`` — post a draft (``override_reason`` optional).

Errors: 400 ``ledger.journal.invalid`` with every problem in ``errors`` (``code`` + ``message``,
line and account named); 409 ``ledger.journal.negative_cash`` (someone who isn't an adviser) or
``ledger.journal.override_reason_required`` (an adviser without a reason) with ``shortfalls``;
409 ``lock.violation`` / ``ledger.period.closed`` from the period check.

Permission ``accounting.journals.post``; feature ``accounting.journals.write`` (402 without it).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
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
from numo9.orgsettings.locks import acting_user, is_adviser, local_date
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .api import JournalDetailSerializer, JournalDetailView, JournalListView
from .cash_guard import shortfalls
from .models import (
    SELECTABLE_CATEGORIES,
    Account,
    AccountType,
    Book,
    JournalCategory,
    JournalEntry,
    JournalStatus,
    LedgerError,
)
from .permissions import JOURNALS_POST
from .policy import NegativeCash, check_policy
from .services import post_entry, post_journal, save_draft
from .validation import JournalSpec, LineSpec, validate_journal

WRITE = "accounting.journals.write"


class LineInputSerializer(serializers.Serializer[Any]):
    account = serializers.UUIDField(help_text="The account's id")
    debit = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=Decimal("0")
    )
    credit = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, default=Decimal("0")
    )
    book = serializers.ChoiceField(choices=Book.choices, required=False, default=Book.BOTH)
    contact = serializers.UUIDField(required=False, allow_null=True, default=None)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    tracking = serializers.DictField(required=False, default=dict)


class JournalInputSerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    journal_type = serializers.ChoiceField(
        choices=[(c, JournalCategory(c).label) for c in SELECTABLE_CATEGORIES],
        required=False,
        default=JournalCategory.GENERAL,
    )
    narration = serializers.CharField(required=False, allow_blank=True, default="")
    auto_reverse_on = serializers.DateField(required=False, allow_null=True, default=None)
    lines = LineInputSerializer(many=True)
    attachments = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    override_reason = serializers.CharField(required=False, allow_blank=True, default="")
    post = serializers.BooleanField(required=False, default=True)


class PostInputSerializer(serializers.Serializer[Any]):
    override_reason = serializers.CharField(required=False, allow_blank=True, default="")


class ProblemSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    message = serializers.CharField()


class CheckSerializer(serializers.Serializer[Any]):
    ok = serializers.BooleanField()
    errors = ProblemSerializer(many=True)  # type: ignore[assignment]
    shortfalls = serializers.ListField(child=serializers.DictField())
    adviser = serializers.BooleanField()
    needs = serializers.DictField()


def _resolve(data: dict[str, Any]) -> tuple[JournalSpec, list[Document]]:
    """The spec from the payload: accounts, contacts and documents by public id, this
    organisation's only (unknown ones → 400 on the field)."""
    lines = data["lines"]
    account_ids = {line["account"] for line in lines}
    accounts = {a.public_id: a for a in Account.objects.filter(public_id__in=account_ids)}
    contact_ids = {line["contact"] for line in lines if line.get("contact")}
    contacts = {
        c.public_id: c
        for c in Contact.objects.filter(public_id__in=contact_ids, deleted_at__isnull=True)
    }
    missing: dict[str, Any] = {}
    for index, line in enumerate(lines):
        problems: dict[str, list[str]] = {}
        if line["account"] not in accounts:
            problems["account"] = [_("There's no account with this id in this organisation.")]
        if line.get("contact") and line["contact"] not in contacts:
            problems["contact"] = [_("There's no contact with this id in this organisation.")]
        if problems:
            missing[str(index)] = problems
    documents = list(Document.objects.filter(public_id__in=data.get("attachments") or []))
    if len(documents) != len(set(data.get("attachments") or [])):
        raise serializers.ValidationError(
            {"attachments": [_("One of the documents isn't in this organisation.")]}
        )
    if missing:
        raise serializers.ValidationError({"lines": missing})
    spec = JournalSpec(
        date=data["date"],
        journal_type=data["journal_type"],
        narration=data.get("narration") or "",
        auto_reverse_on=data.get("auto_reverse_on"),
        lines=tuple(
            LineSpec(
                account=accounts[line["account"]],
                debit=line["debit"],
                credit=line["credit"],
                book=line["book"],
                contact=contacts.get(line["contact"]) if line.get("contact") else None,
                tracking=line.get("tracking") or {},
                description=line.get("description") or "",
            )
            for line in lines
        ),
    )
    return spec, documents


def _problems(error: Exception) -> list[dict[str, str]]:
    items = getattr(error, "error_list", None) or [error]
    return [
        {"code": str(getattr(e, "code", "") or "ledger.journal.invalid"), "message": m}
        for e in items
        for m in getattr(e, "messages", [str(e)])
    ]


def _refused(error: LedgerError) -> Response:
    if isinstance(error, NegativeCash):
        code = error.error_list[0].code or "ledger.journal.negative_cash"
        return Response(
            {
                "code": code,
                "detail": error.messages[0],
                "adviser": error.adviser,
                "shortfalls": [p.as_dict() for p in error.projections],
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response(
        {
            "code": "ledger.journal.invalid",
            "detail": _("This journal can't be posted: %(count)d problem(s).")
            % {"count": len(_problems(error))},
            "errors": _problems(error),
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _detail(request: Request, org: Any, entry: JournalEntry, code: int) -> Response:
    response = JournalDetailView().get(request, org, entry.public_id)
    response.status_code = code
    return response


class JournalsView(JournalListView):
    """``GET journals`` (the read API, C-02-T15) and ``POST journals`` (write, C-03-T10)."""

    @requires_permission(JOURNALS_POST.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="journals_create",
        summary="Write a manual journal and post it (or keep it as a draft)",
        request=JournalInputSerializer,
        responses={201: JournalDetailSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = JournalInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        spec, documents = _resolve(data)
        person = acting_user()
        try:
            if data["post"]:
                entry = post_journal(
                    spec,
                    user=person,
                    attachments=documents,
                    override_reason=data.get("override_reason") or "",
                )
            else:
                with transaction.atomic():
                    entry = save_draft(spec, user=person)
                    if documents:
                        from numo9.files.attachments import attach

                        for document in documents:
                            attach(document, "ledger.JournalEntry", entry.public_id, user=person)
        except LedgerError as error:
            return _refused(error)
        return _detail(request, org, entry, status.HTTP_201_CREATED)


class JournalCheckView(APIView):
    queryset = JournalEntry._base_manager.none()

    @requires_permission(JOURNALS_POST.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="journals_check",
        summary="Every problem a journal would meet, and the cash it would take below zero",
        request=JournalInputSerializer,
        responses=CheckSerializer,
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = JournalInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        spec, documents = _resolve(payload.validated_data)
        organisation = current_org()
        assert organisation is not None  # noqa: S101 - RequiresPermission answered 404 otherwise
        person = acting_user()
        errors: list[dict[str, str]] = []
        found: list[Any] = []
        needs = {"attachment": False, "contact_lines": []}
        try:
            checked = validate_journal(spec, organisation)
        except LedgerError as error:
            errors = _problems(error)
        else:
            try:
                check_policy(checked, attachments=len(documents), organisation=organisation)
            except LedgerError as error:
                errors = _problems(error)
            found = shortfalls(checked, organisation, today=local_date(organisation, _now()))
            needs = _needs(checked, errors)
        return Response(
            {
                "ok": not errors and not found,
                "errors": errors,
                "shortfalls": [p.as_dict() for p in found],
                "adviser": is_adviser(person, organisation),
                "needs": needs,
            }
        )


def _now() -> Any:
    from django.utils import timezone

    return timezone.now()


def _needs(checked: Any, errors: list[dict[str, str]]) -> dict[str, Any]:
    codes = {e["code"] for e in errors}
    contact_lines = sorted(
        {
            line.line_no
            for line in checked.lines
            if not line.spec.contact
            and (
                line.account.require_contact
                or (
                    "ledger.journal.expense_contact_required" in codes
                    and line.account.type == AccountType.EXPENSE
                )
            )
        }
    )
    return {
        "attachment": bool(
            codes
            & {"ledger.journal.attachment_required", "ledger.journal.expense_attachment_required"}
        ),
        "contact_lines": contact_lines,
    }


class JournalPostView(APIView):
    queryset = JournalEntry._base_manager.none()

    @requires_permission(JOURNALS_POST.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="journals_post",
        summary="Post a draft journal",
        request=PostInputSerializer,
        responses=JournalDetailSerializer,
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        payload = PostInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        entry = JournalEntry.objects.filter(public_id=public_id, deleted_at__isnull=True).first()
        if entry is None:
            raise NotFound(_("There's no journal with this id in this organisation."))
        if entry.status not in (JournalStatus.DRAFT, JournalStatus.AWAITING_APPROVAL):
            return Response(
                {
                    "code": "ledger.journal.illegal_transition",
                    "detail": _("Only a draft can be posted."),
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            entry = post_entry(
                entry,
                user=acting_user(),
                override_reason=payload.validated_data.get("override_reason") or "",
            )
        except LedgerError as error:
            return _refused(error)
        return _detail(request, org, entry, status.HTTP_200_OK)
