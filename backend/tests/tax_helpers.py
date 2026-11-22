"""Shared helpers for the tax-engine tests (G-01, G-02)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.tax.models import TaxAuthority, TaxComponent
from numo9.tenancy.models import Organisation


def authority(org: Organisation, code: str = "CRA", name: str = "Canada Revenue Agency") -> Any:
    found = TaxAuthority._base_manager.filter(organisation=org, code=code).first()
    if found is not None:
        return found
    item = TaxAuthority(organisation=org, code=code, name_i18n={"en-ca": name})
    item.save()
    return item


def component(
    org: Organisation,
    key: str,
    rate: str,
    start: dt.date = dt.date(2010, 7, 1),
    end: dt.date | None = None,
    **fields: Any,
) -> TaxComponent:
    fields.setdefault(
        "kind", key.split("_")[0] if key.split("_")[0] in ("gst", "hst", "pst", "qst") else "pst"
    )
    item = TaxComponent(
        organisation=org,
        authority=fields.pop("authority", None) or authority(org),
        key=key,
        rate=Decimal(rate),
        effective_from=start,
        effective_to=end,
        name_i18n={"en-ca": fields.pop("name", key.upper())},
        **fields,
    )
    item.save()
    return item
