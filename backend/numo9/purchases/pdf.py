"""Purchase order PDF (E-01-T09) on the document template system (A-10-T16, gap-43), like the
invoice (D-03a-T09): Letter, 1 in margins, the brand header with the buyer's legal name, address
and GST/HST program account, the branding theme's accent colour.

The PO shows the supplier and its address, the number (``Draft`` before approval), date, the
delivery block (deliver to, attention, delivery date, instructions), the lines (quantity, unit
price, discount, tax code, amount), tax per component, the total and notes. The language is the
supplier's (``Contact.language``).

``purchase_order_context(order)`` builds the data; ``render_purchase_order_pdf(order)`` → bytes.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _

from numo9.documents.pdf import render_pdf
from numo9.sales.pdf import _accent, _customer, _issuer
from numo9.tenancy.context import org_context

from .models import PurchaseOrder

TEMPLATE = "purchases/purchase_order.html"


def _result(order: PurchaseOrder) -> Any:
    from numo9.documents.posting import PreviewLine, result_for

    lines = list(order.lines.select_related("account", "tax_code").order_by("position", "pk"))
    return lines, result_for(
        "purchase_order",
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
        tax_mode=order.tax_mode,
        discount_type=order.discount_type,
        discount_value=order.discount_value,
    )


def purchase_order_context(order: PurchaseOrder) -> dict[str, Any]:
    with org_context(order.organisation):
        lines, result = _result(order)
        names: dict[str, str] = {}
        for line in lines:
            if line.tax_code is not None:
                for link in line.tax_code.components.select_related("component"):
                    names[link.component.key] = link.component.name
        return {
            "accent": _accent(order.organisation),
            "issuer": _issuer(order.organisation, order.date),
            "supplier": _customer(order),  # any document with a contact
            "document_number": order.number or _("Draft"),
            "draft": not order.number,
            "issue_date": order.date,
            "delivery_date": order.delivery_date,
            "delivery_address": order.delivery_address,
            "delivery_attention": order.delivery_attention,
            "delivery_instructions": order.delivery_instructions,
            "reference": order.reference,
            "tax_included": result.tax_included,
            "lines": [
                {
                    "description": line.description,
                    "quantity": f"{line.quantity.normalize():f}",
                    "unit": line.unit_price,
                    "discount_percent": (
                        f"{line.discount_value.normalize():f} %"
                        if line.discount_type == "percent" and line.discount_value
                        else ""
                    ),
                    "discount_amount": (
                        line.discount_value
                        if line.discount_type == "amount" and line.discount_value
                        else None
                    ),
                    "tax_code": line.tax_code.name if line.tax_code else "",
                    "amount": figures.net,
                }
                for line, figures in zip(lines, result.lines, strict=True)
            ],
            "subtotal": result.subtotal,
            "discount_total": result.discount_total,
            "taxes": [
                {"key": key, "name": names.get(key, key.upper()), "amount": amount}
                for key, amount in result.tax_by_component.items()
                if amount
            ],
            "total": result.total,
            "currency": order.currency,
            "notes": order.notes,
        }


def render_purchase_order_pdf(order: PurchaseOrder) -> bytes:
    return render_pdf(TEMPLATE, purchase_order_context(order), locale=order.contact.language)
