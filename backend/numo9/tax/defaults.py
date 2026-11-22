"""Default tax code per account (G-01-T09): expense accounts default to the home-province
purchase rate, never "Exempt" (gap-45).

- ``home_province(organisation)`` — the physical address's province (A-05), else the mailing
  address's.
- ``default_code(account, side, date)`` — the code a new line on ``account`` starts with: the
  account's ``default_tax_key`` resolved for the date (G-01-T08) when it is a key of that side;
  an expense account without a key gets ``purchase.<home province>.standard``; anything else
  has no default (None).
- ``apply_province_defaults(organisation, province)`` — migration helper for the chart: re-keys
  the template purchase / sales defaults (``purchase.<PROV>.standard[.itc50]``,
  ``sales.<PROV>.standard``) and fills empty expense-account defaults to the given (default:
  home) province — after the organisation's province changes or for a chart loaded before the
  province was set. Exempt and custom keys are left alone. Returns how many accounts changed.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from django.db import transaction

from numo9.ledger.models import Account, AccountType
from numo9.tenancy.context import org_context

from .models import TaxCode, TaxSide
from .resolver import TaxCodeExpired, TaxCodeUnknown, code_for

TEMPLATE_KEY = re.compile(
    r"^(?P<side>purchase|sales)\.(?P<prov>[A-Z]{2})\.standard(?P<itc>\.itc50)?$"
)


def home_province(organisation: Any) -> str:
    from numo9.orgsettings.service import get_settings

    settings = get_settings(organisation)
    return (settings.physical_province or settings.mailing_province or "").upper()


def side_of(key: str) -> str | None:
    if key.startswith("sales."):
        return TaxSide.SALES
    if key.startswith("purchase."):
        return TaxSide.PURCHASE
    return None


def default_code(account: Account, side: str, day: dt.date) -> TaxCode | None:
    """The default code for a new ``side`` line on ``account`` dated ``day`` (module docstring)."""
    key = account.default_tax_key
    if not key and account.type == AccountType.EXPENSE and side == TaxSide.PURCHASE:
        province = home_province(account.organisation)
        key = f"purchase.{province}.standard" if province else ""
    if not key or side_of(key) != side:
        return None
    try:
        return code_for(key, side, day, account.organisation)
    except (TaxCodeExpired, TaxCodeUnknown):
        return None


def apply_province_defaults(organisation: Any, province: str | None = None) -> int:
    """Re-key template defaults to ``province`` (module docstring); returns the count changed."""
    province = (province or home_province(organisation)).upper()
    if not province:
        return 0
    changed = 0
    with org_context(organisation), transaction.atomic():
        for account in Account.objects.filter(deleted_at__isnull=True):
            key = account.default_tax_key
            match = TEMPLATE_KEY.match(key) if key else None
            if match:
                new = f"{match['side']}.{province}.standard{match['itc'] or ''}"
            elif not key and account.type == AccountType.EXPENSE and not account.system_role:
                new = f"purchase.{province}.standard"
            else:
                continue
            if new != key:
                account.default_tax_key = new
                account.save()
                changed += 1
    return changed
