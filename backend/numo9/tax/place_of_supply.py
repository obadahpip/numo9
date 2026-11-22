"""Place-of-supply resolver (G-02-T02): the default tax code of a document line.

``resolve(context)`` is a pure function of a ``SupplyContext`` — side, date, the organisation's
home province and registrations, the contact's addresses, the line's ship-to and the item /
account / contact defaults — and returns a ``Resolution``: the code key, where it came from, an
explanation message key with its parameters (the "auto" chip's tooltip: "Ontario customer →
HST 13 %"), the province of supply, flags (``missing_province``) and warnings
(``tax.pos.pst_unregistered`` — G-02-T04). It reads no
database and never "last used"; the same context always gives the same code. The decision
table is ``docs/specs/tax-place-of-supply.md``.

Precedence (business rule): line override > item tax setting > contact explicit default >
place-of-supply resolver > account default. On purchases the account default comes before the
supplier's province (gap-45).

The key is resolved to the code version in force on the date by ``tax.resolver.code_for``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import Any

SALES = "sales"
PURCHASE = "purchase"

HST_PROVINCES = frozenset({"ON", "NS", "NB", "NL", "PE"})
GST_PROVINCES = frozenset({"AB", "NT", "NU", "YT"})
#: Provinces with a separate provincial sales tax, and the registration that collects it.
PROVINCIAL_REGISTRATION = {"BC": "pst_bc", "SK": "pst_sk", "MB": "rst_mb", "QC": "qst"}
PROVINCES = HST_PROVINCES | GST_PROVINCES | frozenset(PROVINCIAL_REGISTRATION)

# Where the code came from.
SOURCE_OVERRIDE = "override"
SOURCE_ITEM = "item"
SOURCE_CONTACT = "contact"
SOURCE_PLACE = "place_of_supply"
SOURCE_ACCOUNT = "account"
SOURCE_NONE = "none"

# Flags.
MISSING_PROVINCE = "missing_province"

# Warnings (G-02-T04).
PST_UNREGISTERED = "tax.pos.pst_unregistered"
#: Provinces whose separate PST/RST the organisation must register for to collect it.
PST_PROVINCES = frozenset({"BC", "SK", "MB"})


@dataclass(frozen=True)
class SupplyAddress:
    """The tax-relevant part of an address: country (ISO two letters) and province."""

    country: str = "CA"
    province: str = ""

    @property
    def known(self) -> bool:
        """An address that places the supply: a foreign country, or a Canadian province."""
        country = (self.country or "CA").upper()
        return country != "CA" or (self.province or "").upper() in PROVINCES


@dataclass(frozen=True)
class Registration:
    """One of the organisation's registrations (A-05-T03) as the resolver sees it."""

    type: str
    status: str = "active"
    effective_from: dt.date | None = None
    effective_to: dt.date | None = None

    def active_on(self, day: dt.date) -> bool:
        return (
            self.status == "active"
            and (self.effective_from is None or self.effective_from <= day)
            and (self.effective_to is None or day <= self.effective_to)
        )


@dataclass(frozen=True)
class SupplyContext:
    side: str
    date: dt.date
    home_province: str = ""
    registrations: tuple[Registration, ...] = ()
    ship_to: SupplyAddress | None = None
    billing: SupplyAddress | None = None
    line_override: str = ""
    item_code: str = ""
    contact_default: str = ""
    account_default: str = ""
    #: False for a line whose item is zero-rated or exempt (no PST warning on it, G-02-T04).
    taxable: bool = True


@dataclass(frozen=True)
class Resolution:
    code: str
    source: str
    explanation: str
    params: dict[str, Any] = field(default_factory=dict)
    province: str = ""
    flags: frozenset[str] = frozenset()
    warnings: tuple[str, ...] = ()

    @property
    def auto(self) -> bool:
        """True when the code is a default (the "auto" chip), False for a line override."""
        return self.source != SOURCE_OVERRIDE


def registered(context: SupplyContext, kind: str) -> bool:
    return any(r.type == kind and r.active_on(context.date) for r in context.registrations)


def _side_key(key: str, side: str) -> str:
    """``key`` when it belongs to ``side`` (a sales line never takes a purchase code)."""
    return key if key and key.startswith(f"{side}.") else ""


def place(context: SupplyContext) -> tuple[SupplyAddress | None, frozenset[str]]:
    """The address that places the supply: ship-to, else billing, else the organisation's home
    province with ``missing_province``; None when even the home province is unknown."""
    for address in (context.ship_to, context.billing):
        if address is not None and address.known:
            return (
                SupplyAddress((address.country or "CA").upper(), (address.province or "").upper()),
                frozenset(),
            )
    home = (context.home_province or "").upper()
    if home in PROVINCES:
        return SupplyAddress("CA", home), frozenset({MISSING_PROVINCE})
    return None, frozenset({MISSING_PROVINCE})


def _sales(context: SupplyContext, where: SupplyAddress) -> tuple[str, str, dict[str, Any]]:
    """(code, explanation key, params) for a sale placed at ``where`` (decision table §3)."""
    if where.country != "CA":
        return "sales.zero_rated", "tax.pos.export", {"country": where.country}
    province = where.province
    params = {"province": province}
    if province in HST_PROVINCES:
        return f"sales.{province}.standard", "tax.pos.hst", params
    if province in GST_PROVINCES:
        return f"sales.{province}.standard", "tax.pos.gst", params
    kind = PROVINCIAL_REGISTRATION[province]
    if registered(context, kind):
        explanation = "tax.pos.gst_qst" if province == "QC" else "tax.pos.gst_pst"
        return f"sales.{province}.standard", explanation, params
    explanation = (
        "tax.pos.gst_unregistered_qst" if province == "QC" else "tax.pos.gst_unregistered_pst"
    )
    return f"sales.{province}.gst", explanation, params


def _purchase(where: SupplyAddress) -> tuple[str, str, dict[str, Any]]:
    """(code, explanation key, params) from the supplier's place (decision table §4)."""
    if where.country != "CA":
        return "purchase.out_of_scope", "tax.pos.import", {"country": where.country}
    return (
        f"purchase.{where.province}.standard",
        "tax.pos.supplier_province",
        {"province": where.province},
    )


def warnings_for(context: SupplyContext) -> tuple[str, ...]:
    """Warnings for a line (G-02-T04): ``tax.pos.pst_unregistered`` for a taxable sale placed in
    BC, SK or MB while the organisation has no active registration for that province's tax —
    whatever code the line ends up with (an override doesn't silence it). Never blocks saving."""
    if context.side != SALES or not context.taxable:
        return ()
    where, _flags = place(context)
    if where is None or where.country != "CA" or where.province not in PST_PROVINCES:
        return ()
    if registered(context, PROVINCIAL_REGISTRATION[where.province]):
        return ()
    return (PST_UNREGISTERED,)


def resolve(context: SupplyContext) -> Resolution:
    """The default code for a line (module docstring), with its warnings."""
    resolution = _resolve(context)
    found = warnings_for(context)
    if not found:
        return resolution
    return replace(resolution, warnings=found)


def _resolve(context: SupplyContext) -> Resolution:
    side = context.side
    if side not in (SALES, PURCHASE):
        raise ValueError(f"Unknown side {side!r}.")
    override = _side_key(context.line_override, side)
    if override:
        return Resolution(override, SOURCE_OVERRIDE, "tax.pos.override")
    item = _side_key(context.item_code, side)
    if item:
        return Resolution(item, SOURCE_ITEM, "tax.pos.item")
    contact = _side_key(context.contact_default, side)
    if contact:
        return Resolution(contact, SOURCE_CONTACT, "tax.pos.contact")
    account = _side_key(context.account_default, side)
    if side == PURCHASE and account:
        return Resolution(account, SOURCE_ACCOUNT, "tax.pos.account")
    where, flags = place(context)
    if where is not None:
        if side == SALES:
            code, explanation, params = _sales(context, where)
        else:
            code, explanation, params = _purchase(where)
        return Resolution(
            code,
            SOURCE_PLACE,
            explanation,
            params,
            province=where.province,
            flags=flags,
        )
    if account:
        return Resolution(account, SOURCE_ACCOUNT, "tax.pos.account", flags=flags)
    return Resolution("", SOURCE_NONE, "tax.pos.none", flags=flags)
