"""Cash-basis allocator (G-05-T03): a document's tax counts when it is paid, in proportion.

Under the cash basis (G-06 ``TaxSettings.basis``, or a report's explicit override) the tax of an
invoice or a bill is recognised in a range in the proportion its **payments dated in the range**
bear to its total: a 1,130.00 invoice paid 565.00 in the quarter reports half its basis and half
its tax there. Lines that aren't a document's — bank transactions (paid when recorded), manual
journals — count on their own date, as under the accrual basis.

Payments come from **payment sources** the documents' apps register
(``register_payment_source``): ``source_types`` — the journal source types they answer for
(``sales.invoice``…) — and ``payments(organisation, refs, start, end) -> {ref: (paid, total)}``:
what was paid on each document (by public id) in the range, and the document's total. A document
no source knows about has nothing paid (its tax waits for a payment).

``cash_basis_lines(organisation, start, end, kind=…, side=…)`` → ``list[RecognisedLine]`` —
each document tax line scaled by its ratio (cents rounded half up; the last line of a document
takes the rounding remainder so the document's tax is exact), plus the range's other lines.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from .models import TaxLine
from .tax_lines import KINDS, posted_tax_lines

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
AMOUNTS = ("basis", "tax", "recoverable", "non_recoverable")


class PaymentSource(Protocol):
    source_types: tuple[str, ...]

    def payments(
        self, organisation: Any, refs: list[str], start: dt.date, end: dt.date
    ) -> dict[str, tuple[Decimal, Decimal]]: ...


_sources: list[PaymentSource] = []
#: Journals of documents paid later: their tax waits for payments, source or not.
DOCUMENT_TYPES = frozenset(
    {"sales.invoice", "sales.credit_note", "purchases.bill", "purchases.supplier_credit"}
)


def _document_types() -> set[str]:
    return set(DOCUMENT_TYPES) | {t for s in _sources for t in s.source_types}


def register_payment_source(source: PaymentSource) -> PaymentSource:
    if source not in _sources:
        _sources.append(source)
    return source


def unregister_payment_source(source: PaymentSource) -> None:
    if source in _sources:
        _sources.remove(source)


def _source_for(source_type: str) -> PaymentSource | None:
    return next((s for s in _sources if source_type in s.source_types), None)


@dataclass(frozen=True)
class RecognisedLine:
    """A tax line as a report counts it: the stored line and the share recognised (1 accrual)."""

    line: TaxLine
    ratio: Decimal
    basis: Decimal
    tax: Decimal
    recoverable: Decimal
    non_recoverable: Decimal

    def __getattr__(self, name: str) -> Any:  # code, kind, side, entry… read from the line
        return getattr(self.line, name)


def accrual(rows: Iterable[TaxLine]) -> list[RecognisedLine]:
    return [
        RecognisedLine(r, Decimal("1"), r.basis, r.tax, r.recoverable, r.non_recoverable)
        for r in rows
    ]


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _documents(organisation: Any, end: dt.date, kind: str | None, side: str | None) -> Any:
    types = sorted(_document_types())
    rows = TaxLine.objects.filter(
        organisation=organisation, date__lte=end, entry__source_type__in=types
    ).select_related("entry")
    if kind and kind != "all":
        rows = rows.filter(kind__in=KINDS[kind])
    if side and side != "all":
        rows = rows.filter(side=side)
    return rows.order_by("entry_id", "line_no", "pk")


def cash_basis_lines(
    organisation: Any,
    start: dt.date,
    end: dt.date,
    *,
    kind: str | None = None,
    side: str | None = None,
) -> list[RecognisedLine]:
    """The range's tax under the cash basis (module docstring)."""
    types = _document_types()
    out: list[RecognisedLine] = []
    # lines that aren't a paid document's: on their own date
    others = posted_tax_lines(organisation, start, end, kind=kind, side=side).exclude(
        entry__source_type__in=types
    )
    out.extend(accrual(others))
    # documents: by payment share — originals only (a reversed document's payments are none)
    by_document: dict[tuple[str, str], list[TaxLine]] = defaultdict(list)
    for row in _documents(organisation, end, kind, side):
        if row.reverses_id is not None:
            continue
        by_document[(row.entry.source_type, row.entry.source_id)].append(row)
    refs: dict[str, list[str]] = defaultdict(list)
    for source_type, ref in by_document:
        refs[source_type].append(ref)
    paid: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
    for source_type, ids in refs.items():
        source = _source_for(source_type)
        if source is None:
            continue
        for ref, figures in source.payments(organisation, ids, start, end).items():
            paid[(source_type, ref)] = figures
    for key, rows in by_document.items():
        amount, total = paid.get(key, (ZERO, ZERO))
        if not amount or not total:
            continue
        ratio = min(Decimal(amount) / Decimal(total), Decimal("1"))
        exact = {name: sum((getattr(r, name) for r in rows), ZERO) * ratio for name in AMOUNTS}
        given = dict.fromkeys(AMOUNTS, ZERO)
        for index, row in enumerate(rows):
            last = index == len(rows) - 1
            values = {}
            for name in AMOUNTS:
                share = (
                    _cents(exact[name]) - given[name]
                    if last
                    else _cents(getattr(row, name) * ratio)
                )
                given[name] += share
                values[name] = share
            out.append(RecognisedLine(row, ratio, **values))
    return sorted(out, key=lambda r: (r.line.date, r.line.entry_id, r.line.line_no))


def recognised_lines(
    organisation: Any,
    start: dt.date,
    end: dt.date,
    *,
    basis: str,
    kind: str | None = None,
    side: str | None = None,
    current_only: bool = False,
) -> list[RecognisedLine]:
    """The lines a tax report counts on ``basis`` (``accrual`` or ``cash``)."""
    if basis == "cash":
        return cash_basis_lines(organisation, start, end, kind=kind, side=side)
    return accrual(
        posted_tax_lines(organisation, start, end, kind=kind, side=side, current_only=current_only)
    )
