"""CRA per-kilometre mileage rates (E-04-T02) and the mileage calculator (E-04-T03).

``rate_on(day, region)`` — the ``MileageRate`` in force on ``day``; ``seed_mileage_rates()``
writes ``data/mileage_rates_ca.json`` into the table (idempotent: a row already there for a
region and start date is updated, never duplicated). Each year's rates run from 1 January to
31 December; the latest year stays open (``effective_to`` null) until the next one is seeded.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .models import MileageRate, MileageRegion

SEED_PATH = Path(__file__).parent / "data" / "mileage_rates_ca.json"

#: Territories where the CRA rate is 4 ¢ higher.
TERRITORIES = frozenset({"YT", "NT", "NU"})


def region_for(province: str) -> str:
    """The rate region of a province or territory code (``ON`` → provinces)."""
    return MileageRegion.TERRITORIES if province.upper() in TERRITORIES else MileageRegion.PROVINCES


def load_mileage_seed() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return data


def seed_mileage_rates(model: Any = MileageRate) -> int:
    """Install the seeded CRA rates (``model`` is the historical model in a data migration).
    Returns the number of rows written."""
    data = load_mileage_seed()
    threshold = int(data["tier_threshold_km"])
    years = sorted({int(r["year"]) for r in data["rates"]})
    latest = years[-1]
    written = 0
    for row in data["rates"]:
        year = int(row["year"])
        model.objects.update_or_create(
            region=row["region"],
            effective_from=dt.date(year, 1, 1),
            defaults={
                "effective_to": None if year == latest else dt.date(year, 12, 31),
                "first_tier_rate": Decimal(row["first"]),
                "second_tier_rate": Decimal(row["after"]),
                "tier_threshold_km": threshold,
                "source": data["source"][:300],
            },
        )
        written += 1
    return written


def rate_on(day: dt.date, region: str = MileageRegion.PROVINCES) -> MileageRate:
    """The rate in force on ``day`` for ``region``; ``ValidationError`` when none covers it."""
    rate = (
        MileageRate.objects.filter(region=region, effective_from__lte=day)
        .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=day))
        .order_by("-effective_from")
        .first()
    )
    if rate is None:
        raise ValidationError(
            _("No mileage rate is set for %(day)s."),
            code="mileage_rate_missing",
            params={"day": day.isoformat()},
        )
    return rate
