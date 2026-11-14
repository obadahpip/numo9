"""GIFI master list (C-01-T04): seed from the CRA list, lookup by code, search.

Source: CRA publication RC4088(E) Rev. 23, *General Index of Financial Information (GIFI)*,
published 2023-08-23 (canada.ca). ``data/gifi_rc4088_rev23.csv`` holds every code of the
balance sheet (1000–3849), other comprehensive income (7000–7020) and income statement
(8000–9999, farming included) with its description, its section and whether it is a total or
computed line (never mapped to an account). The identification lines 0001–0003 are not codes an
account maps to and are left out.

``seed_gifi`` runs in the data migration and again after every ``migrate``/test flush for missing
rows (as the product catalogue does, U-01): rows are never changed by the seed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.db.models import Q

DATA = Path(__file__).resolve().parent / "data" / "gifi_rc4088_rev23.csv"
LIST_VERSION = "RC4088(E) Rev. 23"
PUBLISHED_ON = date(2023, 8, 23)


@dataclass(frozen=True)
class GifiRow:
    code: str
    description: str
    section: str
    is_summary: bool


@lru_cache(maxsize=1)
def published_rows() -> tuple[GifiRow, ...]:
    with DATA.open(encoding="utf-8", newline="") as handle:
        return tuple(
            GifiRow(
                code=row["code"],
                description=row["description"],
                section=row["section"],
                is_summary=row["is_summary"] == "1",
            )
            for row in csv.DictReader(handle)
        )


def seed_gifi(apps: Any, *, missing_only: bool = True) -> int:
    """Create the published codes that are missing; return how many were created."""
    model = apps.get_model("ledger", "GifiCode")
    existing = set(model.objects.values_list("code", flat=True))
    new = [
        model(
            code=row.code,
            description=row.description,
            section=row.section,
            is_summary=row.is_summary,
            list_version=LIST_VERSION,
            published_on=PUBLISHED_ON,
        )
        for row in published_rows()
        if row.code not in existing
    ]
    model.objects.bulk_create(new, batch_size=500)
    return len(new)


def lookup(code: str) -> Any:
    """The ``GifiCode`` for a 4-digit code, or None."""
    from .models import GifiCode

    return GifiCode.objects.filter(code=(code or "").strip()).first()


def search(query: str, *, account_type: str | None = None, limit: int = 20) -> list[Any]:
    """Codes to map an account to, by code prefix or words of the description (GIFI picker).

    Only assignable codes (no totals, not retired); with ``account_type`` only the sections that
    fit that type (an expense account is offered expense codes).
    """
    from .models import TYPE_GIFI_SECTIONS, GifiCode

    queryset = GifiCode.objects.filter(is_summary=False, retired_in="")
    if account_type:
        queryset = queryset.filter(section__in=TYPE_GIFI_SECTIONS[account_type])
    text = (query or "").strip()
    if text.isdigit():
        queryset = queryset.filter(code__startswith=text)
    elif text:
        condition = Q()
        for word in text.split():
            condition &= Q(description__icontains=word)
        queryset = queryset.filter(condition)
    return list(queryset.order_by("code")[:limit])
