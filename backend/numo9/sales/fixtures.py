"""Invoice fixtures (D-03a-T18): 50 invoices across the provinces and territories, and their PDFs.

``build_invoice_fixtures(organisation, user)`` creates, in an organisation whose chart is loaded
(C-01 template) and that is registered for GST/HST:

- one customer per province and territory (``Fixture customer — <code>``), billed there, so the
  place-of-supply rules (G-02) pick each one's tax: HST (ON, NB, NL, NS, PE), GST + PST (BC, MB,
  SK), GST + QST (QC), GST alone (AB, NT, NU, YT);
- **50 invoices**, round-robin over the 13 customers, dated one or two days apart from
  ``start``, each with one to three lines — the standard rate, plus zero-rated (basic groceries)
  and exempt lines on every fourth and fifth invoice, a 10 % discount on every sixth;
- a deterministic mix of statuses: every invoice is approved (it posts, D-03a-T03) except each
  seventh, which stays a **draft**; each tenth approved invoice is then **voided** (D-03a-T07).

The amounts are fixed (``quantity`` and ``unit price`` follow the invoice's position), so the
totals are the same on every run — the snapshot test pins them. A Manitoba or Saskatchewan sale
needs a PST control account; the builder adds the PST and QST control accounts the chart lacks
(an Ontario chart has neither), as an organisation registered in those provinces would.

``render_pdf_fixtures(invoices, directory)`` writes one PDF per province (its first approved
invoice) — the PDF fixtures QA compares with the client's own invoice samples. Command:
``python manage.py seed_invoice_fixtures <org public id> [--user EMAIL] [--pdf-dir DIR]``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any

from numo9.tenancy.context import org_context

from .models import Invoice, InvoiceLine, InvoiceStatus

COUNT = 50
START = dt.date(2026, 4, 1)
#: Every province and territory, in the order the invoices go round.
PROVINCES: tuple[str, ...] = (
    "ON",
    "QC",
    "BC",
    "AB",
    "MB",
    "SK",
    "NS",
    "NB",
    "NL",
    "PE",
    "YT",
    "NT",
    "NU",
)
CITIES = {
    "ON": "Toronto",
    "QC": "Montréal",
    "BC": "Vancouver",
    "AB": "Calgary",
    "MB": "Winnipeg",
    "SK": "Regina",
    "NS": "Halifax",
    "NB": "Moncton",
    "NL": "St. John's",
    "PE": "Charlottetown",
    "YT": "Whitehorse",
    "NT": "Yellowknife",
    "NU": "Iqaluit",
}
CONTROL_ACCOUNTS = (
    ("2215", "pst_payable", "PST payable"),
    ("2225", "qst_payable", "QST payable"),
)
DRAFT_EVERY = 7
VOID_EVERY = 10


def _ensure_controls(organisation: Any) -> None:
    from numo9.ledger.models import Account

    for code, role, name in CONTROL_ACCOUNTS:
        if not Account.objects.filter(system_role=role).exists():
            Account(
                organisation=organisation,
                code=code,
                name_i18n={"en-ca": name},
                type="liability",
                subtype="sales_tax_control",
                system_role=role,
            ).save()


def _customer(organisation: Any, province: str) -> Any:
    from numo9.contacts.models import Address, AddressKind, Contact

    name = f"Fixture customer — {province}"
    found = Contact.objects.filter(display_name=name, deleted_at__isnull=True).first()
    if found is not None:
        return found
    customer = Contact(
        organisation=organisation,
        display_name=name,
        roles=["customer"],
        language="fr-ca" if province == "QC" else "en-ca",
    )
    customer.save()
    Address(
        organisation=organisation,
        contact=customer,
        kind=AddressKind.BILLING,
        country="CA",
        province=province,
        city=CITIES[province],
        line1=f"{100 + PROVINCES.index(province)} Main Street",
    ).save()
    return customer


def _lines(position: int, province: str) -> list[tuple[str, Decimal, Decimal, str, Decimal]]:
    """(description, quantity, unit price, tax code, discount %) of invoice ``position``."""
    quantity = Decimal(1 + position % 4)
    price = Decimal(75 + 25 * (position % 9)).quantize(Decimal("0.01"))
    discount = Decimal("10") if position % 6 == 5 else Decimal("0")
    lines = [("Design consultation", quantity, price, f"sales.{province}.standard", discount)]
    if position % 4 == 3:
        lines.append(
            ("Basic groceries", Decimal("2"), Decimal("12.50"), "sales.zero_rated", Decimal(0))
        )
    if position % 5 == 4:
        lines.append(("Exempt service", Decimal("1"), Decimal("40.00"), "sales.exempt", Decimal(0)))
    return lines


def build_invoice_fixtures(
    organisation: Any, user: Any, *, count: int = COUNT, start: dt.date = START
) -> list[Invoice]:
    """The fixture invoices (module docstring), oldest first."""
    from numo9.documents.models import DiscountType
    from numo9.ledger.models import Account
    from numo9.tax.resolver import code_for

    from .posting import approve, recalculate, void

    with org_context(organisation):
        _ensure_controls(organisation)
        revenue = Account.objects.filter(subtype="revenue").order_by("code").first()
        if revenue is None:
            raise ValueError("Load a chart of accounts before building invoice fixtures.")
        customers = {p: _customer(organisation, p) for p in PROVINCES}
    invoices: list[Invoice] = []
    approved = 0
    for position in range(count):
        province = PROVINCES[position % len(PROVINCES)]
        day = start + dt.timedelta(days=position + position // 3)
        with org_context(organisation):
            invoice = Invoice(
                organisation=organisation,
                contact=customers[province],
                date=day,
                due_date=day + dt.timedelta(days=30),
                reference=f"PO-{7000 + position}",
                notes="Thank you for your business.",
            )
            invoice.save()
            for line_no, (text, quantity, price, key, discount) in enumerate(
                _lines(position, province)
            ):
                InvoiceLine(
                    organisation=organisation,
                    document=invoice,
                    position=line_no,
                    description=text,
                    quantity=quantity,
                    unit_price=price,
                    discount_type=DiscountType.PERCENT if discount else DiscountType.NONE,
                    discount_value=discount,
                    account=revenue,
                    tax_code=code_for(key, "sales", day, organisation),
                ).save()
            invoice = recalculate(invoice)
        if position % DRAFT_EVERY != DRAFT_EVERY - 1:
            invoice = approve(invoice, user)
            approved += 1
            if approved % VOID_EVERY == 0:
                invoice = void(invoice, user, reason="Fixture: issued in error")
        invoices.append(invoice)
    return invoices


def render_pdf_fixtures(invoices: list[Invoice], directory: Path) -> list[Path]:
    """One PDF per province: its first approved (not void) invoice. Returns the files written."""
    from .pdf import render_invoice_pdf

    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    seen: set[str] = set()
    for invoice in invoices:
        if invoice.status == InvoiceStatus.VOID or not invoice.number:
            continue
        with org_context(invoice.organisation):
            province = invoice.contact.addresses.filter(kind="billing").values_list(
                "province", flat=True
            )[0]
            if province in seen:
                continue
            seen.add(province)
            path = directory / f"invoice-{province}-{invoice.number}.pdf"
            path.write_bytes(render_invoice_pdf(invoice))
        written.append(path)
    return written
