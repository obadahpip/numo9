"""Shared helpers for the chart-of-accounts tests (C-01)."""

from __future__ import annotations

from typing import Any

from numo9.ledger.models import SUBTYPE_TYPE, Account
from numo9.tenancy.models import Organisation


def account(
    organisation: Organisation,
    code: str,
    name: str = "",
    subtype: str = "operating_expense",
    **fields: Any,
) -> Account:
    """Create and save an account (runs every save rule)."""
    item = Account(
        organisation=organisation,
        code=code,
        name_i18n={"en-ca": name or f"Account {code}"},
        type=SUBTYPE_TYPE[subtype],
        subtype=subtype,
        **fields,
    )
    item.save()
    return item
