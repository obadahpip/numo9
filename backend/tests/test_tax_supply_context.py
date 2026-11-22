"""G-02-T03 — the context builder: contact addresses, document ship-to, registrations, item hook
and account default feed the place-of-supply resolver.

Acceptance: a contact without a province falls back to the organisation's province with the
``missing_province`` flag.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pytest

from numo9.contacts.models import Address, AddressKind, Contact
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.orgsettings.models import RegistrationType, TaxRegistration
from numo9.orgsettings.service import get_settings
from numo9.tax.place_of_supply import (
    MISSING_PROVINCE,
    SOURCE_ACCOUNT,
    SOURCE_ITEM,
    SupplyAddress,
)
from numo9.tax.supply_context import build_context, resolve_line, supply_address
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db
DAY = dt.date(2026, 7, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(organisation):
        settings = get_settings(organisation)
        settings.physical_province = "ON"
        settings.save()
    load_template(organisation, "ON")
    return organisation


def customer(org: Organisation, name: str, **addresses: tuple[str, str]) -> Contact:
    with org_context(org):
        item = contact(org, name)
        for kind, (country, province) in addresses.items():
            Address(
                organisation=org,
                contact=item,
                kind=AddressKind(kind),
                country=country,
                province=province,
                city="Somewhere",
            ).save()
        return item


@dataclass
class Item:
    """The H-01 hook: anything with ``sales_tax_key`` / ``purchase_tax_key``."""

    sales_tax_key: str = ""
    purchase_tax_key: str = ""
    is_taxable: bool = True


def test_missing_province_falls_back_with_a_flag(org: Organisation) -> None:
    nobody = customer(org, "No Address Ltd.")
    resolution, version = resolve_line("sales", DAY, org, contact=nobody)
    assert resolution.code == "sales.ON.standard" and resolution.flags == {MISSING_PROVINCE}
    assert version is not None and version.code == "sales.ON.standard"


def test_billing_address_places_the_sale(org: Organisation) -> None:
    quebec = customer(org, "Boutique Laval", billing=("CA", "QC"))
    context = build_context("sales", DAY, org, contact=quebec)
    assert context.billing == SupplyAddress("CA", "QC") and context.home_province == "ON"
    resolution, _ = resolve_line("sales", DAY, org, contact=quebec)
    assert resolution.code == "sales.QC.gst"  # not QST-registered


def test_registrations_are_read(org: Organisation) -> None:
    with org_context(org):
        TaxRegistration(
            organisation=org, type=RegistrationType.QST, number="1234567890TQ0001"
        ).save()
    quebec = customer(org, "Boutique Laval", billing=("CA", "QC"))
    resolution, version = resolve_line("sales", DAY, org, contact=quebec)
    assert resolution.code == "sales.QC.standard"
    assert version is not None
    with org_context(org):
        assert version.components.count() == 2


def test_shipping_address_then_document_ship_to(org: Organisation) -> None:
    us = customer(org, "Acme Inc.", billing=("US", ""), shipping=("CA", "AB"))
    assert resolve_line("sales", DAY, org, contact=us)[0].code == "sales.AB.standard"
    on = resolve_line("sales", DAY, org, contact=us, ship_to={"country": "CA", "province": "ON"})
    assert on[0].code == "sales.ON.standard"
    export = customer(org, "Acme Export", billing=("US", ""))
    assert resolve_line("sales", DAY, org, contact=export)[0].code == "sales.zero_rated"


def test_item_hook_and_account_default(org: Organisation) -> None:
    on = customer(org, "Toronto Co.", billing=("CA", "ON"))
    resolution, version = resolve_line(
        "sales", DAY, org, contact=on, item=Item(sales_tax_key="sales.zero_rated")
    )
    assert resolution.source == SOURCE_ITEM and version is not None
    context = build_context("sales", DAY, org, item=Item(is_taxable=False))
    assert context.taxable is False
    with org_context(org):
        meals = Account.objects.get(code="6010")
    bc = customer(org, "Vancouver Catering", billing=("CA", "BC"))
    resolution, _ = resolve_line("purchase", DAY, org, contact=bc, account=meals)
    assert (resolution.code, resolution.source) == ("purchase.ON.standard.itc50", SOURCE_ACCOUNT)


def test_supply_address_shapes() -> None:
    assert supply_address(None) is None
    assert supply_address({"country": "ca", "province": "qc"}) == SupplyAddress("CA", "QC")
    assert supply_address({}) == SupplyAddress("CA", "")
    address = SupplyAddress("US", "")
    assert supply_address(address) is address
