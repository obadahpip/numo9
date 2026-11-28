"""Saving, deleting and reordering bank rules (F-04-T09).

``save_rule(definition, rule=None)`` validates a whole rule — conditions (F-04-T04: operator fits
the field, values present, regex safe), allocations (F-04-T03: percentages total 100 %; ledger
accounts not archived; tax codes known on the rule's side: purchase codes for spend, sales codes
for receive), a transfer's other bank account (required, active; transfers have no allocation
lines), a fixed contact — then writes the rule, its conditions and allocations in one
transaction. A new rule takes the **next priority** of its type; the type is fixed once created.

**Audit** (F-04-T16): the rule's own fields are audited by ``AuditedModel``
(``banking.bankrule.created`` / ``.updated`` / ``.deleted``); a change of its conditions or
allocations writes ``banking.bankrule.conditions_changed`` with both versions; a reorder writes
``banking.rule.reordered`` with each moved rule's old and new priority. Applying, confirming and
reverting are audited by the apply service.

``delete_rule`` soft-deletes it, gives its priority up and closes the gap. ``reorder(type, ids)``
renumbers every rule of the type 1…n in the given order **atomically**: the list must hold each
of the type's rules exactly once, otherwise nothing changes (``banking.rule.reorder_mismatch``);
the deferred unique constraint is checked at commit, so no intermediate state can clash.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.audit.service import record as audit
from numo9.tax.models import TaxCode, TaxSide
from numo9.tenancy.context import current_org

from ..models import (
    BankAccount,
    BankRule,
    BankRuleAllocation,
    BankRuleCondition,
    BankRuleType,
    ContactStrategy,
)
from .allocation import Share, validate_allocations
from .conditions import Condition, validate_condition


class RuleInvalid(ValidationError):
    """A refused rule, with the part of the definition at fault (``conditions.0``…)."""

    def __init__(self, error: ValidationError, where: str = "") -> None:
        super().__init__(error.messages[0], code=error.code)
        self.where = where


@dataclass
class AllocationInput:
    account: Any
    fixed_amount: Decimal | None = None
    percent: Decimal | None = None
    tax_code: str = ""
    description: str = ""


@dataclass
class RuleDefinition:
    """A rule as the API or the builder gives it (model instances already resolved)."""

    type: str
    name: str
    match_mode: str = "all"
    conditions: Sequence[Condition] = ()
    allocations: Sequence[AllocationInput] = ()
    scope_accounts: Sequence[BankAccount] = ()
    contact_strategy: str = ContactStrategy.NONE
    contact: Any = None
    reference_template: str = ""
    transfer_account: BankAccount | None = None
    auto_apply: bool = False
    active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


def _side(rule_type: str) -> str:
    return TaxSide.PURCHASE if rule_type == BankRuleType.SPEND else TaxSide.SALES


def validate_conditions(definition: RuleDefinition) -> None:
    """The conditions' checks only — what the history preview needs (F-04-T13: the builder
    previews before the allocations are complete)."""
    if not definition.conditions:
        raise RuleInvalid(
            ValidationError(
                _("Add at least one condition."), code="banking.rule.conditions_required"
            ),
            "conditions",
        )
    for number, condition in enumerate(definition.conditions):
        try:
            validate_condition(condition)
        except ValidationError as error:
            raise RuleInvalid(error, f"conditions.{number}") from error


def validate_definition(definition: RuleDefinition) -> None:
    """Every check of the module docstring; raises ``RuleInvalid``."""
    if not " ".join(definition.name.split()):
        raise RuleInvalid(
            ValidationError(_("Give the rule a name."), code="banking.rule.name_required"), "name"
        )
    validate_conditions(definition)
    if definition.contact_strategy == ContactStrategy.FIXED and definition.contact is None:
        raise RuleInvalid(
            ValidationError(_("Choose the contact to set."), code="banking.rule.contact_required"),
            "contact",
        )
    if definition.type == BankRuleType.TRANSFER:
        other = definition.transfer_account
        if other is None or other.archived_at is not None or other.deleted_at is not None:
            raise RuleInvalid(
                ValidationError(
                    _("Choose the other bank account of the transfer."),
                    code="banking.rule.transfer_account_required",
                ),
                "transfer_account",
            )
        if other in list(definition.scope_accounts) and len(definition.scope_accounts) == 1:
            raise RuleInvalid(
                ValidationError(
                    _("A transfer can't go to the account it comes from."),
                    code="banking.rule.transfer_same_account",
                ),
                "transfer_account",
            )
        return
    try:
        validate_allocations(
            Share(fixed_amount=a.fixed_amount, percent=a.percent) for a in definition.allocations
        )
    except ValidationError as error:
        raise RuleInvalid(error, "allocations") from error
    side = _side(definition.type)
    for number, allocation in enumerate(definition.allocations):
        if allocation.account.is_archived:
            raise RuleInvalid(
                ValidationError(
                    _("%(account)s is archived: choose another account."),
                    code="banking.rule.account_archived",
                    params={"account": str(allocation.account)},
                ),
                f"allocations.{number}.account",
            )
        code = allocation.tax_code
        if code and not TaxCode.objects.filter(code=code, side=side).exists():
            raise RuleInvalid(
                ValidationError(
                    _("The tax code %(code)s doesn't apply to this kind of rule."),
                    code="banking.rule.tax_code_side",
                    params={"code": code},
                ),
                f"allocations.{number}.tax_code",
            )


def next_priority(rule_type: str) -> int:
    top = BankRule.objects.filter(type=rule_type, deleted_at__isnull=True).aggregate(
        top=Max("priority")
    )["top"]
    return int(top or 0) + 1


def save_rule(
    definition: RuleDefinition, rule: BankRule | None = None, *, user: Any = None
) -> BankRule:
    """Create or replace a rule (conditions and allocations rewritten) — all or nothing."""
    if rule is not None and rule.type != definition.type:
        raise RuleInvalid(
            ValidationError(
                _("A rule's type can't change: create a new rule instead."),
                code="banking.rule.type_fixed",
            ),
            "type",
        )
    validate_definition(definition)
    with transaction.atomic():
        if rule is None:
            rule = BankRule(
                organisation=current_org(),
                type=definition.type,
                priority=next_priority(definition.type),
            )
            if getattr(user, "is_authenticated", False):
                rule.created_by = user
        rule.name = " ".join(definition.name.split())[:120]
        rule.match_mode = definition.match_mode
        rule.contact_strategy = definition.contact_strategy
        rule.contact = definition.contact if definition.contact_strategy == "fixed" else None
        rule.reference_template = definition.reference_template.strip()[:255]
        is_transfer = definition.type == BankRuleType.TRANSFER
        rule.transfer_account = definition.transfer_account if is_transfer else None
        rule.auto_apply = definition.auto_apply
        rule.active = definition.active
        adding = rule.pk is None
        before = None if adding else _parts(rule)
        rule.save()
        rule.scope_accounts.set(list(definition.scope_accounts))
        rule.conditions.all().delete()
        BankRuleCondition.objects.bulk_create(
            BankRuleCondition(
                organisation=rule.organisation,
                rule=rule,
                order=number,
                field=c.field,
                operator=c.operator,
                value=c.value.strip() if c.operator != "regex" else c.value,
                value_to=c.value_to.strip(),
            )
            for number, c in enumerate(definition.conditions)
        )
        rule.allocations.all().delete()
        if not is_transfer:
            BankRuleAllocation.objects.bulk_create(
                BankRuleAllocation(
                    organisation=rule.organisation,
                    rule=rule,
                    order=number,
                    account=a.account,
                    tax_code=a.tax_code,
                    description=a.description.strip()[:500],
                    fixed_amount=a.fixed_amount,
                    percent=a.percent,
                )
                for number, a in enumerate(definition.allocations)
            )
        after = _parts(rule)
        if before is not None and before != after:
            audit(
                "banking.bankrule.conditions_changed",
                obj=rule,
                changes={
                    key: [before[key], after[key]] for key in after if before[key] != after[key]
                },
                actor=user,
            )
        return rule


def _parts(rule: BankRule) -> dict[str, Any]:
    """The rule's conditions, allocations and scope in words, for the audit trail."""
    return {
        "conditions": [
            " ".join(filter(None, [c.field, c.operator, c.value, c.value_to]))
            for c in rule.conditions.order_by("order", "pk")
        ],
        "allocations": [
            f"{a.account.code} {a.percent.normalize():f}% {a.tax_code}".strip()
            if a.percent is not None
            else f"{a.account.code} {a.fixed_amount} {a.tax_code}".strip()
            for a in rule.allocations.select_related("account").order_by("order", "pk")
        ],
        "scope_accounts": sorted(a.display_name for a in rule.scope_accounts.all()),
    }


def _compact(rule_type: str) -> None:
    rules = list(
        BankRule.objects.select_for_update()
        .filter(type=rule_type, deleted_at__isnull=True)
        .order_by("priority", "pk")
    )
    for number, item in enumerate(rules, start=1):
        item.priority = number
    BankRule.objects.bulk_update(rules, ["priority"])


def delete_rule(rule: BankRule, *, user: Any = None) -> None:
    """Soft-delete: the rule gives its priority up and the others close the gap."""
    with transaction.atomic():
        locked = BankRule.objects.select_for_update().get(pk=rule.pk)
        locked.priority = None
        locked.deleted_at = timezone.now()
        locked.save(update_fields=["priority", "deleted_at", "updated_at"])
        _compact(locked.type)


def reorder(rule_type: str, ids: Sequence[Any], *, user: Any = None) -> list[BankRule]:
    """Renumber the type's rules 1…n in the order of ``ids`` (public ids) — atomically."""
    with transaction.atomic():
        rules = {
            str(r.public_id): r
            for r in BankRule.objects.select_for_update().filter(
                type=rule_type, deleted_at__isnull=True
            )
        }
        wanted = [str(i) for i in ids]
        if len(wanted) != len(set(wanted)) or set(wanted) != set(rules):
            raise RuleInvalid(
                ValidationError(
                    _("The new order must list every rule of this type exactly once."),
                    code="banking.rule.reorder_mismatch",
                ),
                "order",
            )
        before = {key: rule.priority for key, rule in rules.items()}
        ordered = [rules[key] for key in wanted]
        for number, item in enumerate(ordered, start=1):
            item.priority = number
        BankRule.objects.bulk_update(ordered, ["priority"])
        moved = {
            key: [before[key], rules[key].priority]
            for key in wanted
            if before[key] != rules[key].priority
        }
        if moved:
            audit(
                "banking.rule.reordered",
                object_type="banking.BankRule",
                object_label=str(BankRuleType(rule_type).label),
                meta={"type": rule_type, "priorities": moved},
                actor=user,
            )
        return ordered
