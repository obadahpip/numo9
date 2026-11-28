"""Priority engine of the bank rules (F-04-T05): ordered evaluation, the first match wins.

``choose(rules, line)`` evaluates the rules that can code the line — a **spend** rule a line of
money out (negative amount), a **receive** rule money in (positive), a **transfer** rule either;
a rule scoped to some bank accounts only their lines — in priority order (1 first; between types
with the same number, spend / receive before transfer) and returns an ``Outcome``: the
``winner`` (the first rule whose conditions match) and the ``shadowed`` rules — the later rules
that match the line too and lose to the winner (the preview shows them, F-04-T08).

``load_rules()`` reads the organisation's **active** rules (deleted ones excluded) as
``RuleSpec``s. A rule that points at an archived ledger account or bank account is **disabled
with a warning** (``rule_warnings``): it is left out of evaluation until the account is restored
or the rule edited.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ..models import BankRule, BankRuleType
from .conditions import Condition, LineFacts, matches_all

TYPE_ORDER: dict[str, int] = {"spend": 0, "receive": 0, "transfer": 1}


@dataclass(frozen=True)
class RuleSpec:
    """A rule as the engine reads it (from the database or from the builder's unsaved form)."""

    name: str
    type: str
    priority: int
    conditions: tuple[Condition, ...]
    match_mode: str = "all"
    scope: frozenset[int] = frozenset()
    id: int | None = None
    public_id: str = ""
    model: Any = field(default=None, compare=False, repr=False)

    def can_code(self, line: LineFacts) -> bool:
        amount = Decimal(line.amount)
        if not amount:
            return False
        if self.type == BankRuleType.SPEND and amount > 0:
            return False
        if self.type == BankRuleType.RECEIVE and amount < 0:
            return False
        return not self.scope or line.bank_account_id in self.scope

    def matches(self, line: LineFacts) -> bool:
        return self.can_code(line) and matches_all(
            list(self.conditions), line, mode=self.match_mode
        )


@dataclass(frozen=True)
class Outcome:
    winner: RuleSpec | None
    shadowed: tuple[RuleSpec, ...] = ()


def ordered(rules: Iterable[RuleSpec]) -> list[RuleSpec]:
    return sorted(rules, key=lambda r: (r.priority, TYPE_ORDER.get(r.type, 9), r.id or 0, r.name))


def choose(rules: Sequence[RuleSpec], line: LineFacts) -> Outcome:
    """The first matching rule in priority order, and the matching rules it shadows."""
    found = [rule for rule in ordered(rules) if rule.matches(line)]
    if not found:
        return Outcome(None)
    return Outcome(found[0], tuple(found[1:]))


def rule_spec(rule: BankRule) -> RuleSpec:
    """The engine's view of a saved rule (conditions and scope read through prefetches)."""
    return RuleSpec(
        name=rule.name,
        type=rule.type,
        priority=rule.priority or 0,
        match_mode=rule.match_mode,
        conditions=tuple(
            Condition(c.field, c.operator, c.value, c.value_to) for c in rule.conditions.all()
        ),
        scope=frozenset(a.pk for a in rule.scope_accounts.all()),
        id=rule.pk,
        public_id=str(rule.public_id),
        model=rule,
    )


def rule_warnings(rule: BankRule) -> list[str]:
    """Why a rule is disabled: ``archived_account`` (an allocation's ledger account is archived)
    or ``archived_bank_account`` (its transfer account is archived or deleted)."""
    warnings: list[str] = []
    if any(a.account.is_archived for a in rule.allocations.all()):
        warnings.append("archived_account")
    other = rule.transfer_account
    if other is not None and (other.archived_at is not None or other.deleted_at is not None):
        warnings.append("archived_bank_account")
    return warnings


def rules_queryset() -> Any:
    return (
        BankRule.objects.filter(deleted_at__isnull=True)
        .select_related("contact", "transfer_account")
        .prefetch_related("conditions", "scope_accounts", "allocations__account")
    )


def load_rules(*, exclude: int | None = None) -> list[RuleSpec]:
    """The active rules of the current organisation that can run (not disabled)."""
    query = rules_queryset().filter(active=True, priority__isnull=False)
    if exclude is not None:
        query = query.exclude(pk=exclude)
    return ordered(rule_spec(rule) for rule in query if not rule_warnings(rule))
