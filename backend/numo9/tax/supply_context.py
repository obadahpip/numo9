"""Context builder (G-02-T03): a ``SupplyContext`` from a document's header and line.

``build_context(side, date, organisation, contact=…, ship_to=…, account=…, item=…,
line_override=…)`` gathers what the pure resolver (``place_of_supply.resolve``) needs:

- the organisation's home province (physical, else mailing address — A-05) and its tax
  registrations (A-05-T03);
- the contact's billing and shipping addresses (B-01-T04); a document ship-to (a
  ``SupplyAddress``, an ``Address`` or a mapping with ``country`` / ``province``) wins over the
  contact's shipping address;
- the item's tax setting — the H-01 hook: an item exposes ``sales_tax_key`` /
  ``purchase_tax_key`` (any object with those attributes; items arrive in H-01) and
  ``is_taxable`` (default True);
- the account's ``default_tax_key`` (G-01-T09); an expense account without one falls back to
  the home province's purchase rate, as ``tax.defaults.default_code`` does.

A contact without an address falls back to the home province: the resolution carries the
``missing_province`` flag (``place_of_supply.MISSING_PROVINCE``).

``resolve_line(...)`` builds the context, resolves it and returns ``(resolution, version)`` —
the code version in force on the date (``tax.resolver.code_for``), or None when the key has no
version on that date (the editor then asks for a code).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any

from numo9.tenancy.context import org_context

from .place_of_supply import (
    PURCHASE,
    Registration,
    Resolution,
    SupplyAddress,
    SupplyContext,
    resolve,
)


def supply_address(value: Any) -> SupplyAddress | None:
    """A ``SupplyAddress`` from an address model, a mapping or a ``SupplyAddress``."""
    if value is None or isinstance(value, SupplyAddress):
        return value
    if isinstance(value, Mapping):
        country, province = value.get("country"), value.get("province")
    else:
        country, province = getattr(value, "country", None), getattr(value, "province", None)
    return SupplyAddress((country or "CA").upper(), (province or "").upper())


def registrations(organisation: Any) -> tuple[Registration, ...]:
    from numo9.orgsettings.models import TaxRegistration

    from .filing_service import gaps

    with org_context(organisation):
        rows = TaxRegistration.objects.filter(organisation=organisation)
        return tuple(
            Registration(
                row.type,
                row.status,
                row.effective_from,
                row.effective_to,
                tuple(gaps(row)) if row.files_returns else (),
            )
            for row in rows
        )


def contact_addresses(contact: Any) -> tuple[SupplyAddress | None, SupplyAddress | None]:
    """(billing, shipping) of ``contact``; None for a missing one."""
    if contact is None:
        return None, None
    from numo9.contacts.models import Address, AddressKind

    with org_context(contact.organisation):
        found = {
            a.kind: a
            for a in Address.objects.filter(contact=contact, deleted_at__isnull=True).only(
                "kind", "country", "province"
            )
        }
    return (
        supply_address(found.get(AddressKind.BILLING)),
        supply_address(found.get(AddressKind.SHIPPING)),
    )


def _item_key(item: Any, side: str) -> str:
    if item is None:
        return ""
    return str(getattr(item, f"{side}_tax_key", "") or "")


def _account_key(account: Any, side: str, home: str) -> str:
    if account is None:
        return ""
    key = str(getattr(account, "default_tax_key", "") or "")
    if key:
        return key
    from numo9.ledger.models import AccountType

    if side == PURCHASE and getattr(account, "type", None) == AccountType.EXPENSE and home:
        return f"purchase.{home}.standard"
    return ""


def build_context(
    side: str,
    date: dt.date,
    organisation: Any,
    *,
    contact: Any = None,
    ship_to: Any = None,
    account: Any = None,
    item: Any = None,
    line_override: str = "",
    contact_default: str = "",
) -> SupplyContext:
    from .defaults import home_province

    home = home_province(organisation)
    billing, shipping = contact_addresses(contact)
    document_ship_to = supply_address(ship_to)
    return SupplyContext(
        side=side,
        date=date,
        home_province=home,
        registrations=registrations(organisation),
        ship_to=document_ship_to if document_ship_to is not None else shipping,
        billing=billing,
        line_override=line_override,
        item_code=_item_key(item, side),
        contact_default=contact_default,
        account_default=_account_key(account, side, home),
        taxable=bool(getattr(item, "is_taxable", True)) if item is not None else True,
        out_of_scope_after_stop=_out_of_scope_after_stop(organisation),
    )


def _out_of_scope_after_stop(organisation: Any) -> bool:
    from .settings import tax_settings

    return bool(tax_settings(organisation).out_of_scope_after_stop)


def resolve_line(
    side: str, date: dt.date, organisation: Any, **header: Any
) -> tuple[Resolution, Any]:
    """Resolve a line (module docstring): ``(resolution, code version or None)``."""
    from .resolver import TaxCodeExpired, TaxCodeUnknown, code_for

    resolution = resolve(build_context(side, date, organisation, **header))
    if not resolution.code:
        return resolution, None
    try:
        return resolution, code_for(resolution.code, side, date, organisation)
    except (TaxCodeExpired, TaxCodeUnknown):
        return resolution, None
