"""Acquisition attribution (U-08-T07): captured for every new organisation at creation.

``record_attribution(organisation=…, source=…, data=…)`` stores one
``AcquisitionAttribution`` row in the creating transaction. ``data`` holds what the sign-up form
received — ``referral_source``, ``utm_source`` … ``utm_content``, ``promo_code``, ``referrer`` —
each trimmed to its column; unknown keys are ignored. Organisations are recorded by every
creation path: self sign-up, the in-app "new organisation" (by an owner or a practice), and demo
conversion; an accountant's sign-up is recorded on the practice.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from numo9.tenancy.models import Organisation, Practice

from .models import AcquisitionAttribution

#: Field → column length (``AcquisitionAttribution``).
FIELDS: dict[str, int] = {
    "referral_source": 100,
    "utm_source": 100,
    "utm_medium": 100,
    "utm_campaign": 100,
    "utm_term": 100,
    "utm_content": 100,
    "promo_code": 64,
    "referrer": 500,
}


def clean(data: Mapping[str, Any] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, limit in FIELDS.items():
        raw = (data or {}).get(name)
        if raw in (None, ""):
            continue
        text = " ".join(str(raw).split())[:limit]
        values[name] = text.upper() if name == "promo_code" else text
    return values


def record_attribution(
    *,
    source: str,
    organisation: Organisation | None = None,
    practice: Practice | None = None,
    data: Mapping[str, Any] | None = None,
) -> AcquisitionAttribution:
    subject: dict[str, Any] = (
        {"organisation": organisation} if organisation is not None else {"practice": practice}
    )
    row, _created = AcquisitionAttribution.objects.update_or_create(
        **subject, defaults={"source": source, **clean(data)}
    )
    return row
