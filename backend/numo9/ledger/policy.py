"""Journal business rules (C-03): what a journal may post, beyond balancing.

``check_policy(checked, entry, …)`` runs in the posting transaction after ``validate_journal``
(C-02-T06) and the period check (C-02-T07), before the number is taken; it raises
``JournalRuleError`` (a ``LedgerError``) listing **every** broken rule, each with a stable code
and a message naming the line, the account or the type:

**Journal types** (C-03-T03):

=========================================  =====================================================
code                                       when
=========================================  =====================================================
``ledger.journal.tax_adjustment_book``     a tax-adjustment journal line not in the tax book
``ledger.journal.tax_adjustment_bank``     a tax-adjustment journal line on a bank account
``ledger.journal.system_type``             a system type (Closing, Payroll, Depreciation) posted
                                           by anyone but its process (``caller``: ``year_end``,
                                           ``payroll``, ``depreciation``)
=========================================  =====================================================

**Account flags** (C-03-T04, set on the account in C-01):

=========================================  =====================================================
``ledger.journal.contact_required``        a line on an account that requires a contact, without
``ledger.journal.tracking_required``       a line on an account that requires a tracking
                                           category, without one
``ledger.journal.attachment_required``     a line on an account that requires an attachment, on
                                           a journal with no document attached
=========================================  =====================================================

**Expense journals** (C-03-T06) — manual journals with a line on an expense account, when the
organisation's settings ask for it (C-03-T05):

==============================================  ================================================
``ledger.journal.expense_attachment_required``  ``journal_expense_requires_attachment`` on and no
                                                document attached
``ledger.journal.expense_contact_required``     ``journal_expense_requires_contact`` on and an
                                                expense line without a contact
==============================================  ================================================

**Cash below zero** (C-03-T08, generalised by F-07-T03 to every posting source: journals, spend
and receive money, transfers, payments, payroll) — a posting by a person (not a system job) that
drives a bank or cash account below zero (``cash_guard`` / the F-07 projector), as the
organisation's negative-balance policy says for the account's type and the person (F-07-T01:
``ALLOW`` / ``WARN`` / ``BLOCK``; by default Cash blocked for non-advisers, everything else
warned):

==============================================  ================================================
``ledger.journal.negative_cash``                BLOCK (or WARN for someone who may not
                                                override): ``NegativeBalanceBlocked``, 409,
                                                naming each account, amount and day
``ledger.journal.override_reason_required``     WARN: posted only with a reason of at least 10
                                                characters (``NegativeBalanceWarning``, 422
                                                without one, F-07-T04), stored as a
                                                ``JournalOverride`` and audited
==============================================  ================================================

Documents posted by modules (invoices, bills, payroll) carry their own documents and contacts:
the expense-journal rules apply to manual journals (``JournalType.MANUAL``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .models import AccountSubtype, AccountType, Book, JournalCategory, JournalType, LedgerError
from .validation import ValidatedJournal

#: The process allowed to post each system journal type.
SYSTEM_CALLERS: dict[str, str] = {
    JournalCategory.CLOSING: "year_end",
    JournalCategory.PAYROLL: "payroll",
    JournalCategory.DEPRECIATION: "depreciation",
}


class JournalRuleError(LedgerError):
    """The journal breaks one or more business rules; ``error_list`` has every problem."""


@dataclass
class Problems:
    errors: list[ValidationError] = field(default_factory=list)

    def add(self, message: str, code: str, **params: Any) -> None:
        self.errors.append(ValidationError(message % params if params else message, code=code))


def _account_label(account: Any) -> str:
    return str(account)


def type_rules(checked: ValidatedJournal, problems: Problems, caller: str | None) -> None:
    """C-03-T03: tax adjustments post to the tax book only, never to a bank account; system
    types only from their own process."""
    journal_type = checked.spec.journal_type
    if journal_type == JournalCategory.TAX_ADJUSTMENT:
        for line in checked.lines:
            if line.book != Book.TAX:
                problems.add(
                    _(
                        "Line %(line)d (%(account)s): a tax adjustment posts to the tax book "
                        "only — set the line's book to Tax."
                    ),
                    "ledger.journal.tax_adjustment_book",
                    line=line.line_no,
                    account=_account_label(line.account),
                )
            if line.account.subtype == AccountSubtype.BANK:
                problems.add(
                    _("Line %(line)d (%(account)s): a tax adjustment can't touch a bank account."),
                    "ledger.journal.tax_adjustment_bank",
                    line=line.line_no,
                    account=_account_label(line.account),
                )
    process = SYSTEM_CALLERS.get(journal_type)
    if process is not None and caller != process:
        problems.add(
            _(
                "%(type)s journals are posted by Numo9 itself (the %(process)s process), not by "
                "hand. Choose General, Adjusting, Reclass or Tax adjustment."
            ),
            "ledger.journal.system_type",
            type=str(JournalCategory(journal_type).label),
            process=str(PROCESS_LABELS[process]),
        )


def account_flag_rules(checked: ValidatedJournal, problems: Problems, attachments: int) -> None:
    """C-03-T04: each line honours its account's ``require_contact`` / ``require_tracking`` /
    ``require_attachment`` flags (an attachment is on the journal, so it is named once per
    account)."""
    wanting_attachment: list[str] = []
    for line in checked.lines:
        account = line.account
        label = _account_label(account)
        if account.require_contact and not line.spec.contact:
            problems.add(
                _("Line %(line)d: %(account)s requires a contact — choose one for the line."),
                "ledger.journal.contact_required",
                line=line.line_no,
                account=label,
            )
        if account.require_tracking and not any((line.spec.tracking or {}).values()):
            problems.add(
                _(
                    "Line %(line)d: %(account)s requires a tracking category — choose one for "
                    "the line."
                ),
                "ledger.journal.tracking_required",
                line=line.line_no,
                account=label,
            )
        if account.require_attachment and not attachments and label not in wanting_attachment:
            wanting_attachment.append(label)
    for label in wanting_attachment:
        problems.add(
            _("%(account)s requires an attachment: attach the supporting document to the journal."),
            "ledger.journal.attachment_required",
            account=label,
        )


def expense_rules(
    checked: ValidatedJournal, problems: Problems, attachments: int, organisation: Any
) -> None:
    """C-03-T06: the organisation's expense-journal toggles, on manual journals."""
    if checked.spec.type != JournalType.MANUAL:
        return
    expense = [line for line in checked.lines if line.account.type == AccountType.EXPENSE]
    if not expense:
        return
    from numo9.orgsettings.models import OrganisationSettings

    flags = (
        OrganisationSettings._base_manager.filter(organisation=organisation)
        .values_list("journal_expense_requires_attachment", "journal_expense_requires_contact")
        .first()
    ) or (False, False)
    needs_attachment, needs_contact = flags
    if needs_attachment and not attachments:
        problems.add(
            _(
                "This journal posts to an expense account (%(account)s): this organisation asks "
                "for a supporting document — attach one to the journal."
            ),
            "ledger.journal.expense_attachment_required",
            account=_account_label(expense[0].account),
        )
    if needs_contact:
        for line in expense:
            if not line.spec.contact:
                problems.add(
                    _(
                        "Line %(line)d: expense lines need a contact in this organisation — "
                        "choose one for %(account)s."
                    ),
                    "ledger.journal.expense_contact_required",
                    line=line.line_no,
                    account=_account_label(line.account),
                )


PROCESS_LABELS: dict[str, Any] = {
    "year_end": gettext_lazy("year-end close"),
    "payroll": gettext_lazy("payroll"),
    "depreciation": gettext_lazy("depreciation"),
}


def check_policy(
    checked: ValidatedJournal,
    *,
    caller: str | None = None,
    attachments: int = 0,
    organisation: Any = None,
) -> None:
    """Every business rule of C-03 for a journal about to be posted (module docstring).

    ``attachments`` — how many documents the journal carries (A-06 attachments)."""
    problems = Problems()
    type_rules(checked, problems, caller)
    account_flag_rules(checked, problems, attachments)
    if organisation is not None:
        expense_rules(checked, problems, attachments, organisation)
    if problems.errors:
        raise JournalRuleError(problems.errors)


MIN_OVERRIDE_REASON = 10

#: Postings the cash rule never stops: the re-post of a recode (C-07-T05, an entry that posted
#: already), the year-end close (no bank lines) and conversion balances (C-05: the balances the
#: books had). Reversals aren't checked either (a correction must always be possible) — NEG_CASH
#: (K-09) reports what they leave below zero.
EXEMPT_CALLERS = frozenset({"recode", "year_end", "conversion"})

#: F-07-T03: the negative-balance policy, set by the banking app (``numo9.banking.cash_controls``
#: ``assess``): ``assess(checked, organisation, person, today) -> list[Projection]`` — every bank
#: or cash account the posting would take below zero, each with the policy's ``action`` for the
#: person (``allow`` / ``warn`` / ``block``). Unset, the C-03 rule applies: block for people who
#: aren't advisers, warn for advisers.
CASH_POLICY: list[Any] = []

ALLOW, WARN, BLOCK = "allow", "warn", "block"


class NegativeCash(JournalRuleError):
    """The posting would drive a bank or cash account below zero (C-03-T08, F-07-T03)."""

    def __init__(self, message: Any, *, code: str, projections: list[Any], adviser: bool) -> None:
        super().__init__(message, code=code)
        self.projections = projections
        self.adviser = adviser


class NegativeBalanceBlocked(NegativeCash):
    """F-07-T03: the policy blocks it for this person (``ledger.journal.negative_cash``)."""


class NegativeBalanceWarning(NegativeCash):
    """F-07-T03: the policy warns — the posting goes through only with a reason
    (``ledger.journal.override_reason_required``)."""


def _c03_assess(checked: ValidatedJournal, organisation: Any, person: Any, today: Any) -> list[Any]:
    from dataclasses import replace

    from numo9.orgsettings.locks import is_adviser

    from .cash_guard import shortfalls

    action = WARN if is_adviser(person, organisation) else BLOCK
    return [replace(p, action=action) for p in shortfalls(checked, organisation, today=today)]


def assess_cash(checked: ValidatedJournal, organisation: Any, person: Any) -> list[Any]:
    """The shortfalls of a posting with the policy's action for ``person`` (``CASH_POLICY``)."""
    from numo9.orgsettings.locks import local_date

    today = local_date(organisation, timezone.now())
    assess = CASH_POLICY[0] if CASH_POLICY else _c03_assess
    return list(assess(checked, organisation, person, today))


def may_override(person: Any, organisation: Any) -> bool:
    """Who may post past a WARN: an adviser, or someone holding
    ``accounting.banking.allow_negative`` (F-07; every role with the books gets it)."""
    from numo9.orgsettings.locks import is_adviser

    if is_adviser(person, organisation):
        return True
    if not CASH_POLICY:
        return False
    from numo9.rbac.catalogue import UnknownPermission
    from numo9.rbac.resolver import has_perm

    try:
        return has_perm(person, organisation, "accounting.banking.allow_negative")
    except UnknownPermission:
        return False


def cash_rule(
    checked: ValidatedJournal,
    organisation: Any,
    person: Any,
    override_reason: str = "",
    *,
    caller: str | None = None,
) -> list[Any]:
    """C-03-T08 / F-07-T03, before anything is written: the shortfalls overridden with a reason
    (``[]`` when nothing goes below zero, or only on accounts the policy allows); raises
    ``NegativeBalanceBlocked`` when the policy blocks one for this person (or it warns and they
    may not override), ``NegativeBalanceWarning`` when it warns and no reason is given."""
    if caller in EXEMPT_CALLERS:
        return []
    if not getattr(person, "is_authenticated", False):
        return []  # a system job (imports, scheduled postings) answers to its own process
    found = [p for p in assess_cash(checked, organisation, person) if p.action != ALLOW]
    if not found:
        return []
    named = "; ".join(p.message() for p in found)
    overrides = may_override(person, organisation)
    blocked = [p for p in found if p.action == BLOCK]
    if blocked or not overrides:
        from numo9.orgsettings.locks import is_adviser

        adviser = is_adviser(person, organisation)
        if adviser:
            text = _(
                "%(shortfalls)s. This organisation's negative-balance policy blocks it for "
                "advisers too — change it in Banking settings, or record the money coming in "
                "first."
            )
        else:
            text = _(
                "%(shortfalls)s. A posting can't take this bank or cash account below zero — "
                "record the money coming in first (for example a transfer), or ask your adviser "
                "(or someone allowed to approve negative balances) to post it."
            )
        raise NegativeBalanceBlocked(
            text % {"shortfalls": "; ".join(p.message() for p in blocked or found)},
            code="ledger.journal.negative_cash",
            projections=blocked or found,
            adviser=adviser,
        )
    if len((override_reason or "").strip()) < MIN_OVERRIDE_REASON:
        raise NegativeBalanceWarning(
            _(
                "%(shortfalls)s. You may post it anyway: give the reason (at least %(min)d "
                "characters)."
            )
            % {"shortfalls": named, "min": MIN_OVERRIDE_REASON},
            code="ledger.journal.override_reason_required",
            projections=found,
            adviser=True,
        )
    return found


def auto_reverse_rule(spec: Any, organisation: Any, person: Any) -> None:
    """C-03-T09: an automatic reversal is dated after the journal, in an open period (checked
    when the journal is saved and when it is posted)."""
    when = getattr(spec, "auto_reverse_on", None)
    if when is None:
        return
    problems = Problems()
    if when <= spec.date:
        problems.add(
            _("The automatic reversal (%(reverse)s) must be dated after the journal (%(date)s)."),
            "ledger.journal.auto_reverse_before",
            reverse=when.isoformat(),
            date=spec.date.isoformat(),
        )
    else:
        from numo9.orgsettings.locks import check_lock
        from numo9.orgsettings.models import LockModule

        violation = check_lock(organisation, LockModule.GL, when, person)
        if violation is not None:
            problems.add(
                _(
                    "The automatic reversal date %(reverse)s is in a locked period (%(lock)s). "
                    "Choose a date after the lock."
                ),
                "ledger.journal.auto_reverse_locked",
                reverse=when.isoformat(),
                lock=violation.date.isoformat(),
            )
    if problems.errors:
        raise JournalRuleError(problems.errors)
