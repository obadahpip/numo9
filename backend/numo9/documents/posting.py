"""Posting preview (D-01-T08): the journal a document will post, before it is saved.

``preview(kind, date, lines, …)`` validates the lines (D-01-T06), calculates them
(``DocumentCalculator``, D-01-T03…T05) and maps the result to the C-02 journal lines the
document's posting will use (``numo9.tax.posting.journal_lines``, G-01-T07) — so the preview
and the posted entry are the same lines (D-03a posts ``Preview.spec()``):

=============================  ============================================================
sales (invoice)                Cr each line's account (taxable net), Cr the tax control
                               accounts (GST/HST payable, PST payable, QST payable), Dr AR
purchase (bill)                Dr each line's account (net + the non-claimable tax), Dr ITC /
                               ITR, Cr AP
credit note, supplier credit   the same lines on the other side
=============================  ============================================================

The document discount is booked net: each line posts its taxable amount (net less its share of
the discount), as the tax is calculated on it. Lines without an account are left out of the
journal (a draft can be incomplete); ``Preview.complete`` says whether every line with an amount
has one.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.models import Account, JournalType, LedgerError, SystemRole
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tax.calculator import ComponentTax, LineTax
from numo9.tax.posting import TaxedLine, journal_lines
from numo9.tax.recovery import claimable_pct

from .calculator import (
    NONE,
    Component,
    DocumentInput,
    DocumentResult,
    LineInput,
    calculate,
)
from .models import TaxMode
from .validation import LineCheck, side_of, validate_lines

ZERO = Decimal("0.00")
CREDITS = frozenset({"credit_note", "supplier_credit"})
JOURNAL_TYPES = {"sales": JournalType.SALES, "purchase": JournalType.PURCHASE}


@dataclass(frozen=True)
class PreviewLine:
    account: Account | None = None
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = ZERO
    discount_type: str = NONE
    discount_value: Decimal = ZERO
    #: A tax code version (G-01), or None.
    tax_code: Any = None
    description: str = ""
    tracking: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Preview:
    kind: str
    date: dt.date
    result: DocumentResult
    lines: tuple[LineSpec, ...]
    complete: bool
    contact: Any = None

    @property
    def side(self) -> str:
        return side_of(self.kind)

    def spec(
        self, *, source_type: str = "", source_id: str = "", narration: str = ""
    ) -> JournalSpec:
        """The ``JournalSpec`` the document posts."""
        return JournalSpec(
            date=self.date,
            lines=self.lines,
            type=JOURNAL_TYPES[self.side],
            narration=narration,
            source_type=source_type,
            source_id=source_id,
        )

    def as_dict(self) -> dict[str, Any]:
        def money(value: Any) -> str:
            return f"{Decimal(value):.2f}"

        rows: list[dict[str, Any]] = []
        for line in self.lines:
            account = line.account
            if not isinstance(account, Account):  # pragma: no cover — journal_lines gives accounts
                account = Account.objects.get(pk=account)
            rows.append(
                {
                    "account": {
                        "id": str(account.public_id),
                        "code": account.code,
                        "name": account.name,
                    },
                    "debit": money(line.debit),
                    "credit": money(line.credit),
                    "description": line.description,
                    "tax_code": line.tax_code,
                }
            )
        return {
            "lines": rows,
            "debits": money(sum((Decimal(r["debit"]) for r in rows), ZERO)),
            "credits": money(sum((Decimal(r["credit"]) for r in rows), ZERO)),
            "complete": self.complete,
        }


def _links(code: Any) -> list[Any]:
    if code is None:
        return []
    if "components" in getattr(code, "_prefetched_objects_cache", {}):
        return sorted(code.components.all(), key=lambda link: link.position)
    return list(code.components.select_related("component", "tax_code").order_by("position"))


def _counter(side: str) -> Account:
    role = SystemRole.AR if side == "sales" else SystemRole.AP
    found = Account.objects.filter(system_role=role).first()
    if found is None:
        raise LedgerError(
            _("The organisation has no %(role)s account: add it to the chart of accounts."),
            code="documents.posting.counter_missing",
            params={"role": SystemRole(role).label},
        )
    return found


def _negate(tax: LineTax) -> LineTax:
    return LineTax(
        tax.code,
        -tax.net,
        tuple(
            ComponentTax(c.link, c.rate, -c.amount, -c.claimable, -c.cost) for c in tax.components
        ),
    )


def _all_links(lines: Sequence[PreviewLine], tax_mode: str) -> list[list[Any]]:
    return [_links(line.tax_code) if tax_mode != TaxMode.NO_TAX else [] for line in lines]


def _document_input(
    side: str,
    lines: Sequence[PreviewLine],
    links: Sequence[Sequence[Any]],
    tax_mode: str,
    discount_type: str,
    discount_value: Decimal,
) -> DocumentInput:
    return DocumentInput(
        lines=[
            LineInput(
                quantity=Decimal(line.quantity),
                unit_price=Decimal(line.unit_price),
                discount_type=line.discount_type,
                discount_value=Decimal(line.discount_value),
                components=tuple(
                    Component(
                        link.component.key,
                        Decimal(link.component.rate),
                        link.component.kind,
                        claimable_pct(link, account=line.account)
                        if side == "purchase"
                        else Decimal("100"),
                    )
                    for link in parts
                ),
            )
            for line, parts in zip(lines, links, strict=True)
        ],
        tax_mode=tax_mode,
        side=side,
        discount_type=discount_type,
        discount_value=Decimal(discount_value),
    )


def result_for(
    kind: str,
    lines: Sequence[PreviewLine],
    *,
    tax_mode: str = TaxMode.EXCLUSIVE,
    discount_type: str = NONE,
    discount_value: Decimal = ZERO,
) -> DocumentResult:
    """The calculation alone (no validation, no journal): the stateless calculate endpoint."""
    side = side_of(kind)
    links = _all_links(lines, tax_mode)
    return calculate(_document_input(side, lines, links, tax_mode, discount_type, discount_value))


def preview(
    kind: str,
    date: dt.date,
    lines: Sequence[PreviewLine],
    *,
    tax_mode: str = TaxMode.EXCLUSIVE,
    discount_type: str = NONE,
    discount_value: Decimal = ZERO,
    contact: Any = None,
) -> Preview:
    """The document's calculation and journal lines (module docstring)."""
    side = side_of(kind)
    validate_lines(
        kind, date, [LineCheck(line.account, line.tax_code) for line in lines], tax_mode=tax_mode
    )
    links = _all_links(lines, tax_mode)
    result = calculate(_document_input(side, lines, links, tax_mode, discount_type, discount_value))
    taxed: list[TaxedLine] = []
    complete = True
    for line, parts, figures in zip(lines, links, result.lines, strict=True):
        if line.account is None:
            if figures.taxable or figures.tax:
                complete = False
            continue
        tax = LineTax(
            line.tax_code if tax_mode != TaxMode.NO_TAX else None,
            figures.exclusive,
            tuple(
                ComponentTax(link, t.rate, t.amount, t.claimable, t.cost)
                for link, t in zip(parts, figures.taxes, strict=True)
            ),
        )
        if kind in CREDITS:
            tax = _negate(tax)
        taxed.append(
            TaxedLine(
                line.account,
                tax,
                description=line.description,
                tracking=dict(line.tracking),
                tax_code=line.tax_code.code if line.tax_code is not None else "",
            )
        )
    journal = journal_lines(taxed, side=side, counter=_counter(side), contact=contact)
    return Preview(kind, date, result, tuple(journal), complete, contact)
