"""Apply service of the bank rules (F-04-T07): code statement lines with the winning rule.

``apply_rules(lines)`` runs the priority engine (F-04-T05) on each line and codes it with the
winner (``code_line``):

- the line becomes a **spend** (money out) or a **receive** (money in) of its bank account
  (F-01), dated like the line: the rule's allocation lines split the amount (F-04-T06, tax per
  line, amounts tax inclusive); a **transfer** rule moves the money to or from its other bank
  account (no tax; refused when that is the line's own account,
  ``banking.rule.transfer_same_account``). The contact follows the rule's strategy and the
  reference its template (``{payee}``, ``{description}``, ``{reference}``, ``{date}``,
  ``{amount}``);
- a rule **without auto-apply** leaves a **draft** transaction for review: the line stays
  Uncoded with the draft and the rule linked; ``confirm_line`` posts the draft and the line
  becomes Coded;
- an **auto-apply** rule posts at once (one balanced journal, C-02): the line becomes Coded and
  is flagged ``auto_coded`` (it can be reverted, F-04-T15).

Rules **never touch** a line that is not Uncoded (Matched, Coded, Ignored), that already has a
transaction, or that is dated in a locked period (Bank or GL lock, A-05) — those are returned as
skipped with the reason. **Every application is logged**: the rule on the line
(``applied_rule``), a ``BankRuleApplication`` row, the audit event ``banking.rule.applied`` and the
rule's counters (``applied_count``, ``last_applied_at``).

**Revert** (F-04-T15): ``revert_line`` undoes a rule's coding — a posted transaction is voided
(its journal reversed on the same date, so the ledger nets to 0), a draft is discarded — and the
line goes back to Uncoded without the rule link; the application is marked reverted and the audit
event ``banking.rule.reverted`` is written. The rule that was reverted on a line is **not applied
to that line again** (``reverted_rules``), by apply and preview alike.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.audit.service import record as audit
from numo9.contacts.models import Contact
from numo9.ledger.models import LedgerError
from numo9.ledger.services import ACTING
from numo9.orgsettings.locks import check_lock
from numo9.orgsettings.models import LockModule
from numo9.tax.models import TaxError
from numo9.tenancy.context import org_context

from ..models import (
    BankRule,
    BankRuleApplication,
    BankRuleType,
    BankTransaction,
    BankTransactionKind,
    BankTransactionStatus,
    ContactStrategy,
    RuleApplicationMode,
    StatementLine,
    StatementLineStatus,
    TaxMode,
)
from ..transactions import (
    MoneyLine,
    MoneySpec,
    post_draft_transaction,
    record_bank_transaction,
    void_bank_transaction,
)
from .allocation import Share, allocate, money_spec
from .conditions import LineFacts
from .engine import RuleSpec, choose, load_rules

TOKENS = re.compile(r"\{(payee|description|reference|date|amount)\}")


@dataclass
class ApplyResult:
    applied: list[tuple[StatementLine, BankRule, BankTransaction]] = field(default_factory=list)
    skipped: list[tuple[StatementLine, str]] = field(default_factory=list)


def skip_reason(line: StatementLine, user: Any = None) -> str | None:
    """Why rules must leave this line alone, or None: ``status`` (not Uncoded — Matched lines
    included), ``coded`` (it already has a transaction), ``locked`` (locked period)."""
    if line.status != StatementLineStatus.UNCODED:
        return "status"
    if line.bank_transaction_id is not None:
        return "coded"
    if check_lock(line.organisation, LockModule.BANK, line.date, user) is not None:
        return "locked"
    return None


def render_reference(template: str, line: StatementLine) -> str:
    values = {
        "payee": line.payee,
        "description": line.description,
        "reference": line.reference,
        "date": f"{line.date:%Y-%m-%d}",
        "amount": f"{abs(line.amount):.2f}",
    }
    text = TOKENS.sub(lambda m: values[m.group(1)], template or "")
    return " ".join(text.split())[:255]


def _contact(rule: BankRule, line: StatementLine) -> Contact | None:
    if rule.contact_strategy == ContactStrategy.FIXED:
        return rule.contact
    if rule.contact_strategy == ContactStrategy.MATCH_PAYEE and line.payee.strip():
        found: Contact | None = Contact.objects.filter(
            display_name__iexact=line.payee.strip(), deleted_at__isnull=True
        ).first()
        return found
    return None


def coding_spec(rule: BankRule, line: StatementLine) -> MoneySpec:
    """The spend / receive the rule makes of the line (not yet written)."""
    kind = BankTransactionKind.SPEND if line.amount < 0 else BankTransactionKind.RECEIVE
    reference = render_reference(rule.reference_template, line)
    contact = _contact(rule, line)
    if rule.type == BankRuleType.TRANSFER:
        other = rule.transfer_account
        if other is None or other.pk == line.bank_account_id:
            raise ValidationError(
                _("A transfer rule needs another bank account than the line's own."),
                code="banking.rule.transfer_same_account",
            )
        return MoneySpec(
            kind=kind,
            bank_account=line.bank_account,
            date=line.date,
            contact=contact,
            reference=reference,
            tax_mode=TaxMode.NO_TAX,
            lines=[
                MoneyLine(
                    other.gl_account,
                    abs(Decimal(line.amount)),
                    description=line.description or line.payee,
                )
            ],
        )
    shares = [Share.of(a) for a in rule.allocations.select_related("account").order_by("order")]
    spec: MoneySpec = money_spec(
        kind,
        line.bank_account,
        line.date,
        allocate(Decimal(line.amount), shares),
        contact=contact,
        reference=reference,
    )
    return spec


def code_line(line: StatementLine, rule: BankRule, *, user: Any = ACTING) -> BankTransaction:
    """Code one line with ``rule`` (module docstring) and log the application."""
    with org_context(line.organisation), transaction.atomic():
        locked = (
            StatementLine._base_manager.select_for_update()
            .select_related("bank_account__gl_account", "organisation")
            .get(pk=line.pk)
        )
        person = None if user is ACTING else user
        reason = skip_reason(locked, person)
        if reason is not None:
            raise ValidationError(
                _("Rules don't change this statement line (%(reason)s)."),
                code=f"banking.rule.line_{reason}",
                params={"reason": reason},
            )
        auto = rule.auto_apply
        txn = record_bank_transaction(coding_spec(rule, locked), user=user, draft=not auto)
        locked.bank_transaction = txn
        locked.applied_rule = rule
        locked.auto_coded = auto
        locked.status = StatementLineStatus.CODED if auto else StatementLineStatus.UNCODED
        locked.save(
            update_fields=["bank_transaction", "applied_rule", "auto_coded", "status", "updated_at"]
        )
        mode = RuleApplicationMode.AUTO if auto else RuleApplicationMode.DRAFT
        BankRuleApplication.objects.create(
            organisation=locked.organisation,
            rule=rule,
            statement_line=locked,
            bank_transaction=txn,
            mode=mode,
            created_by=person if getattr(person, "is_authenticated", False) else None,
        )
        BankRule.objects.filter(pk=rule.pk).update(
            applied_count=F("applied_count") + 1, last_applied_at=timezone.now()
        )
        audit(
            "banking.rule.applied",
            obj=locked,
            meta={
                "rule": str(rule.public_id),
                "rule_name": rule.name,
                "mode": str(mode),
                "transaction": str(txn.public_id),
            },
            actor=person,
        )
        line.refresh_from_db()
        return txn


def apply_rules(
    lines: Iterable[StatementLine],
    *,
    rules: Sequence[RuleSpec] | None = None,
    user: Any = ACTING,
) -> ApplyResult:
    """Run the rules on ``lines`` (the current organisation's active rules unless given)."""
    result = ApplyResult()
    candidates = list(load_rules() if rules is None else rules)
    person = None if user is ACTING else user
    for line in lines:
        reason = skip_reason(line, person)
        if reason is not None:
            result.skipped.append((line, reason))
            continue
        outcome = choose(candidates, LineFacts.of(line))
        if outcome.winner is None:
            result.skipped.append((line, "no_match"))
            continue
        if outcome.winner.id in reverted_rules(line):
            result.skipped.append((line, "reverted"))
            continue
        rule = outcome.winner.model or BankRule.objects.get(pk=outcome.winner.id)
        try:
            with transaction.atomic():
                txn = code_line(line, rule, user=user)
        except (ValidationError, LedgerError, TaxError) as error:
            result.skipped.append((line, getattr(error, "code", None) or "invalid"))
            continue
        result.applied.append((line, rule, txn))
    return result


def uncoded_lines(bank_account: Any = None) -> Any:
    """The lines rules may code: Uncoded, without a transaction, oldest first."""
    query = StatementLine.objects.select_related("bank_account__gl_account", "organisation").filter(
        status=StatementLineStatus.UNCODED, bank_transaction__isnull=True
    )
    if bank_account is not None:
        query = query.filter(bank_account=bank_account)
    return query.order_by("date", "pk")


def confirm_line(line: StatementLine, *, user: Any = ACTING) -> BankTransaction:
    """Post the draft a rule left on ``line``: the line becomes Coded (F-04-T07)."""
    with org_context(line.organisation), transaction.atomic():
        locked = StatementLine._base_manager.select_for_update().get(pk=line.pk)
        txn = locked.bank_transaction
        if txn is None or txn.status != BankTransactionStatus.DRAFT:
            raise ValidationError(
                _("This statement line has no draft coding to post."),
                code="banking.rule.no_draft",
            )
        posted = post_draft_transaction(txn, user=user)
        locked.status = StatementLineStatus.CODED
        locked.save(update_fields=["status", "updated_at"])
        person = None if user is ACTING else user
        audit(
            "banking.rule.confirmed",
            obj=locked,
            meta={
                "transaction": str(posted.public_id),
                "rule": str(locked.applied_rule.public_id) if locked.applied_rule else "",
            },
            actor=person,
        )
        line.refresh_from_db()
        return posted


def reverted_rules(line: StatementLine) -> set[int]:
    """The rules whose coding of ``line`` was reverted: they don't code it again."""
    return set(
        BankRuleApplication.objects.filter(
            statement_line_id=line.pk, reverted_at__isnull=False
        ).values_list("rule_id", flat=True)
    )


def revert_line(line: StatementLine, *, user: Any = ACTING) -> StatementLine:
    """Undo a rule's coding of ``line`` (module docstring)."""
    with org_context(line.organisation), transaction.atomic():
        locked = (
            StatementLine._base_manager.select_for_update(of=("self",))
            .select_related("applied_rule", "bank_transaction")
            .get(pk=line.pk)
        )
        txn = locked.bank_transaction
        if locked.applied_rule_id is None or txn is None:
            raise ValidationError(
                _("This statement line wasn't coded by a rule."),
                code="banking.rule.not_rule_coded",
            )
        person = None if user is ACTING else user
        was = {"status": locked.status, "auto_coded": locked.auto_coded}
        if txn.status == BankTransactionStatus.POSTED:
            void_bank_transaction(txn, date=txn.date, user=user)
        elif txn.status == BankTransactionStatus.DRAFT:
            BankTransaction.objects.filter(pk=txn.pk).update(
                status=BankTransactionStatus.VOIDED, voided_at=timezone.now()
            )
        rule = locked.applied_rule
        BankRuleApplication.objects.filter(
            statement_line=locked, bank_transaction=txn, reverted_at__isnull=True
        ).update(reverted_at=timezone.now())
        locked.status = StatementLineStatus.UNCODED
        locked.bank_transaction = None
        locked.applied_rule = None
        locked.auto_coded = False
        locked.save(
            update_fields=["status", "bank_transaction", "applied_rule", "auto_coded", "updated_at"]
        )
        audit(
            "banking.rule.reverted",
            obj=locked,
            changes={
                "status": [str(was["status"]), str(StatementLineStatus.UNCODED)],
                "auto_coded": [was["auto_coded"], False],
            },
            meta={
                "rule": str(rule.public_id) if rule else "",
                "rule_name": rule.name if rule else "",
                "transaction": str(txn.public_id),
            },
            actor=person,
        )
        line.refresh_from_db()
        return line
