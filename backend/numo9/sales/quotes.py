"""Quotes (D-02): creation with its number (T02), totals of the selected lines (T03), the
lifecycle (T04), expiry (T05). See each function."""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction

from numo9.orgsettings.models import DocType
from numo9.orgsettings.numbering import allocate_number
from numo9.tenancy.context import org_context

from .models import Quote


def create_quote(organisation: Any, *, number: str = "", **fields: Any) -> Quote:
    """A draft quote numbered ``QU-0001`` from the organisation's quote sequence (D-02-T02), in
    one transaction with the insert: a quote that fails to save gives its number back, and two
    creates at once wait for each other on the sequence row (unique numbers)."""
    with org_context(organisation), transaction.atomic():
        item = Quote(
            organisation=organisation,
            number=number or allocate_number(DocType.QUOTE, organisation),
            **fields,
        )
        item.save()
        return item


def counted(lines: list[Any]) -> list[bool]:
    """Which lines count in the totals (D-02-T03), in the order given: a plain line always; an
    optional line when the customer selected it; of an alternative group, the **first selected**
    line by position (none selected: the group adds nothing)."""
    chosen: set[str] = set()
    out = []
    for line in sorted(lines, key=lambda item: (item.position, item.pk or 0)):
        if line.alternative_group:
            take = bool(line.selected) and line.alternative_group not in chosen
            if take:
                chosen.add(line.alternative_group)
        elif line.is_optional:
            take = bool(line.selected)
        else:
            take = True
        out.append((line, take))
    order = {id(line): take for line, take in out}
    return [order[id(line)] for line in lines]


def _preview_line(line: Any) -> Any:
    from numo9.documents.posting import PreviewLine

    return PreviewLine(
        account=line.account,
        quantity=line.quantity,
        unit_price=line.unit_price,
        discount_type=line.discount_type,
        discount_value=line.discount_value,
        tax_code=line.tax_code,
        description=line.description,
    )


def recalculate(quote: Quote) -> Quote:
    """The calculator's figures on the quote and its lines (server-authoritative): every line
    gets its own amounts, but the **totals** (and the document discount) cover only the lines
    that count (``counted``) — ticking an optional line or choosing another alternative changes
    the total (D-02-T03)."""
    from numo9.documents.posting import result_for

    with org_context(quote.organisation), transaction.atomic():
        lines = list(quote.lines.select_related("account", "tax_code").order_by("position", "pk"))
        flags = counted(lines)
        included = [line for line, take in zip(lines, flags, strict=True) if take]
        excluded = [line for line, take in zip(lines, flags, strict=True) if not take]
        result = result_for(
            "quote",
            [_preview_line(line) for line in included],
            tax_mode=quote.tax_mode,
            discount_type=quote.discount_type,
            discount_value=quote.discount_value,
        )
        alone = result_for(
            "quote",
            [_preview_line(line) for line in excluded],
            tax_mode=quote.tax_mode,
        )
        figures = list(zip(included, result.lines, strict=True)) + list(
            zip(excluded, alone.lines, strict=True)
        )
        for line, row in figures:
            line.net, line.tax_amount, line.amount = row.exclusive, row.tax, row.net
            line.save(update_fields=["net", "tax_amount", "amount", "updated_at"])
        quote.subtotal = result.subtotal
        quote.discount_total = result.discount_total
        quote.tax_total = result.tax_total
        quote.total = result.total
        quote.save(update_fields=["subtotal", "discount_total", "tax_total", "total", "updated_at"])
        return quote


__all__ = ["create_quote", "dt", "recalculate"]
