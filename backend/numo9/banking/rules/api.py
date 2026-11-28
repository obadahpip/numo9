"""Bank rules API (F-04-T09), under ``/api/v1/o/<org>/`` like the rest of banking.

- ``GET bank-rules`` ``?type=spend|receive|transfer&status=active|inactive|all&search=`` — the
  rules in priority order (type, then priority) with their conditions, allocations, scope,
  counters (``applied_count``, ``last_applied_at``) and ``warnings`` (``archived_account`` …:
  the rule is disabled until fixed).
- ``POST bank-rules`` ``{type, name, match_mode, conditions: [{field, operator, value,
  value_to}], allocations: [{account, tax_code, description, fixed_amount | percent}],
  scope_accounts: [ids], contact_strategy, contact, reference_template, transfer_account,
  auto_apply, active}`` — 201; the rule takes the next priority of its type.
- ``GET`` / ``PATCH`` / ``DELETE bank-rules/<id>`` — ``PATCH`` takes any of the fields (the list's
  on/off toggle sends ``{active}``); the type is fixed. ``DELETE`` soft-deletes and closes the gap.
- ``POST bank-rules/reorder`` ``{type, order: [ids]}`` — renumbers the type's rules 1…n
  atomically (every rule exactly once, else 400 ``banking.rule.reorder_mismatch``).
- ``POST bank-rules/preview`` ``{rule: {…definition…}, id?, days?}`` — the history preview
  (F-04-T08) of a saved rule (``id``) or of the builder's unsaved form; nothing is written.
- ``POST bank-rules/apply`` ``{bank_account?}`` — runs the rules on the Uncoded lines (F-04-T07).
- ``POST bank-rules/lines/<line id>/confirm`` — posts the draft a rule left on the line.

Errors: 400 ``{code, detail, field}`` (``field`` = the part at fault, e.g. ``conditions.0``).
Permissions: ``accounting.banking.view`` to read and preview, ``accounting.banking.rules`` to
change rules, ``accounting.banking.transact`` to apply, confirm and revert codings. Features
``accounting.banking.read`` / ``.write`` (banking is never gated, gap-27).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.contacts.models import Contact
from numo9.ledger.models import Account, LedgerError
from numo9.orgsettings.locks import acting_user
from numo9.rbac.drf import requires_permission
from numo9.tax.models import TaxError

from ..models import (
    BankAccount,
    BankRule,
    BankRuleType,
    ConditionField,
    ConditionOperator,
    ContactStrategy,
    MatchMode,
    StatementLine,
)
from ..permissions import BANKING_RULES, BANKING_TRANSACT, BANKING_VIEW
from .apply import apply_rules, confirm_line, uncoded_lines
from .conditions import Condition
from .engine import RuleSpec, rule_spec, rule_warnings, rules_queryset
from .preview import DEFAULT_DAYS, MAX_ROWS, preview_rule
from .service import (
    AllocationInput,
    RuleDefinition,
    RuleInvalid,
    delete_rule,
    next_priority,
    reorder,
    save_rule,
    validate_definition,
)

READ = "accounting.banking.read"
WRITE = "accounting.banking.write"


def refused(error: DjangoValidationError | LedgerError) -> Response:
    return Response(
        {
            "code": getattr(error, "code", None) or "invalid",
            "detail": " ".join(str(m) for m in error.messages),
            "field": getattr(error, "where", ""),
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _money(value: Any) -> str | None:
    return None if value is None else f"{value:.2f}"


def _named(item: Any, name: str) -> dict[str, Any] | None:
    return None if item is None else {"id": str(item.public_id), "name": name}


def rule_row(rule: BankRule) -> dict[str, Any]:
    return {
        "id": str(rule.public_id),
        "type": rule.type,
        "name": rule.name,
        "match_mode": rule.match_mode,
        "priority": rule.priority,
        "active": rule.active,
        "auto_apply": rule.auto_apply,
        "contact_strategy": rule.contact_strategy,
        "contact": _named(rule.contact, rule.contact.display_name) if rule.contact else None,
        "reference_template": rule.reference_template,
        "transfer_account": _named(rule.transfer_account, rule.transfer_account.display_name)
        if rule.transfer_account
        else None,
        "scope_accounts": [
            {"id": str(a.public_id), "name": a.display_name} for a in rule.scope_accounts.all()
        ],
        "conditions": [
            {
                "field": c.field,
                "operator": c.operator,
                "value": c.value,
                "value_to": c.value_to,
            }
            for c in rule.conditions.all()
        ],
        "allocations": [
            {
                "account": {
                    "id": str(a.account.public_id),
                    "code": a.account.code,
                    "name": a.account.name,
                },
                "tax_code": a.tax_code,
                "description": a.description,
                "fixed_amount": _money(a.fixed_amount),
                "percent": None if a.percent is None else f"{a.percent.normalize():f}",
            }
            for a in rule.allocations.all()
        ],
        "applied_count": rule.applied_count,
        "last_applied_at": rule.last_applied_at,
        "warnings": rule_warnings(rule),
    }


def _rule(public_id: Any) -> BankRule:
    found: BankRule | None = rules_queryset().filter(public_id=public_id).first()
    if found is None:
        raise NotFound(_("That bank rule doesn't exist."))
    return found


class ConditionSerializer(serializers.Serializer[Any]):
    field = serializers.ChoiceField(choices=ConditionField.choices)
    operator = serializers.ChoiceField(choices=ConditionOperator.choices)
    value = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    value_to = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")

    def to_internal_value(self, data: Any) -> Any:
        # Patterns keep their spaces; DRF trims CharField values by default.
        values = super().to_internal_value(data)
        if isinstance(data, dict) and isinstance(data.get("value"), str):
            values["value"] = data["value"]
        return values


class AllocationSerializer(serializers.Serializer[Any]):
    account = serializers.UUIDField()
    tax_code = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )
    fixed_amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, allow_null=True, default=None
    )
    percent = serializers.DecimalField(
        max_digits=7, decimal_places=4, required=False, allow_null=True, default=None
    )


class RuleInputSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=BankRuleType.choices)
    name = serializers.CharField(max_length=120)
    match_mode = serializers.ChoiceField(choices=MatchMode.choices, default=MatchMode.ALL)
    conditions = ConditionSerializer(many=True)
    allocations = AllocationSerializer(many=True, required=False, default=list)
    scope_accounts = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    contact_strategy = serializers.ChoiceField(
        choices=ContactStrategy.choices, default=ContactStrategy.NONE
    )
    contact = serializers.UUIDField(required=False, allow_null=True, default=None)
    reference_template = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    transfer_account = serializers.UUIDField(required=False, allow_null=True, default=None)
    auto_apply = serializers.BooleanField(required=False, default=False)
    active = serializers.BooleanField(required=False, default=True)


def _bank(public_id: Any, where: str) -> BankAccount:
    found: BankAccount | None = BankAccount.objects.filter(
        public_id=public_id, deleted_at__isnull=True
    ).first()
    if found is None:
        raise serializers.ValidationError({where: [_("That bank account doesn't exist.")]})
    return found


def definition_from(data: dict[str, Any]) -> RuleDefinition:
    """Resolve the ids of validated input into a ``RuleDefinition``."""
    ids = {a["account"] for a in data.get("allocations") or []}
    accounts = {a.public_id: a for a in Account.objects.filter(public_id__in=ids)}
    missing = {
        str(n): {"account": [_("That account doesn't exist.")]}
        for n, a in enumerate(data.get("allocations") or [])
        if a["account"] not in accounts
    }
    if missing:
        raise serializers.ValidationError({"allocations": missing})
    contact = None
    if data.get("contact"):
        contact = Contact.objects.filter(public_id=data["contact"], deleted_at__isnull=True).first()
        if contact is None:
            raise serializers.ValidationError({"contact": [_("That contact doesn't exist.")]})
    return RuleDefinition(
        type=data["type"],
        name=data["name"],
        match_mode=data.get("match_mode") or MatchMode.ALL,
        conditions=[
            Condition(c["field"], c["operator"], c.get("value") or "", c.get("value_to") or "")
            for c in data["conditions"]
        ],
        allocations=[
            AllocationInput(
                account=accounts[a["account"]],
                fixed_amount=a.get("fixed_amount"),
                percent=a.get("percent"),
                tax_code=a.get("tax_code") or "",
                description=a.get("description") or "",
            )
            for a in data.get("allocations") or []
        ],
        scope_accounts=[_bank(i, "scope_accounts") for i in data.get("scope_accounts") or []],
        contact_strategy=data.get("contact_strategy") or ContactStrategy.NONE,
        contact=contact,
        reference_template=data.get("reference_template") or "",
        transfer_account=_bank(data["transfer_account"], "transfer_account")
        if data.get("transfer_account")
        else None,
        auto_apply=bool(data.get("auto_apply")),
        active=data.get("active", True),
    )


def input_of(rule: BankRule) -> dict[str, Any]:
    """A saved rule as API input (what a partial PATCH is merged into)."""
    return {
        "type": rule.type,
        "name": rule.name,
        "match_mode": rule.match_mode,
        "conditions": [
            {"field": c.field, "operator": c.operator, "value": c.value, "value_to": c.value_to}
            for c in rule.conditions.all()
        ],
        "allocations": [
            {
                "account": a.account.public_id,
                "tax_code": a.tax_code,
                "description": a.description,
                "fixed_amount": a.fixed_amount,
                "percent": a.percent,
            }
            for a in rule.allocations.all()
        ],
        "scope_accounts": [a.public_id for a in rule.scope_accounts.all()],
        "contact_strategy": rule.contact_strategy,
        "contact": rule.contact.public_id if rule.contact else None,
        "reference_template": rule.reference_template,
        "transfer_account": rule.transfer_account.public_id if rule.transfer_account else None,
        "auto_apply": rule.auto_apply,
        "active": rule.active,
    }


class BankRuleListView(APIView):
    queryset = BankRule._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_rules_list", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        rules = rules_queryset()
        params = request.query_params
        if params.get("type") in BankRuleType.values:
            rules = rules.filter(type=params["type"])
        wanted = params.get("status", "all")
        if wanted == "active":
            rules = rules.filter(active=True)
        elif wanted == "inactive":
            rules = rules.filter(active=False)
        search = (params.get("search") or "").strip()
        if search:
            rules = rules.filter(
                Q(name__icontains=search) | Q(conditions__value__icontains=search)
            ).distinct()
        return Response({"results": [rule_row(r) for r in rules.order_by("type", "priority")]})

    @requires_permission(BANKING_RULES.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_rules_create", request=RuleInputSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        data = RuleInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            rule = save_rule(definition_from(dict(data.validated_data)), user=acting_user())
        except RuleInvalid as error:
            return refused(error)
        return Response(rule_row(_rule(rule.public_id)), status=status.HTTP_201_CREATED)


class BankRuleDetailView(APIView):
    queryset = BankRule._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_rules_read", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(rule_row(_rule(public_id)))

    @requires_permission(BANKING_RULES.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_rules_update", request=RuleInputSerializer, responses={200: dict}
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        rule = _rule(public_id)
        merged = {**input_of(rule), **(request.data if isinstance(request.data, dict) else {})}
        data = RuleInputSerializer(data=merged)
        data.is_valid(raise_exception=True)
        try:
            save_rule(definition_from(dict(data.validated_data)), rule, user=acting_user())
        except RuleInvalid as error:
            return refused(error)
        return Response(rule_row(_rule(public_id)))

    @requires_permission(BANKING_RULES.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bank_rules_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        delete_rule(_rule(public_id), user=acting_user())
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReorderSerializer(serializers.Serializer[Any]):
    type = serializers.ChoiceField(choices=BankRuleType.choices)
    order = serializers.ListField(child=serializers.UUIDField(), max_length=1000)


class BankRuleReorderView(APIView):
    queryset = BankRule._base_manager.none()

    @requires_permission(BANKING_RULES.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_rules_reorder", request=ReorderSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        data = ReorderSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            reorder(data.validated_data["type"], data.validated_data["order"], user=acting_user())
        except RuleInvalid as error:
            return refused(error)
        rules = rules_queryset().filter(type=data.validated_data["type"]).order_by("priority")
        return Response({"results": [rule_row(r) for r in rules]})


class PreviewSerializer(serializers.Serializer[Any]):
    rule = RuleInputSerializer()
    id = serializers.UUIDField(required=False, allow_null=True, default=None)
    days = serializers.IntegerField(required=False, min_value=1, max_value=730, default=None)


def _line_row(line: StatementLine) -> dict[str, Any]:
    return {
        "id": str(line.public_id),
        "date": line.date,
        "amount": _money(line.amount),
        "payee": line.payee,
        "description": line.description,
        "reference": line.reference,
        "bank_account": {
            "id": str(line.bank_account.public_id),
            "name": line.bank_account.display_name,
        },
    }


def _brief(spec: RuleSpec | None) -> dict[str, Any] | None:
    return None if spec is None else {"id": spec.public_id or None, "name": spec.name}


class BankRulePreviewView(APIView):
    queryset = BankRule._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="bank_rules_preview", request=PreviewSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        data = PreviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        saved = _rule(values["id"]) if values.get("id") else None
        try:
            definition = definition_from(dict(values["rule"]))
            validate_definition(definition)
        except RuleInvalid as error:
            return refused(error)
        if saved is not None and saved.type == definition.type and saved.priority:
            priority = saved.priority
        else:
            priority = next_priority(definition.type)
        candidate = RuleSpec(
            name=definition.name,
            type=definition.type,
            priority=priority,
            match_mode=definition.match_mode,
            conditions=tuple(definition.conditions),
            scope=frozenset(a.pk for a in definition.scope_accounts),
            id=saved.pk if saved else None,
            public_id=str(saved.public_id) if saved else "",
        )
        result = preview_rule(
            candidate, days=values.get("days") or DEFAULT_DAYS, user=acting_user()
        )
        return Response(
            {
                "since": result.since,
                "days": result.days,
                "applies": result.applies,
                "shadowed": result.shadowed,
                "truncated": len(result.rows) > MAX_ROWS,
                "rows": [
                    {
                        "line": _line_row(row.line),
                        "outcome": row.outcome,
                        "shadowed_by": _brief(row.shadowed_by),
                        "also_matches": [_brief(r) for r in row.also_matches],
                    }
                    for row in result.rows[:MAX_ROWS]
                ],
            }
        )


class ApplySerializer(serializers.Serializer[Any]):
    bank_account = serializers.UUIDField(required=False, allow_null=True, default=None)


class BankRuleApplyView(APIView):
    queryset = BankRule._base_manager.none()

    @requires_permission(BANKING_TRANSACT.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bank_rules_apply", request=ApplySerializer, responses={200: dict})
    def post(self, request: Request, org: Any) -> Response:
        data = ApplySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        bank = data.validated_data.get("bank_account")
        lines = uncoded_lines(_bank(bank, "bank_account") if bank else None)
        result = apply_rules(lines, user=acting_user())
        return Response(
            {
                "applied": [
                    {
                        "line": str(line.public_id),
                        "rule": {"id": str(rule.public_id), "name": rule.name},
                        "transaction": str(txn.public_id),
                        "status": txn.status,
                    }
                    for line, rule, txn in result.applied
                ],
                "skipped": len(result.skipped),
            }
        )


def statement_line(public_id: Any) -> StatementLine:
    found: StatementLine | None = (
        StatementLine.objects.select_related("bank_account", "organisation")
        .filter(public_id=public_id)
        .first()
    )
    if found is None:
        raise NotFound(_("That statement line doesn't exist."))
    return found


class StatementLineConfirmView(APIView):
    queryset = StatementLine._base_manager.none()

    @requires_permission(BANKING_TRANSACT.key)
    @requires_feature(WRITE)
    @extend_schema(operation_id="bank_rules_line_confirm", request=None, responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        line = statement_line(public_id)
        try:
            txn = confirm_line(line, user=acting_user())
        except (DjangoValidationError, LedgerError, TaxError) as error:
            return refused(error)
        return Response({"line": str(line.public_id), "transaction": str(txn.public_id)})


__all__ = [
    "BankRuleApplyView",
    "BankRuleDetailView",
    "BankRuleListView",
    "BankRulePreviewView",
    "BankRuleReorderView",
    "StatementLineConfirmView",
    "rule_spec",
]
