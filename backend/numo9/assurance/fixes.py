"""Fix-to-draft service (K-09-T16): a finding's proposed correcting entry becomes a **draft
journal** (C-04), linked to the finding; posting that draft re-checks the finding and resolves it.

- ``propose(finding)`` — the rule's ``propose_fix`` in the organisation's context with its
  settings (``None`` when the rule has none or nothing can be proposed now);
- ``create_fix_draft(finding, user, lines=…, date=…, narration=…)`` — saves the proposal (or the
  person's edited grid from the drawer) as a draft manual journal of type *Adjusting* with
  ``save_draft`` (validated like every journal; never posted here: a draft fix is never
  auto-posted), sets ``finding.fix_entry`` and audits ``assurance.finding.fix_drafted``. Asking
  again while the draft is still a draft replaces its lines;
- ``resolve_fixed(entry, person)`` — the posting hook: the active findings whose fix is the posted
  journal are evaluated again for their subject, in the same transaction; a condition that is
  gone resolves the finding (``assurance.finding.resolved`` with ``fixed_by``).

Refusals are ``FixRefused`` (``ValidationError``) with a code: ``assurance.fix.not_active``,
``assurance.fix.none`` (no journal fix for this finding), ``assurance.fix.invalid`` (a line).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.ledger.models import Account, JournalCategory, JournalEntry, JournalStatus
from numo9.ledger.sequence import format_journal_number
from numo9.ledger.services import save_draft
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context

from .models import ACTIVE_STATUSES, ExceptionFinding, fingerprint_of
from .rules.base import FixProposal, Scope, context_for, registry
from .runner import _audit, resolve


class FixRefused(ValidationError):
    pass


def _refuse(message: str, code: str, **params: Any) -> FixRefused:
    return FixRefused(message, code=code, params=params)


def propose(finding: ExceptionFinding, *, now: dt.datetime | None = None) -> FixProposal | None:
    if finding.rule_code not in registry:
        return None
    rule = registry.get(finding.rule_code)
    if not rule.has_fix:
        return None
    ctx = context_for(finding.organisation, rule, now=now)
    with org_context(finding.organisation):
        return rule.propose_fix(finding, ctx)


def _money(value: Any, position: int) -> Decimal:
    try:
        amount = Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise _refuse(
            _("Line %(line)d: enter an amount."), "assurance.fix.invalid", line=position
        ) from None
    if amount < 0:
        raise _refuse(
            _("Line %(line)d: amounts are positive."), "assurance.fix.invalid", line=position
        )
    return amount


def _line_specs(rows: Sequence[dict[str, Any]]) -> tuple[LineSpec, ...]:
    specs: list[LineSpec] = []
    for position, row in enumerate(rows, 1):
        account = Account.objects.filter(public_id=row.get("account")).first()
        if account is None:
            raise _refuse(
                _("Line %(line)d: choose an account of this organisation."),
                "assurance.fix.invalid",
                line=position,
            )
        specs.append(
            LineSpec(
                account,
                debit=_money(row.get("debit"), position),
                credit=_money(row.get("credit"), position),
                description=str(row.get("description") or "")[:500],
            )
        )
    return tuple(specs)


def create_fix_draft(
    finding: ExceptionFinding,
    user: Any,
    *,
    lines: Sequence[dict[str, Any]] | None = None,
    date: dt.date | None = None,
    narration: str | None = None,
) -> JournalEntry:
    """The finding's fix as a draft journal (module docstring)."""
    organisation = finding.organisation
    with org_context(organisation), transaction.atomic():
        finding = ExceptionFinding.objects.select_for_update().get(pk=finding.pk)
        if finding.status not in ACTIVE_STATUSES:
            raise _refuse(
                _("This finding is %(status)s: there is nothing to fix."),
                "assurance.fix.not_active",
                status=str(finding.get_status_display()).lower(),
            )
        proposal = propose(finding)
        if proposal is None or proposal.kind != "journal":
            raise _refuse(
                _("There is no correcting journal to propose for this finding."),
                "assurance.fix.none",
            )
        spec = JournalSpec(
            date=date or proposal.date or timezone.localdate(),
            narration=(narration if narration is not None else proposal.narration)[:1000],
            journal_type=JournalCategory.ADJUSTING,
            lines=_line_specs(lines if lines is not None else proposal.lines),
        )
        existing = finding.fix_entry
        reuse = (
            existing if existing is not None and existing.status == JournalStatus.DRAFT else None
        )
        draft = save_draft(spec, entry=reuse, organisation=organisation, user=user)
        finding.fix_entry = draft
        finding.save(update_fields=["fix_entry", "updated_at"])
        person = user if getattr(user, "is_authenticated", False) else None
        _audit(
            finding,
            "fix_drafted",
            person,
            draft=str(draft.public_id),
            reasoning=proposal.reasoning,
        )
        return draft


def resolve_fixed(entry: JournalEntry, person: Any = None) -> int:
    """Resolve the active findings whose fix ``entry`` is, when their condition is gone."""
    findings = list(
        ExceptionFinding.objects.filter(fix_entry=entry, status__in=ACTIVE_STATUSES).order_by("pk")
    )
    resolved = 0
    for finding in findings:
        if finding.rule_code not in registry:
            continue
        rule = registry.get(finding.rule_code)
        accounts = (
            frozenset({finding.subject_id})
            if finding.subject_type == "ledger.Account"
            else frozenset(str(line.account.public_id) for line in entry.lines.all())
        )
        entries = frozenset({str(entry.public_id)})
        if finding.subject_type == "ledger.JournalEntry":
            entries |= {finding.subject_id}
        ctx = context_for(entry.organisation, rule, scope=Scope(entries, accounts))
        still = {
            fingerprint_of(rule.code, hit.subject_type, hit.subject_id)
            for hit in rule.evaluate(ctx)
        }
        if finding.fingerprint in still:
            continue
        resolve(
            finding,
            now=timezone.now(),
            actor=person if getattr(person, "is_authenticated", False) else None,
            fixed_by=format_journal_number(entry.organisation, entry.number),
        )
        resolved += 1
    return resolved
