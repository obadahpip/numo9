"""G-02-T10 — gap tests of place-of-supply defaulting through ``POST tax/resolve`` (the editors'
call):

- gap-09: no line needs a manual pick — an Ontario customer gets HST 13 %, a US customer
  zero-rated, a Quebec customer GST + QST once QST-registered (GST only before), each with the
  explanation the "auto" chip shows; never "last used".
- gap-45: purchases default from the expense account's code, then the supplier's province — an
  expense account with an HST default and an Ontario supplier → HST 13 % purchase code; a
  supplier in Quebec with an account without its own code → the Quebec purchase rate.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.contacts.models import Address, AddressKind
from numo9.ledger.models import Account
from numo9.orgsettings.models import TaxRegistration
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.contact_helpers import contact
from tests.sales_helpers import sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = sales_books()
    org = books["org"]
    owner = User.objects.create_user("owner@refined.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    with org_context(org):
        us = contact(org, "Boston Buyer LLC", roles=["customer"])
        Address(organisation=org, contact=us, kind=AddressKind.BILLING, country="US").save()
        quebec = contact(org, "Fournitures Laval", roles=["supplier"])
        Address(
            organisation=org, contact=quebec, kind=AddressKind.BILLING, country="CA", province="QC"
        ).save()
        hst_default = Account.objects.filter(
            type="expense", default_tax_key="purchase.ON.standard"
        ).first()
        plain = Account.objects.filter(type="expense", default_tax_key="").order_by("code").first()
    client = Client()
    client.force_login(owner)
    return {
        **books,
        "us": us,
        "quebec": quebec,
        "hst_default": hst_default,
        "plain": plain,
        "client": client,
    }


def resolve(ctx: dict[str, Any], side: str, contact_id: Any, account: Any = None) -> dict[str, Any]:
    body = {
        "side": side,
        "date": "2026-06-15",
        "contact": str(contact_id),
        "lines": [{"account": str(account.public_id) if account else None}],
    }
    answer = ctx["client"].post(
        f"/api/v1/o/{ctx['org'].public_id}/tax/resolve", body, content_type="application/json"
    )
    assert answer.status_code == 200, answer.content
    line: dict[str, Any] = answer.json()["lines"][0]
    return line


@pytest.mark.gap("gap-09")
def test_gap_09_no_manual_pick_per_line(ctx: dict[str, Any]) -> None:
    on = resolve(ctx, "sales", ctx["customers"]["ON"].public_id, ctx["revenue"])
    assert (on["key"], on["explanation"], on["auto"]) == ("sales.ON.standard", "tax.pos.hst", True)
    us = resolve(ctx, "sales", ctx["us"].public_id, ctx["revenue"])
    assert (us["key"], us["explanation"]) == ("sales.zero_rated", "tax.pos.export")
    qc = resolve(ctx, "sales", ctx["customers"]["QC"].public_id, ctx["revenue"])
    assert (qc["key"], qc["explanation"]) == ("sales.QC.gst", "tax.pos.gst_unregistered_qst")
    with org_context(ctx["org"]):
        TaxRegistration(
            organisation=ctx["org"],
            type="qst",
            number="1234567890TQ0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
    qc = resolve(ctx, "sales", ctx["customers"]["QC"].public_id, ctx["revenue"])
    assert (qc["key"], qc["explanation"]) == ("sales.QC.standard", "tax.pos.gst_qst")
    again = resolve(ctx, "sales", ctx["customers"]["ON"].public_id, ctx["revenue"])
    assert again["key"] == "sales.ON.standard"  # never "last used"


@pytest.mark.gap("gap-45")
def test_gap_45_purchases_from_the_account_then_the_supplier(ctx: dict[str, Any]) -> None:
    hst = resolve(ctx, "purchase", ctx["quebec"].public_id, ctx["hst_default"])
    assert (hst["key"], hst["source"]) == ("purchase.ON.standard", "account")
    assert hst["tax_code"]["code"] == "purchase.ON.standard"
    by_province = resolve(ctx, "purchase", ctx["quebec"].public_id)
    assert (by_province["key"], by_province["explanation"]) == (
        "purchase.QC.standard",
        "tax.pos.supplier_province",
    )
