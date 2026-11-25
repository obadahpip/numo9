"""Copy to invoice / quote (D-03a-T10): a new **draft** with the same header and identical lines.

``copy_document(source, to, user, date=None)`` — ``source`` an ``Invoice`` or a ``Quote``, ``to``
``"invoice"`` or ``"quote"``:

- the header: the contact, reference, currency, how amounts are entered (tax mode), the document
  discount, the ship-to and the notes; dated ``date`` (the organisation's today by default); an
  invoice copy has no number until it is approved and no due date until the editor sets it from
  the terms; a quote copy takes its ``QU-`` number and expires after the organisation's default
  validity (30 days);
- the lines, in order: item, description, quantity, unit price, line discount, account, tax code,
  the "changed from default" flag and tracking — identical. From a quote to an invoice, only the
  lines that count (the selected options, D-02-T03); a quote to a quote keeps every line with its
  optional / alternative flags and selection;
- the figures are recalculated (server-authoritative) and the copy is audited with its source
  (``sales.invoice.copied`` / ``sales.quote.copied``).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction

from numo9.tenancy.context import org_context

from .models import Invoice, InvoiceLine, Quote, QuoteLine

QUOTE_VALID_DAYS = 30
HEADER = (
    "contact",
    "reference",
    "currency",
    "tax_mode",
    "discount_type",
    "discount_value",
    "ship_to_country",
    "ship_to_province",
    "notes",
)
LINE = (
    "position",
    "item",
    "description",
    "quantity",
    "unit_price",
    "discount_type",
    "discount_value",
    "account",
    "tax_code",
    "tax_overridden",
    "tracking",
)


def _lines(source: Any, to: str) -> list[Any]:
    lines = list(source.lines.order_by("position", "pk"))
    if isinstance(source, Quote) and to == "invoice":
        from .quotes import counted

        return [line for line, take in zip(lines, counted(lines), strict=True) if take]
    return lines


def copy_document(source: Any, to: str, user: Any = None, *, date: dt.date | None = None) -> Any:
    from numo9.audit import service as audit

    from .posting import recalculate as recalculate_invoice
    from .quotes import create_quote, local_today
    from .quotes import recalculate as recalculate_quote

    if to not in ("invoice", "quote"):
        raise ValueError(f"Copy to an invoice or a quote, not {to!r}.")
    organisation = source.organisation
    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(organisation), transaction.atomic():
        day = date or local_today(organisation)
        header = {name: getattr(source, name) for name in HEADER}
        if to == "invoice":
            copy: Any = Invoice(organisation=organisation, date=day, created_by=person, **header)
            copy.save()
        else:
            copy = create_quote(
                organisation,
                date=day,
                expiry_date=day + dt.timedelta(days=QUOTE_VALID_DAYS),
                title=getattr(source, "title", ""),
                summary=getattr(source, "summary", ""),
                created_by=person,
                **header,
            )
        line_model = InvoiceLine if to == "invoice" else QuoteLine
        for n, line in enumerate(_lines(source, to)):
            values = {name: getattr(line, name) for name in LINE}
            values["position"] = n
            values["tracking"] = dict(line.tracking or {})
            if to == "quote" and isinstance(line, QuoteLine):
                values.update(
                    is_optional=line.is_optional,
                    alternative_group=line.alternative_group,
                    selected=line.selected,
                )
            line_model(organisation=organisation, document=copy, **values).save()
        copy = recalculate_invoice(copy) if to == "invoice" else recalculate_quote(copy)
        kind = "invoice" if to == "invoice" else "quote"
        audit.record(
            f"sales.{kind}.copied",
            obj=copy,
            meta={
                "from": f"{type(source).__name__.lower()} {source.number or source.public_id}",
                "lines": copy.lines.count(),
            },
            actor=person,
        )
        return copy
