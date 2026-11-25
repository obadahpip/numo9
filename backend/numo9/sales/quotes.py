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


def recalculate(quote: Quote) -> Quote:
    """The calculator's figures on the quote and its lines (D-02-T03 extends it)."""
    from numo9.documents.posting import PreviewLine, result_for

    with org_context(quote.organisation), transaction.atomic():
        lines = list(quote.lines.select_related("account", "tax_code").order_by("position", "pk"))
        result = result_for(
            "quote",
            [
                PreviewLine(
                    account=line.account,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_type=line.discount_type,
                    discount_value=line.discount_value,
                    tax_code=line.tax_code,
                    description=line.description,
                )
                for line in lines
            ],
            tax_mode=quote.tax_mode,
            discount_type=quote.discount_type,
            discount_value=quote.discount_value,
        )
        for line, figures in zip(lines, result.lines, strict=True):
            line.net, line.tax_amount, line.amount = figures.exclusive, figures.tax, figures.net
            line.save(update_fields=["net", "tax_amount", "amount", "updated_at"])
        quote.subtotal = result.subtotal
        quote.discount_total = result.discount_total
        quote.tax_total = result.tax_total
        quote.total = result.total
        quote.save(update_fields=["subtotal", "discount_total", "tax_total", "total", "updated_at"])
        return quote


__all__ = ["create_quote", "dt", "recalculate"]
