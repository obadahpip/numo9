"""Province tax hint (B-01-T07): which sales taxes apply where a contact is.

    province_tax_hint("QC").code        # "GST+QST"
    province_tax_hint("ON").code        # "HST13"
    contact_tax_hint(contact)           # from the contact's address province, or None

A contact's default tax follows its province (``tax_default_basis = "province"``): a Quebec
customer defaults to GST + QST, an Ontario customer to HST 13 %, a British Columbia customer to
GST + PST. Phase 0 only names the regime; the tax engine (G-02) resolves the hint to the
organisation's tax codes, applies place-of-supply rules (ship-to province, services, exports) and
computes the amounts. The hint is derived, never stored, so a changed address changes it at once.

Rates are general rates with the date they took effect (CRA GST/HST rates table; Revenu Québec;
the BC, Saskatchewan and Manitoba finance ministries — checked October 2026). A date before a
province's first row has no hint. Rate changes are added as new rows (e.g. Nova Scotia's HST fell
from 15 % to 14 % on 1 April 2025).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils import timezone

from numo9.orgsettings.validators import Province

if TYPE_CHECKING:
    from .models import Contact

#: How a contact's default tax is chosen (Phase 0: from its province).
TAX_DEFAULT_BASIS = "province"


class Regime:
    GST = "gst"  # federal GST only (AB and the territories)
    HST = "hst"  # harmonized sales tax (ON, NS, NB, NL, PE)
    GST_PST = "gst_pst"  # GST + a separate provincial sales tax (BC PST, SK PST, MB RST)
    GST_QST = "gst_qst"  # GST + Quebec sales tax


@dataclass(frozen=True)
class TaxComponent:
    """One tax of a regime: ``name`` (GST, HST, PST, RST, QST) and its general rate in %."""

    name: str
    rate: Decimal
    authority: str  # who administers it: CRA, Revenu Québec, a provincial ministry


@dataclass(frozen=True)
class ProvinceTaxHint:
    province: str
    regime: str
    code: str  # "GST", "HST13", "HST14", "HST15", "GST+PST", "GST+RST", "GST+QST"
    components: tuple[TaxComponent, ...]
    effective_from: date

    @property
    def combined_rate(self) -> Decimal:
        return sum((c.rate for c in self.components), Decimal("0"))

    @property
    def label(self) -> str:
        """``GST 5 % + QST 9.975 %`` — for a hint next to the address."""
        return " + ".join(f"{c.name} {_percent(c.rate)} %" for c in self.components)


def _percent(rate: Decimal) -> str:
    return format(rate.normalize(), "f")  # 9.975, 13, 5


CRA = "CRA"
_GST = TaxComponent("GST", Decimal("5"), CRA)


def _hst(rate: str) -> tuple[TaxComponent, ...]:
    return (TaxComponent("HST", Decimal(rate), CRA),)


#: (province, regime, code, components, effective from) — general rates, newest last per province.
_TABLE: tuple[tuple[str, str, str, tuple[TaxComponent, ...], date], ...] = (
    (Province.AB, Regime.GST, "GST", (_GST,), date(2008, 1, 1)),
    (Province.NT, Regime.GST, "GST", (_GST,), date(2008, 1, 1)),
    (Province.NU, Regime.GST, "GST", (_GST,), date(2008, 1, 1)),
    (Province.YT, Regime.GST, "GST", (_GST,), date(2008, 1, 1)),
    (Province.ON, Regime.HST, "HST13", _hst("13"), date(2010, 7, 1)),
    (Province.NS, Regime.HST, "HST15", _hst("15"), date(2010, 7, 1)),
    (Province.NS, Regime.HST, "HST14", _hst("14"), date(2025, 4, 1)),
    (Province.NB, Regime.HST, "HST15", _hst("15"), date(2016, 7, 1)),
    (Province.NL, Regime.HST, "HST15", _hst("15"), date(2016, 7, 1)),
    (Province.PE, Regime.HST, "HST15", _hst("15"), date(2016, 10, 1)),
    (
        Province.BC,
        Regime.GST_PST,
        "GST+PST",
        (_GST, TaxComponent("PST", Decimal("7"), "BC Ministry of Finance")),
        date(2013, 4, 1),
    ),
    (
        Province.SK,
        Regime.GST_PST,
        "GST+PST",
        (_GST, TaxComponent("PST", Decimal("6"), "Saskatchewan Ministry of Finance")),
        date(2017, 3, 23),
    ),
    (
        Province.MB,
        Regime.GST_PST,
        "GST+RST",
        (_GST, TaxComponent("RST", Decimal("7"), "Manitoba Finance")),
        date(2019, 7, 1),
    ),
    (
        Province.QC,
        Regime.GST_QST,
        "GST+QST",
        (_GST, TaxComponent("QST", Decimal("9.975"), "Revenu Québec")),
        date(2013, 1, 1),
    ),
)


def province_tax_hint(province: str, on: date | None = None) -> ProvinceTaxHint | None:
    """The sales-tax regime of a province or territory on a date (today by default); ``None``
    for an unknown code or a date before the table starts."""
    code = (province or "").strip().upper()
    day = on or timezone.localdate()
    rows = [row for row in _TABLE if row[0] == code and row[4] <= day]
    if not rows:
        return None
    prov, regime, hint_code, components, effective_from = max(rows, key=lambda row: row[4])
    return ProvinceTaxHint(str(prov), regime, hint_code, components, effective_from)


def contact_province(contact: Contact) -> str:
    """The province a contact's default tax comes from: its billing address, else its shipping
    address — Canadian addresses with a province only; empty when there is none."""
    from .models import AddressKind

    addresses = {
        a.kind: a
        for a in contact.addresses.filter(deleted_at__isnull=True)
        if a.is_canadian and a.province
    }
    for kind in (AddressKind.BILLING, AddressKind.SHIPPING):
        if kind in addresses:
            return addresses[kind].province
    return ""


def contact_tax_hint(contact: Contact, on: date | None = None) -> ProvinceTaxHint | None:
    """The tax hint of a contact (``None`` without a Canadian province: G-02 then flags
    ``missing_province`` or applies export rules)."""
    return province_tax_hint(contact_province(contact), on)
