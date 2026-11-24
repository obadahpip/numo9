"""Tax settings access (G-06-T02): ``tax_settings(organisation)`` — the row, created with the
defaults (accrual basis, per-line rounding, no quick method, no default codes) the first time."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from numo9.tenancy.context import current_org, org_context

from .models import TaxSettings


def tax_settings(organisation: Any = None) -> TaxSettings:
    org = organisation or current_org()
    if org is None:
        raise RuntimeError("tax_settings() needs an active organisation.")
    existing: TaxSettings | None = TaxSettings._base_manager.filter(organisation=org).first()
    if existing is not None:
        return existing
    with org_context(org):
        row = TaxSettings(organisation=org)
        try:
            with transaction.atomic():
                row.save()
        except IntegrityError:  # created at the same moment by another request
            found: TaxSettings = TaxSettings._base_manager.get(organisation=org)
            return found
    return row
