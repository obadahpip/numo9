"""Tax defaults for spend and receive money (G-02-T09).

A spend line is a purchase: its default code is the account's ``default_tax_key`` (G-01-T09),
then the supplier's province (``place_of_supply``); a receive line is a sale and follows the
sales decision table (customer's ship-to / billing province, registrations, exports). Bills use
the same purchase resolution when they arrive (D-03b).

- ``line_default(kind, date, organisation, account=, contact=)`` → ``(resolution, version)``.
- ``portions(version, amount, inclusive=, account=)`` → the line's ``TaxPortion`` list from the
  calculator (G-01-T06): on a spend the claimable part (ITC / QST ITR) is recoverable and the
  rest (PST, the restricted part of an ITC) is not — it goes to the expense line; on a receipt
  every component is tax collected.
- ``apply_auto(spec)`` — lines whose ``tax_code`` is ``"auto"`` (and that carry no portions) get
  the default code and its portions; ``"auto"`` with no default, or in a no-tax transaction,
  becomes no code. Lines with an explicit code or portions are posted as given.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.ledger.models import Account, SystemRole
from numo9.tax.calculator import calculate
from numo9.tax.models import TaxSide
from numo9.tax.place_of_supply import Resolution
from numo9.tax.posting import ROLES
from numo9.tax.supply_context import resolve_line

from .models import BankTransactionKind, TaxMode
from .transactions import MoneyLine, MoneySpec, TaxPortion

AUTO = "auto"


def side_for(kind: str) -> str:
    return TaxSide.PURCHASE if kind == BankTransactionKind.SPEND else TaxSide.SALES


def line_default(
    kind: str, day: dt.date, organisation: Any, *, account: Any = None, contact: Any = None
) -> tuple[Resolution, Any]:
    return resolve_line(side_for(kind), day, organisation, contact=contact, account=account)


def portions(
    version: Any, amount: Decimal, *, inclusive: bool, account: Any = None
) -> list[TaxPortion]:
    if version is None:
        return []
    line_tax = calculate(version, amount, inclusive=inclusive, account=account)
    out: list[TaxPortion] = []
    for part in line_tax.components:
        sales_role, purchase_role = ROLES[part.kind]
        if version.side == TaxSide.SALES:
            if part.amount:
                out.append(TaxPortion(sales_role, part.amount, True))
            continue
        role = purchase_role or SystemRole.PST_PAYABLE
        if part.claimable:
            out.append(TaxPortion(role, part.claimable, True))
        if part.cost:
            out.append(TaxPortion(role, part.cost, False))
    return out


def apply_auto(spec: MoneySpec) -> MoneySpec:
    if not any(line.tax_code == AUTO for line in spec.lines):
        return spec
    organisation = spec.bank_account.organisation
    lines: list[MoneyLine] = []
    for line in spec.lines:
        if line.tax_code != AUTO or line.taxes:
            lines.append(line)
            continue
        if spec.tax_mode == TaxMode.NO_TAX:
            lines.append(dataclasses.replace(line, tax_code=""))
            continue
        account = line.account
        if not isinstance(account, Account):
            account = Account.objects.get(pk=account)
        _resolution, version = line_default(
            spec.kind, spec.date, organisation, account=account, contact=spec.contact
        )
        taxes = portions(
            version,
            Decimal(str(line.amount)),
            inclusive=spec.tax_mode == TaxMode.INCLUSIVE,
            account=account,
        )
        lines.append(
            dataclasses.replace(line, tax_code=version.code if version else "", taxes=taxes)
        )
    return dataclasses.replace(spec, lines=lines)
