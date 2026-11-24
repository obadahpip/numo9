"""Purchase orders for the E-01 tests: an Ontario organisation with the template chart, a
supplier, an owner and a buyer with purchase-order approval limits, and a ``po()`` builder."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.accounts.models import User
from numo9.contacts.models import Address, AddressKind
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.orgsettings.service import get_settings
from numo9.purchases.approvals import recalculate
from numo9.purchases.models import PurchaseOrder, PurchaseOrderLine
from numo9.rbac.models import ApprovalLimit
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact

DAY = dt.date(2026, 6, 15)


def member(org: Organisation, email: str, role: str, limit: str | None = None) -> User:
    user = User.objects.create_user(email, name=email.split("@")[0].title())
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    if limit is not None:
        with org_context(org):
            ApprovalLimit.objects.create(
                user=user, doc_type="purchase_order", max_amount=Decimal(limit)
            )
    return user


def purchase_books(name: str = "Refined Interiors Inc.") -> dict[str, Any]:
    org = Organisation.objects.create(name=name)
    with org_context(org):
        settings = get_settings(org)
        settings.physical_province = "ON"
        settings.save()
    load_template(org, "ON")
    with org_context(org):
        expense = Account.objects.filter(type="expense").order_by("code").first()
        supplier = contact(org, "Cedar Supply Co.", roles=["supplier"])
        Address(
            organisation=org,
            contact=supplier,
            kind=AddressKind.BILLING,
            country="CA",
            province="ON",
            city="Toronto",
        ).save()
        other = contact(org, "Maple Hardware Ltd", roles=["supplier"])
    return {
        "org": org,
        "expense": expense,
        "supplier": supplier,
        "other": other,
        "owner": member(org, "owner@refined.ca", "owner", "100000"),
        "buyer": member(org, "buyer@refined.ca", "admin", "5000"),
        "clerk": member(org, "clerk@refined.ca", "admin"),
    }


def po(
    books: dict[str, Any],
    lines: list[tuple[str, str]],
    *,
    tax: str = "",
    supplier: str = "supplier",
    date: dt.date = DAY,
    account: Any = None,
    user: Any = None,
    **fields: Any,
) -> PurchaseOrder:
    """A draft PO: ``lines`` = (quantity, unit price); ``tax`` = a purchase tax code key."""
    org = books["org"]
    with org_context(org):
        order = PurchaseOrder(
            organisation=org,
            contact=books[supplier],
            date=date,
            created_by=user,
            tax_mode="no_tax" if not tax else "exclusive",
            **fields,
        )
        order.save()
        for position, (quantity, price) in enumerate(lines):
            PurchaseOrderLine(
                organisation=org,
                document=order,
                position=position,
                description=f"Line {position + 1}",
                quantity=Decimal(quantity),
                unit_price=Decimal(price),
                account=account or books["expense"],
                tax_code=code_for(tax, "purchase", date, org) if tax else None,
            ).save()
        return recalculate(order)
