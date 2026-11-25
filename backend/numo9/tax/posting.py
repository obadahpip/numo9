"""Posting mapper (G-01-T07): where a line's tax goes in the journal.

``map_tax(line_tax)`` turns one line's calculated tax (``LineTax``, G-01-T06) into:

- the amount **added to the line's own account** — on a purchase, every component's
  non-claimable part (BC PST, the restricted half of a meals ITC); on a sale, nothing;
- one posting per component to its **control account**:

  ===================  ===========================  ===============================
  component            sales (tax collected)        purchases (claimable part only)
  ===================  ===========================  ===============================
  GST, HST             GST/HST payable              GST/HST receivable (ITC)
  QST                  QST payable                  QST receivable (ITR)
  PST / RST            PST payable                  — (never claimable: on the cost)
  ===================  ===========================  ===============================

  The component's own ``control_account_sales`` / ``control_account_purchase`` wins; otherwise
  the organisation's system account for the role. A missing account is refused naming it
  (``tax.posting.control_missing``) — never posted somewhere else.

``journal_lines(entries, side=…, counter=…)`` builds a balanced set of C-02 ``LineSpec``: each
line's account (net + cost), the control accounts (summed per account) and the counter account
(AR, AP or the bank) for the gross, on the side the document needs.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.models import Account, SystemRole
from numo9.ledger.validation import LineSpec, TaxPart

from .calculator import ComponentTax, LineTax
from .models import TaxError, TaxKind, TaxSide

ZERO = Decimal("0.00")

ROLES: dict[str, tuple[str, str]] = {
    TaxKind.GST: (SystemRole.GST_HST_PAYABLE, SystemRole.ITC_RECEIVABLE),
    TaxKind.HST: (SystemRole.GST_HST_PAYABLE, SystemRole.ITC_RECEIVABLE),
    TaxKind.QST: (SystemRole.QST_PAYABLE, SystemRole.QST_ITR),
    TaxKind.PST: (SystemRole.PST_PAYABLE, ""),
}


@dataclass(frozen=True)
class TaxPosting:
    account: Account
    amount: Decimal
    component: str


@dataclass(frozen=True)
class MappedTax:
    #: Added to the line's own account (purchases: the non-claimable tax).
    to_line: Decimal
    postings: tuple[TaxPosting, ...]


def control_account(part: ComponentTax, side: str) -> Account:
    component = part.link.component
    explicit = (
        component.control_account_sales
        if side == TaxSide.SALES
        else component.control_account_purchase
    )
    if explicit is not None:
        return explicit
    role = ROLES[component.kind][0 if side == TaxSide.SALES else 1]
    found = (
        Account._base_manager.filter(
            organisation_id=component.organisation_id, system_role=role
        ).first()
        if role
        else None
    )
    if found is None:
        raise TaxError(
            _("%(component)s has no control account: add the %(role)s account first."),
            code="tax.posting.control_missing",
            params={
                "component": str(component),
                "role": SystemRole(role).label if role else component.key,
            },
        )
    return found


def map_tax(line_tax: LineTax) -> MappedTax:
    side = line_tax.code.side if line_tax.code is not None else TaxSide.SALES
    to_line = ZERO
    postings = []
    for part in line_tax.components:
        amount = part.amount if side == TaxSide.SALES else part.claimable
        if side == TaxSide.PURCHASE:
            to_line += part.cost
        if amount:
            postings.append(TaxPosting(control_account(part, side), amount, part.key))
    return MappedTax(to_line, tuple(postings))


@dataclass(frozen=True)
class TaxedLine:
    account: Account
    tax: LineTax
    description: str = ""
    contact: Any = None
    tracking: dict[str, Any] = field(default_factory=dict)
    tax_code: str = ""
    #: The document line's code was changed from its default (G-02; the tax audit flag).
    overridden: bool = False


def tax_parts(line_tax: LineTax, *, overridden: bool = False) -> tuple[TaxPart, ...]:
    """The line's tax per component as the ledger carries it to the tax lines (G-05-T02)."""
    code = line_tax.code
    side = code.side if code is not None else TaxSide.SALES
    purchase = side == TaxSide.PURCHASE
    return tuple(
        TaxPart(
            component=part.key,
            kind=part.kind,
            side=side,
            basis=line_tax.net,
            tax=part.amount,
            recoverable=part.claimable if purchase else ZERO,
            non_recoverable=part.cost if purchase else ZERO,
            rate=part.rate,
            code=code.code if code is not None else "",
            overridden=overridden,
            restricted=purchase and part.cost != 0 and bool(part.link.component.recoverable),
        )
        for part in line_tax.components
    )


def journal_lines(
    entries: Iterable[TaxedLine], *, side: str, counter: Account, contact: Any = None
) -> list[LineSpec]:
    """Balanced lines for a document (module docstring). Sales credit the lines and the tax and
    debit ``counter``; purchases the reverse. Negative amounts flip sides (credit notes)."""
    sale = side == TaxSide.SALES
    lines: list[LineSpec] = []
    controls: dict[int, tuple[Account, Decimal]] = {}
    gross = ZERO

    def put(account: Account, amount: Decimal, *, debit: bool, **extra: Any) -> LineSpec:
        if amount < 0:
            amount, debit = -amount, not debit
        return LineSpec(
            account,
            debit=amount if debit else ZERO,
            credit=ZERO if debit else amount,
            **extra,
        )

    for entry in entries:
        mapped = map_tax(entry.tax)
        booked = entry.tax.net + mapped.to_line
        gross += entry.tax.gross
        if booked:
            lines.append(
                put(
                    entry.account,
                    booked,
                    debit=not sale,
                    contact=entry.contact or contact,
                    tracking=dict(entry.tracking),
                    description=entry.description,
                    tax_code=entry.tax_code,
                    tax_parts=tax_parts(entry.tax, overridden=entry.overridden),
                )
            )
        for posting in mapped.postings:
            account, total = controls.get(posting.account.pk, (posting.account, ZERO))
            controls[posting.account.pk] = (account, total + posting.amount)
    for account, total in controls.values():
        if total:
            lines.append(put(account, total, debit=not sale))
    if gross:
        lines.append(put(counter, gross, debit=sale, contact=contact))
    return lines
