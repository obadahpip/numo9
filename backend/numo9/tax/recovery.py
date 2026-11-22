"""Partial recovery of input tax (G-01-T05): how much of a purchase tax comes back.

A component's tax on a purchase is claimable as an input tax credit (GST/HST) or refund (QST
ITR) only if the component is ``recoverable`` — PST never is. How much of it is claimable is a
percentage resolved in this order, the first one set wins:

1. the **line**'s own % (an editor override);
2. the **account**'s ``itc_restriction_pct`` (Meals and entertainment: 50);
3. the **tax code**'s ``itc_restriction_pct`` (``purchase.ON.standard.itc50``: 50);
4. the code component's ``recoverable_pct`` override;
5. otherwise 100 %.

The rest of the tax is a cost: it is added to the expense line (G-01-T07).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .models import TaxCodeComponent

HUNDRED = Decimal("100")
ZERO = Decimal("0")


def claimable_pct(
    link: TaxCodeComponent, *, line_pct: Decimal | None = None, account: Any = None
) -> Decimal:
    """The claimable share (0–100) of ``link``'s tax on a purchase (module docstring)."""
    if not link.component.recoverable:
        return ZERO
    candidates = (
        line_pct,
        getattr(account, "itc_restriction_pct", None) if account is not None else None,
        link.tax_code.itc_restriction_pct,
        link.recoverable_pct,
    )
    for pct in candidates:
        if pct is not None:
            return min(max(Decimal(pct), ZERO), HUNDRED)
    return HUNDRED
