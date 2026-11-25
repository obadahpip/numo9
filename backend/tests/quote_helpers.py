"""Quotes (D-02) test helpers: the sales books of D-03a and a ``quote()`` builder."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.sales.models import Quote, QuoteLine
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.sales_helpers import DAY, sales_books

__all__ = ["DAY", "quote", "sales_books"]


def quote(
    books: dict[str, Any],
    lines: list[Any],
    *,
    number: str = "",
    date: dt.date = DAY,
    expiry: dt.date | None = None,
    **fields: Any,
) -> Quote:
    """A draft quote: ``lines`` = (quantity, unit price, tax key) tuples, or dicts with
    ``quantity``, ``price``, ``tax``, ``is_optional``, ``alternative_group``, ``selected``."""
    from numo9.sales.quotes import create_quote, recalculate

    org = books["org"]
    with org_context(org):
        item = create_quote(
            org,
            contact=books["customers"][fields.pop("province", "ON")],
            date=date,
            expiry_date=expiry or date + dt.timedelta(days=30),
            number=number,
            **fields,
        )
        for position, raw in enumerate(lines):
            spec: dict[str, Any] = (
                raw
                if isinstance(raw, dict)
                else {"quantity": raw[0], "price": raw[1], "tax": raw[2]}
            )
            key = spec.get("tax", "")
            QuoteLine(
                organisation=org,
                document=item,
                position=position,
                description=spec.get("description", f"Line {position + 1}"),
                quantity=Decimal(spec.get("quantity", "1")),
                unit_price=Decimal(spec["price"]),
                account=books["revenue"],
                tax_code=code_for(key, "sales", date, org) if key else None,
                is_optional=spec.get("is_optional", False),
                alternative_group=spec.get("alternative_group", ""),
                selected=spec.get("selected", not spec.get("is_optional", False)),
            ).save()
        return recalculate(item)
