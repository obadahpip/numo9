"""Tax split of expense-claim receipts (E-04-T04).

A receipt's amount **includes** its tax (what the employee paid). Its tax code splits it, with the
inclusive rule of ``numo9.tax.calculator.calculate`` (net + Σ tax = the receipt amount, to the
cent), and each component's tax splits again into the **claimable** part (ITC / QST ITR) and the
**cost** with the partial-recovery rules of ``numo9.tax.recovery`` — the category account's
``itc_restriction_pct`` (Meals and entertainment: 50 %) or the code's.

The expense the claim books on the category account is net + cost; the claimable part goes to
the ITC control accounts (the reimbursement bill, E-04-T06). A receipt without a tax code (a
foreign receipt, a supplier not registered) has no tax: all of it is the expense.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from numo9.tax.calculator import LineTax, calculate

from .models import ExpenseLineKind

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ReceiptSplit:
    """A receipt's amount split: ``net`` + ``tax`` = ``gross``; ``tax`` = ``claimable`` +
    ``cost``; the expense booked is ``expense`` = ``net`` + ``cost``."""

    gross: Decimal
    line_tax: LineTax

    @property
    def net(self) -> Decimal:
        return self.line_tax.net

    @property
    def tax(self) -> Decimal:
        return self.line_tax.tax

    @property
    def claimable(self) -> Decimal:
        return self.line_tax.claimable

    @property
    def cost(self) -> Decimal:
        return self.line_tax.cost

    @property
    def expense(self) -> Decimal:
        return self.net + self.cost

    def as_dict(self) -> dict[str, Any]:
        return {
            "gross": str(self.gross),
            "net": str(self.net),
            "tax": str(self.tax),
            "claimable": str(self.claimable),
            "cost": str(self.cost),
            "expense": str(self.expense),
            "components": [
                {
                    "key": c.link.component.key,
                    "rate": str(c.rate),
                    "amount": str(c.amount),
                    "claimable": str(c.claimable),
                    "cost": str(c.cost),
                }
                for c in self.line_tax.components
            ],
        }


def receipt_split(line: Any) -> ReceiptSplit:
    """The split of one claim line. Mileage is an allowance (no tax on it to claim): the whole
    amount is the expense."""
    gross = Decimal(line.amount)
    if line.kind == ExpenseLineKind.MILEAGE or line.tax_code_id is None:
        return ReceiptSplit(gross, calculate(None, gross))
    return ReceiptSplit(
        gross, calculate(line.tax_code, gross, inclusive=True, account=line.account)
    )


@dataclass(frozen=True)
class ClaimTax:
    gross: Decimal
    net: Decimal
    tax: Decimal
    claimable: Decimal
    cost: Decimal

    @property
    def expense(self) -> Decimal:
        return self.net + self.cost


def claim_tax(claim: Any) -> ClaimTax:
    """The claim's totals over its lines (gross = the claim total)."""
    splits = [receipt_split(line) for line in claim.lines.all()]
    return ClaimTax(
        gross=sum((s.gross for s in splits), ZERO),
        net=sum((s.net for s in splits), ZERO),
        tax=sum((s.tax for s in splits), ZERO),
        claimable=sum((s.claimable for s in splits), ZERO),
        cost=sum((s.cost for s in splits), ZERO),
    )
