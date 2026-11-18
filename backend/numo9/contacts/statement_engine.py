"""Statement engine (B-02-T04): a contact's statement from the sub-ledger sources.

``build_statement(contact, kind, as_at, start=None)`` → ``StatementDocument`` (B-02-T05 renders
it, T06 sends it):

- **outstanding** — the open items as at ``as_at`` (customers: receivables; suppliers:
  payables), oldest first with a running balance; the **total is the sum of the open items** —
  the same basis as AR aging (B-02-T13) — and the aging buckets by days past due;
- **activity** — the **opening balance** (everything before ``start``), then every document and
  payment from ``start`` to ``as_at`` with a running balance; the closing balance is the amount due.

A contact with both roles gets separate customer and supplier statements (``side``). Amounts are
in the contact's currency; zero-balance contacts are left out of bulk runs by
``statement_due()``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from numo9.orgsettings.models import OrganisationSettings

from . import subledger
from .models import Address, Contact
from .statements import Party, StatementDocument, StatementKind, StatementLine, aging_of
from .subledger import Side

ZERO = Decimal("0.00")


def side_of(contact: Contact) -> Side:
    return (
        "receivables"
        if "customer" in contact.roles or "supplier" not in contact.roles
        else "payables"
    )


def _issuer(contact: Contact) -> Party:
    found = OrganisationSettings.objects.filter(organisation_id=contact.organisation_id).first()
    if found is None:
        return Party(legal_name=contact.organisation.name)
    return Party(
        legal_name=found.printed_name or contact.organisation.name,
        address_line=" ".join(filter(None, [found.mailing_line1, found.mailing_line2])),
        city=found.mailing_city,
        province=found.mailing_province,
        postal_code=found.mailing_postal_code,
        phone=found.phone,
        email=found.email,
    )


def _party(contact: Contact) -> Party:
    billing = Address.objects.filter(
        contact=contact, kind="billing", deleted_at__isnull=True
    ).first()
    return Party(
        legal_name=contact.legal_name or contact.display_name,
        address_line=" ".join(filter(None, [billing.line1, billing.line2])) if billing else "",
        city=billing.city if billing else "",
        province=billing.province if billing else "",
        postal_code=billing.postal_code if billing else "",
        business_number=contact.bn,
    )


def build_statement(
    contact: Contact,
    kind: StatementKind | str,
    as_at: dt.date,
    *,
    start: dt.date | None = None,
    side: Side | None = None,
    issue_date: dt.date | None = None,
) -> StatementDocument:
    kind = StatementKind(kind)
    side = side or side_of(contact)
    lines: list[StatementLine] = []
    opening = ZERO
    if kind == StatementKind.OUTSTANDING:
        balance = ZERO
        for item in subledger.open_items(side, contact, as_at):
            balance += item.outstanding
            lines.append(
                StatementLine(
                    item.date,
                    item.document,
                    item.description,
                    item.due_date,
                    item.outstanding,
                    balance,
                )
            )
        aging = aging_of(lines, as_at)
    else:
        if start is None or start > as_at:
            raise ValueError("An activity statement needs a start on or before its end.")
        before = subledger.activity(side, contact, dt.date.min, start - dt.timedelta(days=1))
        opening = sum((i.amount for i in before), ZERO)
        balance = opening
        for move in subledger.activity(side, contact, start, as_at):
            balance += move.amount
            lines.append(
                StatementLine(
                    move.date, move.document, move.description, move.due_date, move.amount, balance
                )
            )
        open_now = [
            StatementLine(i.date, i.document, i.description, i.due_date, i.outstanding, ZERO)
            for i in subledger.open_items(side, contact, as_at)
        ]
        aging = aging_of(open_now, as_at)
    return StatementDocument(
        kind=kind,
        issuer=_issuer(contact),
        contact=_party(contact),
        contact_number=contact.number,
        currency=contact.currency,
        issue_date=issue_date or as_at,
        as_at=as_at,
        lines=lines,
        period_start=start if kind == StatementKind.ACTIVITY else None,
        opening_balance=opening,
        aging=aging,
    )


def statement_due(contact: Contact, as_at: dt.date, side: Side | None = None) -> bool:
    """Whether a bulk statement run includes the contact (a non-zero balance)."""
    total = sum(
        (i.outstanding for i in subledger.open_items(side or side_of(contact), contact, as_at)),
        ZERO,
    )
    return total != ZERO
