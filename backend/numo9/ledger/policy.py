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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .models import AccountSubtype, Book, JournalCategory, LedgerError
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
) -> None:
    """Every business rule of C-03 for a journal about to be posted (module docstring).

    ``attachments`` — how many documents the journal carries (A-06 attachments)."""
    problems = Problems()
    type_rules(checked, problems, caller)
    account_flag_rules(checked, problems, attachments)
    if problems.errors:
        raise JournalRuleError(problems.errors)
