"""Posted tax lines (G-05-T02): the query layer of the tax reports.

**Writing.** ``record_tax_lines`` is a ledger posted hook (``ledger.services.POSTED_HOOKS``): in
the posting transaction it writes one ``TaxLine`` per journal line and tax component from the
tax the line carried (``LineSpec.tax_parts``, filled by documents and bank transactions):

- a **reversal** copies its original's tax lines with the opposite sign (``reverses``), dated
  the reversal's date — so a revised document (reversal + re-post, D-03b) shows its revision as
  a difference in the period of the change;
- a line with a tax code but no calculated tax (a manual journal) is a ``journal``-source line:
  its basis, no tax — the audit report and the tie-out list it;
- a posting into a filed period (``late_adjustment``, G-03-T08) is flagged ``late``;
- the re-posts of find & recode (C-07) copy the recoded entry's tax lines, with the line's new
  tax code (``copy_for_repost`` — the recode changes coding, never amounts).

**Reading.** ``posted_tax_lines(organisation, start, end, kind=…, side=…, current_only=…)`` —
the organisation's tax lines dated in the range (posted entries and their reversals: every
revision's effect), optionally one tax (``gst_hst``, ``qst``, ``pst``) or one side;
``current_only`` leaves out a superseded pair when both the original and its reversal fall in the
range (lists show the current revision only; totals are the same either way).
"""

from __future__ import annotations

import datetime as dt
from contextvars import ContextVar
from decimal import Decimal
from typing import Any

from django.db.models import Q, QuerySet

from .models import TaxLine, TaxLineSource, TaxSide

ZERO = Decimal("0.00")
KINDS = {"gst_hst": ("gst", "hst"), "qst": ("qst",), "pst": ("pst",)}

#: Set while find & recode re-posts an entry: the re-post's tax lines are copied, not rebuilt.
_REPOSTING: ContextVar[bool] = ContextVar("numo9_tax_reposting", default=False)


def _side_of_code(code: str) -> str:
    return TaxSide.PURCHASE if code.startswith("purchase.") else TaxSide.SALES


def _copy_reversed(entry: Any) -> None:
    originals = TaxLine.objects.filter(entry_id=entry.reversal_of_id).order_by("pk")
    TaxLine.objects.bulk_create(
        [
            TaxLine(
                organisation_id=entry.organisation_id,
                entry=entry,
                line_no=row.line_no,
                date=entry.date,
                side=row.side,
                code=row.code,
                component=row.component,
                kind=row.kind,
                rate=row.rate,
                basis=-row.basis,
                tax=-row.tax,
                recoverable=-row.recoverable,
                non_recoverable=-row.non_recoverable,
                source=row.source,
                overridden=row.overridden,
                restricted=row.restricted,
                late=row.late,
                reverses=row,
            )
            for row in originals
        ]
    )


def record_tax_lines(entry: Any, checked: Any, spec: Any, organisation: Any, person: Any) -> None:
    """Ledger posted hook (module docstring)."""
    if _REPOSTING.get():
        return
    if entry.reversal_of_id is not None:
        _copy_reversed(entry)
        return
    from .returns import _is_late

    late = _is_late(spec)
    rows: list[TaxLine] = []
    for line in checked.lines:
        parts = getattr(line.spec, "tax_parts", ())
        for part in parts:
            rows.append(
                TaxLine(
                    organisation=organisation,
                    entry=entry,
                    line_no=line.line_no,
                    date=entry.date,
                    side=part.side,
                    code=part.code,
                    component=part.component,
                    kind=part.kind,
                    rate=part.rate,
                    basis=part.basis,
                    tax=part.tax,
                    recoverable=part.recoverable,
                    non_recoverable=part.non_recoverable,
                    overridden=part.overridden,
                    restricted=part.restricted,
                    late=late,
                )
            )
        if not parts and line.spec.tax_code:
            side = _side_of_code(line.spec.tax_code)
            basis = line.credit - line.debit if side == TaxSide.SALES else line.debit - line.credit
            rows.append(
                TaxLine(
                    organisation=organisation,
                    entry=entry,
                    line_no=line.line_no,
                    date=entry.date,
                    side=side,
                    code=line.spec.tax_code,
                    basis=basis,
                    source=TaxLineSource.JOURNAL,
                    late=late,
                )
            )
    if rows:
        TaxLine.objects.bulk_create(rows)


class reposting:  # noqa: N801  (a context manager used like a function)
    """While find & recode re-posts an entry, its tax lines come from ``copy_for_repost``."""

    def __enter__(self) -> None:
        self._token = _REPOSTING.set(True)

    def __exit__(self, *exc: object) -> None:
        _REPOSTING.reset(self._token)


def copy_for_repost(original: Any, repost: Any, codes: dict[int, str]) -> None:
    """The re-post of a recode carries ``original``'s tax lines; ``codes`` — the new tax code of
    each recoded line (by line number) — relabels them. Amounts stay as they were."""
    rows = TaxLine.objects.filter(entry_id=original.pk).order_by("pk")
    TaxLine.objects.bulk_create(
        [
            TaxLine(
                organisation_id=repost.organisation_id,
                entry=repost,
                line_no=row.line_no,
                date=repost.date,
                side=row.side,
                code=codes.get(row.line_no, row.code),
                component=row.component,
                kind=row.kind,
                rate=row.rate,
                basis=row.basis,
                tax=row.tax,
                recoverable=row.recoverable,
                non_recoverable=row.non_recoverable,
                source=row.source,
                overridden=row.overridden or row.line_no in codes,
                restricted=row.restricted,
                late=row.late,
            )
            for row in rows
        ]
    )


def posted_tax_lines(
    organisation: Any,
    start: dt.date,
    end: dt.date,
    *,
    kind: str | None = None,
    side: str | None = None,
    current_only: bool = False,
) -> QuerySet[TaxLine]:
    """The tax lines dated in the range (module docstring)."""
    rows = TaxLine.objects.filter(
        organisation=organisation, date__gte=start, date__lte=end
    ).select_related("entry")
    if kind and kind != "all":
        rows = rows.filter(kind__in=KINDS[kind])
    if side and side != "all":
        rows = rows.filter(side=side)
    if current_only:
        # a reversed original whose reversal is in the range, and that reversal
        pair = Q(
            entry__reversed_by__date__gte=start,
            entry__reversed_by__date__lte=end,
        )
        undone = Q(reverses__date__gte=start, reverses__date__lte=end)
        rows = rows.exclude(pair).exclude(undone)
    return rows.order_by("date", "entry_id", "line_no", "pk")
