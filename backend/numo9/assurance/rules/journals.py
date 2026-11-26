"""Rules over manual journals (K-09-T07, T08, T11): journals that post to bank or cash, expense
journals without a contact or an attachment, round amounts and weekend postings.

Manual journals are the riskiest way to record a purchase: they bypass the supplier ledger, the
receipt and the GST/HST input-tax-credit logic (docs/xero_teardown.md §5.8). Every rule here
checks posted, unreversed manual journals; in an incremental run, the posted journals only.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any, ClassVar

from django.utils.translation import gettext_lazy

from numo9.ledger.models import AccountType, JournalEntry, JournalLine

from ..models import Severity
from .base import Context, Hit, Param, Rule, register
from .common import (
    ZERO,
    Numbers,
    accounting_lines,
    entry_hit,
    entry_total,
    is_cash,
    posted_entries,
)


@register
class JournalToCash(Rule):
    code = "JOURNAL_TO_CASH"
    name = gettext_lazy("Manual journal posts to a bank or cash account")
    description = gettext_lazy(
        "Money in or out of a bank or cash account recorded by manual journal instead of a bank "
        "transaction, a payment or a transfer."
    )
    explanation = gettext_lazy(
        "%(journal)s (%(date)s) posts %(cash_amount)s to %(accounts)s. Money in or out of a bank "
        "or cash account should be recorded as a bank transaction, a payment or a transfer so it "
        "can be reconciled."
    )
    default_severity = Severity.WARNING
    incremental = True
    money_keys = ("cash_amount",)
    date_keys = ("date",)
    params = {
        "min_amount": Param(
            "decimal", Decimal("0.00"), gettext_lazy("Minimum amount"), minimum=Decimal("0")
        )
    }

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        numbers = Numbers(ctx.organisation)
        for entry in posted_entries(ctx, manual=True):
            cash = [line for line in accounting_lines(entry) if is_cash(line.account)]
            if not cash:
                continue
            amount = sum((line.debit + line.credit for line in cash), ZERO)
            if amount < ctx.params["min_amount"]:
                continue
            names = sorted({line.account.name for line in cash})
            yield entry_hit(
                entry,
                numbers,
                amount,
                cash_amount=f"{amount:.2f}",
                accounts=", ".join(names),
            )


def _expense_lines(entry: JournalEntry) -> list[JournalLine]:
    return [line for line in entry.lines.all() if line.account.type == AccountType.EXPENSE]


def _attached(entry_ids: list[Any]) -> set[str]:
    """The journals (public ids) that have at least one live document attached."""
    if not entry_ids:
        return set()
    from django.contrib.contenttypes.models import ContentType

    from numo9.files.models import Attachment

    rows = Attachment.objects.filter(
        content_type=ContentType.objects.get_for_model(JournalEntry),
        object_public_id__in=entry_ids,
        deleted_at__isnull=True,
        document__deleted_at__isnull=True,
    ).values_list("object_public_id", flat=True)
    return {str(value) for value in rows}


class _ExpenseJournalRule(Rule):
    """Manual journals with an expense line; ``flagged`` picks the lines with the problem."""

    default_severity = Severity.WARNING
    incremental = True
    needs_attachments: ClassVar[bool] = False
    money_keys = ("expense_amount",)
    date_keys = ("date",)
    params = {
        "min_amount": Param(
            "decimal", Decimal("0.00"), gettext_lazy("Minimum amount"), minimum=Decimal("0")
        )
    }

    def flagged(
        self, entry: JournalEntry, expense: list[JournalLine], attached: set[str]
    ) -> list[JournalLine]:
        raise NotImplementedError

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        numbers = Numbers(ctx.organisation)
        entries = [
            (entry, expense)
            for entry in posted_entries(ctx, manual=True)
            if (expense := _expense_lines(entry))
        ]
        attached = (
            _attached([entry.public_id for entry, _lines in entries])
            if self.needs_attachments
            else set()
        )
        for entry, expense in entries:
            amount = sum((line.debit - line.credit for line in expense), ZERO)
            if abs(amount) < ctx.params["min_amount"]:
                continue
            lines = self.flagged(entry, expense, attached)
            if not lines:
                continue
            yield entry_hit(
                entry,
                numbers,
                amount,
                expense_amount=f"{amount:.2f}",
                lines=[line.line_no for line in lines],
                accounts=", ".join(sorted({line.account.name for line in lines})),
            )


@register
class ExpenseJournalNoContact(_ExpenseJournalRule):
    code = "EXPENSE_JOURNAL_NO_CONTACT"
    name = gettext_lazy("Expense journal without a contact")
    description = gettext_lazy(
        "A manual journal records an expense without saying who it was paid to."
    )
    explanation = gettext_lazy(
        "%(journal)s (%(date)s) records %(expense_amount)s of expenses (%(accounts)s) with no "
        "supplier. Enter purchases as bills or spend money with the supplier, so the supplier "
        "ledger and the GST/HST credits are right."
    )

    def flagged(
        self, entry: JournalEntry, expense: list[JournalLine], attached: set[str]
    ) -> list[JournalLine]:
        return [line for line in expense if not line.contact_id]


@register
class ExpenseJournalNoAttachment(_ExpenseJournalRule):
    code = "EXPENSE_JOURNAL_NO_ATTACHMENT"
    name = gettext_lazy("Expense journal without an attachment")
    description = gettext_lazy("A manual journal records an expense with no receipt attached.")
    explanation = gettext_lazy(
        "%(journal)s (%(date)s) records %(expense_amount)s of expenses (%(accounts)s) with no "
        "receipt or invoice attached. Attach the supporting document: the CRA asks for it to "
        "claim the expense and its input tax credits."
    )
    needs_attachments = True

    def flagged(
        self, entry: JournalEntry, expense: list[JournalLine], attached: set[str]
    ) -> list[JournalLine]:
        return [] if str(entry.public_id) in attached else expense


@register
class RoundAmount(Rule):
    """A posted manual journal whose amount is at least ``threshold`` and a multiple of
    ``multiple`` (5,000.00; 12,300.00…) — estimates and plugs look like this."""

    code = "ROUND_AMOUNT"
    name = gettext_lazy("Round amount journal")
    description = gettext_lazy("A large manual journal for a round amount: an estimate or a plug?")
    explanation = gettext_lazy(
        "%(journal)s (%(date)s) is for %(total)s, a round amount: check it is supported by a "
        "document and not an estimate or a balancing figure."
    )
    default_severity = Severity.INFO
    incremental = True
    money_keys = ("total",)
    date_keys = ("date",)
    params = {
        "threshold": Param(
            "decimal", Decimal("1000.00"), gettext_lazy("From"), minimum=Decimal("1")
        ),
        "multiple": Param(
            "decimal", Decimal("100.00"), gettext_lazy("Multiple of"), minimum=Decimal("1")
        ),
    }

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        numbers = Numbers(ctx.organisation)
        threshold, multiple = ctx.params["threshold"], ctx.params["multiple"]
        for entry in posted_entries(ctx, manual=True):
            total = entry_total(entry)
            if total >= threshold and total % multiple == 0:
                yield entry_hit(entry, numbers, total, total=f"{total:.2f}")
