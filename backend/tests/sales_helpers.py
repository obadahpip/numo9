"""Invoices for the D-03a tests: an Ontario organisation with the template chart and tax table,
customers in Ontario and British Columbia, and a ``draft()`` builder."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.contacts.models import Address, AddressKind
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.orgsettings.service import get_settings
from numo9.sales.models import Invoice, InvoiceLine
from numo9.sales.posting import recalculate
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

DAY = dt.date(2026, 6, 15)


def sales_books(name: str = "Refined Interiors Inc.") -> dict[str, Any]:
    org = Organisation.objects.create(name=name)
    with org_context(org):
        settings = get_settings(org)
        settings.physical_province = "ON"
        settings.save()
    load_template(org, "ON")
    with org_context(org):
        # An Ontario chart has no PST or QST control accounts: an Ontario seller registered in
        # BC and Quebec adds them (the BC and QC templates carry them).
        for code, role, name in (
            ("2215", "pst_payable", "PST payable"),
            ("2225", "qst_payable", "QST payable"),
        ):
            if not Account.objects.filter(system_role=role).exists():
                Account(
                    organisation=org,
                    code=code,
                    name_i18n={"en-ca": name},
                    type="liability",
                    subtype="sales_tax_control",
                    system_role=role,
                ).save()
        revenue = Account.objects.filter(subtype="revenue").order_by("code").first()
        customers = {}
        for province in ("ON", "BC", "QC"):
            customer = contact(org, f"{province} Customer Ltd", roles=["customer"])
            Address(
                organisation=org,
                contact=customer,
                kind=AddressKind.BILLING,
                country="CA",
                province=province,
                city="Somewhere",
            ).save()
            customers[province] = customer
    return {"org": org, "revenue": revenue, "customers": customers}


def draft(
    books: dict[str, Any],
    lines: list[tuple[str, str, str]],
    *,
    province: str = "ON",
    date: dt.date = DAY,
    **fields: Any,
) -> Invoice:
    """A draft invoice: ``lines`` = (quantity, unit price, tax code key)."""
    org = books["org"]
    with org_context(org):
        invoice = Invoice(
            organisation=org, contact=books["customers"][province], date=date, **fields
        )
        invoice.save()
        for position, (quantity, price, key) in enumerate(lines):
            InvoiceLine(
                organisation=org,
                document=invoice,
                position=position,
                description=f"Line {position + 1}",
                quantity=Decimal(quantity),
                unit_price=Decimal(price),
                account=books["revenue"],
                tax_code=code_for(key, "sales", date, org) if key else None,
            ).save()
        return recalculate(invoice)  # the editor saves the server's figures
