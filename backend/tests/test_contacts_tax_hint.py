"""B-01-T07 — province tax hint resolver, exposed for the tax engine (G-02).

Acceptance: table test of the 13 provinces and territories. Also: rates by date (Nova Scotia
15 % → 14 % on 1 April 2025), no hint for an unknown code or a date before the table, labels and
combined rates; a contact's hint comes from its billing address, else its shipping address,
never from a foreign address, and follows an address change at once.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from numo9.contacts.models import Address, AddressKind, Contact
from numo9.contacts.tax import (
    TAX_DEFAULT_BASIS,
    Regime,
    contact_province,
    contact_tax_hint,
    province_tax_hint,
)
from numo9.orgsettings.validators import Province
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

ON_DAY = date(2026, 11, 14)

#: province → (regime, code, components as (name, rate), combined rate) on ON_DAY.
EXPECTED: dict[str, tuple[str, str, list[tuple[str, str]], str]] = {
    "AB": (Regime.GST, "GST", [("GST", "5")], "5"),
    "BC": (Regime.GST_PST, "GST+PST", [("GST", "5"), ("PST", "7")], "12"),
    "MB": (Regime.GST_PST, "GST+RST", [("GST", "5"), ("RST", "7")], "12"),
    "NB": (Regime.HST, "HST15", [("HST", "15")], "15"),
    "NL": (Regime.HST, "HST15", [("HST", "15")], "15"),
    "NS": (Regime.HST, "HST14", [("HST", "14")], "14"),
    "NT": (Regime.GST, "GST", [("GST", "5")], "5"),
    "NU": (Regime.GST, "GST", [("GST", "5")], "5"),
    "ON": (Regime.HST, "HST13", [("HST", "13")], "13"),
    "PE": (Regime.HST, "HST15", [("HST", "15")], "15"),
    "QC": (Regime.GST_QST, "GST+QST", [("GST", "5"), ("QST", "9.975")], "14.975"),
    "SK": (Regime.GST_PST, "GST+PST", [("GST", "5"), ("PST", "6")], "11"),
    "YT": (Regime.GST, "GST", [("GST", "5")], "5"),
}


# ---- acceptance: the 13 provinces and territories ----------------------------------------------


def test_the_table_covers_every_province_and_territory() -> None:
    assert sorted(EXPECTED) == sorted(Province.values)


@pytest.mark.parametrize("province", sorted(EXPECTED))
def test_province_tax_hint(province: str) -> None:
    regime, code, components, combined = EXPECTED[province]
    hint = province_tax_hint(province, ON_DAY)
    assert hint is not None
    assert (hint.province, hint.regime, hint.code) == (province, regime, code)
    assert [(c.name, c.rate) for c in hint.components] == [
        (name, Decimal(rate)) for name, rate in components
    ]
    assert hint.combined_rate == Decimal(combined)


def test_examples_from_the_plan() -> None:
    assert province_tax_hint("QC", ON_DAY).code == "GST+QST"  # type: ignore[union-attr]
    assert province_tax_hint("ON", ON_DAY).code == "HST13"  # type: ignore[union-attr]
    assert province_tax_hint("BC", ON_DAY).code == "GST+PST"  # type: ignore[union-attr]


# ---- dates, unknown codes, labels ---------------------------------------------------------------


def test_rates_follow_the_date() -> None:
    before = province_tax_hint("NS", date(2025, 3, 31))
    after = province_tax_hint("NS", date(2025, 4, 1))
    assert before is not None and after is not None
    assert (before.code, before.combined_rate) == ("HST15", Decimal("15"))
    assert (after.code, after.combined_rate, after.effective_from) == (
        "HST14",
        Decimal("14"),
        date(2025, 4, 1),
    )


def test_no_hint_for_an_unknown_code_or_a_date_before_the_table() -> None:
    assert province_tax_hint("ZZ", ON_DAY) is None
    assert province_tax_hint("", ON_DAY) is None
    assert province_tax_hint("ON", date(2009, 1, 1)) is None


def test_lower_case_codes_and_today_by_default() -> None:
    hint = province_tax_hint(" qc ")
    assert hint is not None and hint.code == "GST+QST"


def test_labels_name_each_tax_and_rate() -> None:
    assert province_tax_hint("QC", ON_DAY).label == "GST 5 % + QST 9.975 %"  # type: ignore[union-attr]
    assert province_tax_hint("ON", ON_DAY).label == "HST 13 %"  # type: ignore[union-attr]
    assert TAX_DEFAULT_BASIS == "province"


# ---- a contact's hint ---------------------------------------------------------------------------


@pytest.fixture
def org(db: None) -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def add_address(item: Contact, kind: str, **fields: str) -> Address:
    a = Address(contact=item, kind=kind, **fields)
    a.save()
    return a


@pytest.mark.usefixtures("_active")
def test_a_quebec_contact_defaults_to_gst_and_qst(org: Organisation) -> None:
    erable = contact(org, "Érable Distribution inc.")
    add_address(erable, AddressKind.BILLING, city="Montréal", province="QC", postal_code="H2Y1C6")
    hint = contact_tax_hint(erable, ON_DAY)
    assert hint is not None and hint.code == "GST+QST"
    assert erable.province_tax_hint is not None
    assert erable.province_tax_hint.code == "GST+QST"


@pytest.mark.usefixtures("_active")
def test_billing_province_first_then_shipping(org: Organisation) -> None:
    item = contact(org, "Maple Supply Ltd.")
    assert contact_province(item) == "" and contact_tax_hint(item, ON_DAY) is None
    add_address(item, AddressKind.SHIPPING, province="BC")
    assert contact_province(item) == "BC"
    billing = add_address(item, AddressKind.BILLING, province="ON", postal_code="M5V 2T6")
    assert contact_tax_hint(item, ON_DAY).code == "HST13"  # type: ignore[union-attr]
    billing.province, billing.postal_code = "QC", "H2Y 1C6"
    billing.save()
    assert contact_tax_hint(item, ON_DAY).code == "GST+QST"  # type: ignore[union-attr]
    billing.soft_delete()
    assert contact_province(item) == "BC"


@pytest.mark.usefixtures("_active")
def test_no_hint_from_a_foreign_or_province_less_address(org: Organisation) -> None:
    item = contact(org, "Empire State Supplies")
    add_address(item, AddressKind.BILLING, region="NY", postal_code="10118", country="US")
    add_address(item, AddressKind.SHIPPING, city="Toronto")  # Canadian, no province yet
    assert contact_tax_hint(item, ON_DAY) is None
