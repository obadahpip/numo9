"""Rules over manual journals (K-09-T07, T08, T11): journals that post to bank or cash, expense
journals without a contact or an attachment, round amounts and weekend postings.

Manual journals are the riskiest way to record a purchase: they bypass the supplier ledger, the
receipt and the GST/HST input-tax-credit logic (docs/xero_teardown.md §5.8). Every rule here
checks posted, unreversed manual journals; in an incremental run, the posted journals only.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from django.utils.translation import gettext_lazy

from ..models import Severity
from .base import Context, Hit, Param, Rule, register
from .common import ZERO, Numbers, accounting_lines, entry_hit, is_cash, posted_entries


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
