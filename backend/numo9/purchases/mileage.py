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


# ---- calculator (E-04-T03) ---------------------------------------------------------------------

CENT = Decimal("0.01")


def split_km(prior_km: Decimal, km: Decimal, threshold: Decimal) -> tuple[Decimal, Decimal]:
    """Split ``km`` driven after ``prior_km`` business kilometres this year into the part at the
    first-tier rate (up to ``threshold``) and the part after it."""
    if km < 0 or prior_km < 0:
        raise ValueError("kilometres cannot be negative")
    first = max(Decimal(0), min(km, threshold - prior_km))
    return first, km - first


def mileage_amount(
    km: Decimal, rate: MileageRate, prior_km: Decimal = Decimal(0)
) -> tuple[Decimal, list[dict[str, str]]]:
    """The amount of ``km`` at ``rate`` with ``prior_km`` already driven in the year, rounded to
    the cent, and the tiers applied (``rate_detail``: km, rate, amount per tier)."""
    first, after = split_km(prior_km, km, Decimal(rate.tier_threshold_km))
    detail: list[dict[str, str]] = []
    total = Decimal(0)
    for tier, part, per_km in (
        ("first", first, rate.first_tier_rate),
        ("after", after, rate.second_tier_rate),
    ):
        if part > 0:
            amount = part * per_km
            total += amount
            detail.append(
                {
                    "tier": tier,
                    "km": str(part),
                    "rate": str(per_km.normalize()),
                    "amount": str(amount.quantize(CENT)),
                }
            )
    return total.quantize(CENT), detail


def year_to_date_km(claim: Any, before: Any = None) -> Decimal:
    """Business kilometres the claim's claimant already claimed this calendar year in the
    organisation, before ``before`` (a line of ``claim``): every mileage line of their other
    claims that are not rejected (drafts included — they are being claimed), dated in the year
    and before the line's date, plus the earlier lines of this claim."""
    from .models import ExpenseClaimLine, ExpenseClaimStatus, ExpenseLineKind

    day = before.date if before is not None else None
    if day is None:
        return Decimal(0)
    year_start = dt.date(day.year, 1, 1)
    others = (
        ExpenseClaimLine.objects.filter(
            organisation_id=claim.organisation_id,
            claim__claimant_id=claim.claimant_id,
            kind=ExpenseLineKind.MILEAGE,
            date__gte=year_start,
            date__lt=day,
        )
        .exclude(claim_id=claim.pk)
        .exclude(claim__status=ExpenseClaimStatus.REJECTED)
        .aggregate(km=models.Sum("distance_km"))["km"]
    ) or Decimal(0)
    own = Decimal(0)
    for line in _ordered_mileage_lines(claim):
        if line.pk == before.pk:
            break
        if line.date.year == day.year:
            own += line.distance_km or 0
    return Decimal(others) + own


def _ordered_mileage_lines(claim: Any) -> list[Any]:
    from .models import ExpenseLineKind

    return sorted(
        (line for line in claim.lines.all() if line.kind == ExpenseLineKind.MILEAGE),
        key=lambda line: (line.date, line.position, line.pk or 0),
    )


def price_mileage(claim: Any, region: str = MileageRegion.PROVINCES) -> Decimal:
    """Set ``amount`` and ``rate_detail`` of every mileage line of ``claim`` (in date order, so
    a claim crossing 5,000 km gets both tiers on the crossing line) and save them; returns the
    mileage total. The rate is the one in force on each line's date."""
    total = Decimal(0)
    for line in _ordered_mileage_lines(claim):
        rate = rate_on(line.date, region)
        prior = year_to_date_km(claim, line)
        line.amount, line.rate_detail = mileage_amount(Decimal(line.distance_km), rate, prior)
        line.save(update_fields=["amount", "rate_detail"])
        total += line.amount
    return total
