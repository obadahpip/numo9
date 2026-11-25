"""Bill fixtures (E-02-T17): 50 purchase documents across the provinces and territories, with
partial ITCs.

``build_bill_fixtures(organisation, user)`` creates, in an organisation whose chart is loaded
(C-01 template) and that is registered for GST/HST (RT), the ITCs being claimable:

- one supplier per province and territory (``Fixture supplier — <code>``, billing address
  there), each bill on that province's purchase code: HST (ON, NB, NL, NS, PE), GST + PST — the
  PST never claimable — (BC, MB, SK), GST + QST (QC), GST alone (AB, NT, NU, YT);
- **50 bills**, round-robin over the 13 suppliers, one or two days apart from ``start``, each
  with one to three lines: supplies on an operating expense; on every fourth bill a **meals and
  entertainment** line (ITC restricted to 50 %: half the tax claimable, half a cost); on every
  fifth a zero-rated line; a **10 % holdback** on every ninth;
- statuses: every bill is approved (it posts, E-02-T05) except each seventh, which stays a
  **draft**; each tenth approved bill is then **voided** (E-02-T09).

Quantities and prices follow the bill's position, so the totals are the same on every run: the
snapshot test pins them, with each line's claimable ITC and cost.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.tenancy.context import org_context

from .models import Bill, BillLine, HoldbackType

COUNT = 50
START = dt.date(2026, 4, 1)
PROVINCES: tuple[str, ...] = (
    "ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU",
)  # fmt: skip
DRAFT_EVERY = 7
VOID_EVERY = 10
MEALS_EVERY = 4
ZERO_RATED_EVERY = 5
HOLDBACK_EVERY = 9


def _ensure_qst_itr(organisation: Any) -> None:
    """A Quebec purchase claims QST as an ITR: an Ontario chart has no QST receivable account,
    so the builder adds one, as an organisation registered for QST would."""
    from numo9.ledger.models import Account

    if not Account.objects.filter(system_role="qst_itr").exists():
        Account(
            organisation=organisation,
            code="1415",
            name_i18n={"en-ca": "QST receivable (ITRs)"},
            type="asset",
            subtype="current_asset",
            system_role="qst_itr",
        ).save()


def _supplier(organisation: Any, province: str) -> Any:
    from numo9.contacts.models import Address, AddressKind, Contact

    name = f"Fixture supplier — {province}"
    found = Contact.objects.filter(display_name=name, deleted_at__isnull=True).first()
    if found is not None:
        return found
    supplier = Contact(organisation=organisation, display_name=name, roles=["supplier"])
    supplier.save()
    Address(
        organisation=organisation,
        contact=supplier,
        kind=AddressKind.BILLING,
        country="CA",
        province=province,
        city="—",
        line1=f"{200 + PROVINCES.index(province)} Industrial Road",
    ).save()
    return supplier


def _lines(position: int, province: str, accounts: dict[str, Any]) -> list[tuple[Any, ...]]:
    """(description, quantity, unit price, account, tax code key) of bill ``position``."""
    quantity = Decimal(1 + position % 3)
    price = Decimal(60 + 15 * (position % 11)).quantize(Decimal("0.01"))
    key = f"purchase.{province}.standard"
    lines: list[tuple[Any, ...]] = [("Supplies", quantity, price, accounts["supplies"], key)]
    if position % MEALS_EVERY == MEALS_EVERY - 1:
        lines.append(("Client lunch", Decimal("1"), Decimal("88.00"), accounts["meals"], key))
    if position % ZERO_RATED_EVERY == ZERO_RATED_EVERY - 1:
        lines.append(
            (
                "Basic groceries",
                Decimal("3"),
                Decimal("9.50"),
                accounts["supplies"],
                "purchase.zero_rated",
            )
        )
    return lines


def build_bill_fixtures(
    organisation: Any, user: Any, *, count: int = COUNT, start: dt.date = START
) -> list[Bill]:
    """The fixture bills (module docstring), oldest first."""
    from numo9.ledger.models import Account
    from numo9.tax.resolver import code_for

    from .bill_posting import approve, void
    from .bills import recalculate

    with org_context(organisation):
        _ensure_qst_itr(organisation)
        supplies = (
            Account.objects.filter(type="expense", itc_restriction_pct__isnull=True)
            .order_by("code")
            .first()
        )
        meals = Account.objects.filter(itc_restriction_pct=Decimal("50")).first()
        if supplies is None or meals is None:
            raise ValueError("Load a chart of accounts before building bill fixtures.")
        accounts = {"supplies": supplies, "meals": meals}
        suppliers = {p: _supplier(organisation, p) for p in PROVINCES}
    bills: list[Bill] = []
    approved = 0
    for position in range(count):
        province = PROVINCES[position % len(PROVINCES)]
        day = start + dt.timedelta(days=position + position // 3)
        with org_context(organisation):
            draft = Bill(
                organisation=organisation,
                contact=suppliers[province],
                date=day,
                due_date=day + dt.timedelta(days=30),
                supplier_invoice_no=f"{province}-{9000 + position}",
                reference=f"PO-{8000 + position}",
                holdback_type=HoldbackType.PERCENT
                if position % HOLDBACK_EVERY == HOLDBACK_EVERY - 1
                else HoldbackType.NONE,
                holdback_value=Decimal("10")
                if position % HOLDBACK_EVERY == HOLDBACK_EVERY - 1
                else Decimal("0"),
                created_by=None,
            )
            draft.save()
            for line_no, (text, quantity, price, account, key) in enumerate(
                _lines(position, province, accounts)
            ):
                BillLine(
                    organisation=organisation,
                    document=draft,
                    position=line_no,
                    description=text,
                    quantity=quantity,
                    unit_price=price,
                    account=account,
                    tax_code=code_for(key, "purchase", day, organisation),
                ).save()
            bill = recalculate(draft)
        if position % DRAFT_EVERY != DRAFT_EVERY - 1:
            bill = approve(bill, user)
            approved += 1
            if approved % VOID_EVERY == 0:
                bill = void(bill, user, reason="Fixture: entered twice")
        bills.append(bill)
    return bills
