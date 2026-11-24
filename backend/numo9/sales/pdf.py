"""Invoice PDF (D-03a-T09) on the one document template system (A-10-T16, gap-43): Letter, 1 in
margins, the brand header with the issuer's legal name, address and GST/HST program account.

The invoice adds: the organisation's **branding theme** (its accent colour from its email
branding, A-07-T04 — black when none; logos are drawn only from ``data:`` URIs, the renderer
fetches nothing), the customer and billing address, number (``Draft`` before approval), dates and
terms, the lines (quantity, unit price, discount, tax code, amount), **tax per component** (GST,
HST, PST, QST — never one lumped "Tax"), the totals and amount due, the **QST number** when the
organisation is registered in Quebec, notes and terms, and a **pay-advice** slip to tear off and
send back with a cheque. The language is the customer's (``Contact.language``).

``invoice_context(invoice)`` builds the data; ``sample_invoice_context()`` is the Canadian sample
the theme preview uses (Refined Interiors Inc., Toronto, billing Maple Leaf Supply Ltd., HST 13 %);
``render_invoice_pdf(invoice)`` → PDF bytes.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from numo9.documents.pdf import render_pdf
from numo9.documents.sample_data import sample_context
from numo9.tenancy.context import org_context

from .models import Invoice

TEMPLATE = "sales/invoice.html"
DEFAULT_ACCENT = "#111111"
COLOUR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _registration(organisation: Any, kind: str, day: dt.date) -> str:
    from numo9.orgsettings.models import RegistrationStatus, TaxRegistration
    from numo9.orgsettings.validators import display_registration_number

    found = (
        TaxRegistration.objects.filter(organisation=organisation, type=kind)
        .exclude(status=RegistrationStatus.CLOSED)
        .order_by("-effective_from")
    )
    for row in found:
        if (row.effective_from is None or row.effective_from <= day) and (
            row.effective_to is None or row.effective_to >= day
        ):
            return display_registration_number(kind, row.number)
    return ""


def _accent(organisation: Any) -> str:
    from numo9.notifications.models import OrganisationBranding

    branding = OrganisationBranding._base_manager.filter(organisation=organisation).first()
    colour = getattr(branding, "colour", "") or ""
    return colour if COLOUR.match(colour) else DEFAULT_ACCENT


def _issuer(organisation: Any, day: dt.date) -> dict[str, Any]:
    from numo9.orgsettings.service import get_settings

    settings = get_settings(organisation)
    prefix = "mailing" if settings.mailing_line1 else "physical"
    return {
        "legal_name": settings.legal_name or settings.display_name or organisation.name,
        "address_line": " ".join(
            x
            for x in (getattr(settings, f"{prefix}_line1"), getattr(settings, f"{prefix}_line2"))
            if x
        ),
        "city": getattr(settings, f"{prefix}_city"),
        "province": getattr(settings, f"{prefix}_province"),
        "postal_code": getattr(settings, f"{prefix}_postal_code"),
        "business_number": _registration(organisation, "rt", day),
        "qst_number": _registration(organisation, "qst", day),
        "phone": settings.phone,
        "email": settings.email,
    }


def _customer(invoice: Invoice) -> dict[str, Any]:
    from numo9.contacts.models import AddressKind

    contact = invoice.contact
    address = (
        contact.addresses.filter(kind=AddressKind.BILLING, deleted_at__isnull=True).first()
        if hasattr(contact, "addresses")
        else None
    )
    return {
        "legal_name": contact.legal_name or contact.display_name,
        "address_line": " ".join(x for x in (address.line1, address.line2) if x) if address else "",
        "city": address.city if address else "",
        "province": address.province if address else "",
        "postal_code": address.postal_code if address else "",
    }


def invoice_context(invoice: Invoice) -> dict[str, Any]:
    from .posting import invoice_preview

    with org_context(invoice.organisation):
        result = invoice_preview(invoice).result
        lines = list(invoice.lines.select_related("tax_code").order_by("position", "pk"))
        names = {}
        for line in lines:
            if line.tax_code is not None:
                for link in line.tax_code.components.select_related("component"):
                    names[link.component.key] = link.component.name
        return {
            "accent": _accent(invoice.organisation),
            "issuer": _issuer(invoice.organisation, invoice.date),
            "customer": _customer(invoice),
            "document_number": invoice.number or _("Draft"),
            "draft": not invoice.number,
            "issue_date": invoice.date,
            "due_date": invoice.due_date,
            "terms": invoice.terms.name if invoice.terms_id and invoice.terms else "",
            "reference": invoice.reference,
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
            "amount_paid": invoice.amount_paid,
            "amount_due": result.total - Decimal(invoice.amount_paid),
            "currency": invoice.currency,
            "notes": invoice.notes,
        }


def sample_invoice_context() -> dict[str, Any]:
    """The theme preview's invoice: the Canadian sample of the template baseline (gap-43)."""
    base = sample_context()
    return {
        **base,
        "accent": DEFAULT_ACCENT,
        "document_number": "INV-0042",
        "draft": False,
        "terms": _("Net 30"),
        "reference": "PO 7781",
        "tax_included": False,
        "lines": [
            {**line, "discount_percent": "", "discount_amount": None, "tax_code": "HST 13 % (ON)"}
            for line in base["lines"]
        ],
        "discount_total": Decimal("0.00"),
        "taxes": [{"key": "hst_on", "name": "HST (ON) 13 %", "amount": base["tax"]}],
        "amount_paid": Decimal("0.00"),
        "amount_due": base["total"],
        "currency": "CAD",
        "notes": _("Thank you for your business. Payment by cheque or e-Transfer."),
        "issuer": {**base["issuer"], "qst_number": ""},
    }


def render_invoice_pdf(invoice: Invoice) -> bytes:
    return render_pdf(TEMPLATE, invoice_context(invoice), locale=invoice.contact.language)
