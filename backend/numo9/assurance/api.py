"""Assurance API (K-09-T20), under ``/api/v1/o/<org>/assurance/``. Feature key
``accounting.assurance.read`` (every package with Accounting); permissions
``accounting.assurance.view`` (see) and ``accounting.assurance.manage`` (run, acknowledge, false
positive, reopen, fix, rule settings). Findings are the organisation's own (row-level security):
practice staff see the organisations they are assigned to only (A-01).

- ``GET assurance/`` — the summary: score, counts by severity and status, groups by rule, last run;
- ``GET assurance/findings?severity=&status=&rule=&q=`` — findings (default: open and
  acknowledged), most severe first, each with its plain-language ``explanation``, ``has_fix`` and
  ``source`` (what *View source* opens); ``GET assurance/findings/<id>`` — one, with its history;
- ``POST assurance/findings/<id>/acknowledge`` ``{reason?}`` · ``…/false-positive``
  ``{reason}`` · ``…/reopen``;
- ``GET assurance/findings/<id>/fix`` — the proposed fix (``null`` when none);
  ``POST …/fix`` ``{lines?, date?, narration?}`` — the draft journal (``201``), never posted;
- ``POST assurance/run`` — a full run in the background (``202`` with the job);
  ``GET assurance/runs`` — the latest runs;
- ``GET assurance/rules`` — every rule with its schema and the organisation's settings;
  ``PATCH assurance/rules/<code>`` ``{enabled?, severity?, params?}`` — validated, audited, used
  by the next run;
- ``GET assurance/heatmap?days=&user=`` — activity per day and person (audit log).

A refusal is a ``400`` ``{"code", "detail"}`` (``assurance.param_invalid`` with ``param``,
``assurance.fix.*``, ``assurance.finding.*``).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, Q, Value, When
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.audit.models import AuditEvent
from numo9.catalogue.drf import requires_feature
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from . import fixes, workflow
from .heatmap import heatmap
from .models import (
    ACTIVE_STATUSES,
    ExceptionFinding,
    ExceptionRuleConfig,
    ExceptionRun,
    FindingStatus,
    Severity,
)
from .permissions import ASSURANCE_MANAGE, ASSURANCE_VIEW
from .rules.base import clean_params, json_params, registry, settings_for
from .runner import start_run
from .score import summary

FEATURE = "accounting.assurance.read"
VIEW = ASSURANCE_VIEW.key
MANAGE = ASSURANCE_MANAGE.key
MAX_FINDINGS = 500


def _org() -> Any:
    organisation = current_org()
    if organisation is None:
        raise NotFound
    return organisation


def _refused(error: ValidationError) -> Response:
    code = getattr(error, "code", None) or "invalid"
    body: dict[str, Any] = {"code": code, "detail": " ".join(str(m) for m in error.messages)}
    params = getattr(error, "params", None) or {}
    if "param" in params:
        body["param"] = params["param"]
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def _person(user: Any) -> dict[str, str] | None:
    return {"id": str(user.public_id), "name": user.name or user.email} if user else None


#: What *View source* opens, per subject type: (kind, link template under /o/<org>/).
SOURCES: dict[str, tuple[str, str]] = {
    "ledger.JournalEntry": ("journal", "accounting/journals/{id}"),
    "ledger.JournalLine": ("journal", "accounting/journals/{entry}"),
    "ledger.Account": ("account", "accounting/chart-of-accounts?account={id}"),
    "purchases.Bill": ("bill", "purchases/bills/{id}"),
    "sales.Invoice": ("invoice", "sales/invoices/{id}"),
    "contacts.Contact": ("contact", "contacts/{id}"),
    "accounts.User": ("user", "settings/users"),
    "conversion.ConversionSession": ("conversion", "accounting/conversion"),
}
#: Organisation-level findings open the page that fixes them.
ORG_SOURCES: dict[str, str] = {
    "UNMAPPED_GIFI": "accounting/chart-of-accounts",
    "MISSING_BN": "settings/tax-registrations",
    "MISSING_LOCK_DATE": "settings/lock-dates",
    "TAX_CODE_OVERRIDE_RATE": "accounting/chart-of-accounts",
}


def source_of(finding: ExceptionFinding) -> dict[str, str] | None:
    if finding.subject_type == "tenancy.Organisation":
        path = ORG_SOURCES.get(finding.rule_code)
        return {"kind": "settings", "path": path} if path else None
    found = SOURCES.get(finding.subject_type)
    if found is None:
        return None
    kind, template = found
    entry = str((finding.details or {}).get("entry", ""))
    return {"kind": kind, "path": template.format(id=finding.subject_id, entry=entry)}


def finding_row(finding: ExceptionFinding) -> dict[str, Any]:
    rule = registry.get(finding.rule_code) if finding.rule_code in registry else None
    return {
        "id": str(finding.public_id),
        "rule": finding.rule_code,
        "rule_name": str(rule.name) if rule else finding.rule_code,
        "severity": finding.severity,
        "status": finding.status,
        "subject": {
            "type": finding.subject_type,
            "id": finding.subject_id,
            "label": finding.subject_label,
        },
        "amount": f"{finding.amount:.2f}" if finding.amount is not None else None,
        "details": finding.details,
        "explanation": rule.explain(finding.details or {}) if rule else "",
        "has_fix": bool(rule and rule.has_fix),
        "source": source_of(finding),
        "first_seen": finding.first_seen.isoformat(),
        "last_seen": finding.last_seen.isoformat(),
        "resolved_at": finding.resolved_at.isoformat() if finding.resolved_at else None,
        "ack_by": _person(finding.ack_by),
        "ack_at": finding.ack_at.isoformat() if finding.ack_at else None,
        "reason": finding.reason,
        "fix_entry": str(finding.fix_entry.public_id)
        if finding.fix_entry_id and finding.fix_entry
        else None,
    }


def _finding(public_id: Any) -> ExceptionFinding:
    found: ExceptionFinding | None = (
        ExceptionFinding.objects.select_related("ack_by", "fix_entry")
        .filter(public_id=public_id)
        .first()
    )
    if found is None:
        raise NotFound
    return found


def _history(finding: ExceptionFinding) -> list[dict[str, Any]]:
    events = AuditEvent.objects.filter(
        organisation=finding.organisation,
        object_type=ExceptionFinding._meta.label,
        object_id=str(finding.public_id),
    ).order_by("created_at", "id")[:200]
    return [
        {
            "action": e.action.rsplit(".", 1)[-1],
            "at": e.created_at.isoformat(),
            "by": e.actor_label,
            "reason": (e.meta or {}).get("reason", ""),
            "changes": e.changes,
        }
        for e in events
    ]


_SEVERITY_RANK = Case(
    When(severity=Severity.CRITICAL, then=Value(0)),
    When(severity=Severity.WARNING, then=Value(1)),
    default=Value(2),
    output_field=IntegerField(),
)


class SummaryView(APIView):
    @requires_permission(VIEW)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_summary", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        return Response(summary(_org()))


class FindingListView(APIView):
    @requires_permission(VIEW)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_findings", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        params = request.query_params
        statuses = [s for s in params.getlist("status") if s in FindingStatus.values]
        severities = [s for s in params.getlist("severity") if s in Severity.values]
        rules = params.getlist("rule")
        rows = ExceptionFinding.objects.select_related("ack_by", "fix_entry").filter(
            status__in=statuses or list(ACTIVE_STATUSES)
        )
        if severities:
            rows = rows.filter(severity__in=severities)
        if rules:
            rows = rows.filter(rule_code__in=rules)
        text = (params.get("q") or "").strip()
        if text:
            codes = [r.code for r in registry if text.lower() in str(r.name).lower()]
            rows = rows.filter(
                Q(subject_label__icontains=text)
                | Q(rule_code__icontains=text)
                | Q(rule_code__in=codes)
            )
        rows = rows.annotate(rank=_SEVERITY_RANK).order_by("rank", "rule_code", "-amount", "pk")
        found = [finding_row(f) for f in rows[:MAX_FINDINGS]]
        return Response({"count": len(found), "findings": found})


class FindingDetailView(APIView):
    queryset = ExceptionFinding._base_manager.none()

    @requires_permission(VIEW)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_finding", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        finding = _finding(public_id)
        return Response({**finding_row(finding), "history": _history(finding)})


class ReasonSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class _TransitionView(APIView):
    queryset = ExceptionFinding._base_manager.none()

    def move(self, finding: ExceptionFinding, user: Any, reason: str) -> ExceptionFinding:
        raise NotImplementedError

    def _post(self, request: Request, public_id: Any) -> Response:
        finding = _finding(public_id)
        payload = ReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            done = self.move(finding, request.user, payload.validated_data.get("reason", ""))
        except ValidationError as error:
            return _refused(error)
        return Response(finding_row(_finding(done.public_id)))


class AcknowledgeView(_TransitionView):
    def move(self, finding: ExceptionFinding, user: Any, reason: str) -> ExceptionFinding:
        return workflow.acknowledge(finding, user, reason)

    @requires_permission(MANAGE)
    @requires_feature(FEATURE)
    @extend_schema(
        operation_id="assurance_acknowledge", request=ReasonSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self._post(request, public_id)


class FalsePositiveView(_TransitionView):
    def move(self, finding: ExceptionFinding, user: Any, reason: str) -> ExceptionFinding:
        return workflow.mark_false_positive(finding, user, reason)

    @requires_permission(MANAGE)
    @requires_feature(FEATURE)
    @extend_schema(
        operation_id="assurance_false_positive", request=ReasonSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self._post(request, public_id)


class ReopenView(_TransitionView):
    def move(self, finding: ExceptionFinding, user: Any, reason: str) -> ExceptionFinding:
        return workflow.reopen(finding, user)

    @requires_permission(MANAGE)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_reopen", responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        return self._post(request, public_id)


class FixLineSerializer(serializers.Serializer[Any]):
    account = serializers.CharField()
    debit = serializers.CharField(required=False, allow_blank=True)
    credit = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=500)


class FixSerializer(serializers.Serializer[Any]):
    lines = FixLineSerializer(many=True, required=False)
    date = serializers.DateField(required=False)
    narration = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class FixView(APIView):
    queryset = ExceptionFinding._base_manager.none()

    @requires_permission(VIEW)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_fix", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        finding = _finding(public_id)
        proposal = fixes.propose(finding) if finding.is_active else None
        return Response({"fix": proposal.as_dict() if proposal else None})

    @requires_permission(MANAGE)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_fix_draft", request=FixSerializer, responses={201: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        finding = _finding(public_id)
        payload = FixSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            draft = fixes.create_fix_draft(
                finding,
                request.user,
                lines=[dict(line) for line in data["lines"]] if "lines" in data else None,
                date=data.get("date"),
                narration=data.get("narration"),
            )
        except ValidationError as error:
            return _refused(error)
        return Response(
            {
                "draft": {"id": str(draft.public_id), "status": draft.status},
                "finding": finding_row(_finding(public_id)),
            },
            status=status.HTTP_201_CREATED,
        )


class RunView(APIView):
    @requires_permission(MANAGE)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_run", responses={202: dict})
    def post(self, request: Request, org: Any) -> Response:
        job = start_run(_org(), user=request.user)
        return Response({"job": str(job.public_id)}, status=status.HTTP_202_ACCEPTED)


class RunListView(APIView):
    @requires_permission(VIEW)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_runs", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        runs = ExceptionRun.objects.order_by("-started_at", "-pk")[:20]
        return Response(
            {
                "runs": [
                    {
                        "id": str(r.public_id),
                        "trigger": r.trigger,
                        "status": r.status,
                        "started_at": r.started_at.isoformat(),
                        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                        "counts": r.counts,
                        "rules": r.rules,
                    }
                    for r in runs
                ]
            }
        )


def _rule_row(organisation: Any, code: str) -> dict[str, Any]:
    rule = registry.get(code)
    found = settings_for(organisation, rule)
    return {
        **rule.schema(),
        "enabled": found.enabled,
        "severity": found.severity,
        "values": json_params(found.params),
    }


class RuleListView(APIView):
    @requires_permission(VIEW)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_rules", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        organisation = _org()
        return Response({"rules": [_rule_row(organisation, r.code) for r in registry]})


class RuleSettingsSerializer(serializers.Serializer[Any]):
    enabled = serializers.BooleanField(required=False)
    severity = serializers.ChoiceField(choices=Severity.values, required=False)
    params = serializers.DictField(required=False)


class RuleDetailView(APIView):
    @requires_permission(VIEW)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_rule", responses={200: dict})
    def get(self, request: Request, org: Any, code: str) -> Response:
        if code not in registry:
            raise NotFound
        return Response(_rule_row(_org(), code))

    @requires_permission(MANAGE)
    @requires_feature(FEATURE)
    @extend_schema(
        operation_id="assurance_rule_update", request=RuleSettingsSerializer, responses={200: dict}
    )
    def patch(self, request: Request, org: Any, code: str) -> Response:
        if code not in registry:
            raise NotFound
        organisation = _org()
        rule = registry.get(code)
        payload = RuleSettingsSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        config = ExceptionRuleConfig.objects.filter(rule_code=code).first() or ExceptionRuleConfig(
            organisation=organisation, rule_code=code
        )
        if "params" in data:
            try:
                merged = {**(config.params or {}), **data["params"]}
                config.params = json_params(
                    {k: v for k, v in clean_params(rule, merged).items() if k in merged}
                )
            except ValidationError as error:
                return _refused(error)
        if "enabled" in data:
            config.enabled = data["enabled"]
        if "severity" in data:
            config.severity = data["severity"]
        if config.pk is None and getattr(request.user, "is_authenticated", False):
            config.created_by = request.user
        config.save()
        return Response(_rule_row(organisation, code))


class HeatmapView(APIView):
    @requires_permission(VIEW)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="assurance_heatmap", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        from numo9.accounts.models import User

        organisation = _org()
        try:
            days = int(request.query_params.get("days") or 365)
        except ValueError:
            days = 365
        person = None
        wanted = request.query_params.get("user")
        if wanted:  # the events are this organisation's only, whoever is asked about
            person = User.objects.filter(public_id=wanted).first() if _is_uuid(wanted) else None
            person = person or User(pk=-1)  # nobody: nothing to count
        return Response(heatmap(organisation, days=days, user=person))


def _is_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
