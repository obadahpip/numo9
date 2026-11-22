"""Define tax codes (G-01-T03): a code version and its components, checked together.

``define_code(organisation, code=…, side=…, type=…, components=[…])`` creates one version of a
tax code with its components in one transaction. On top of each component's own checks
(``TaxCodeComponent.clean``: side, effective range, zero-rated / exempt rules) a **taxable**
code needs at least one component (``tax.code.components_required``).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import TaxCode, TaxCodeComponent, TaxCodeType, TaxComponent, TaxError

#: (component, recoverable % override or None)
ComponentSpec = tuple[TaxComponent, Decimal | None]


def define_code(
    organisation: Organisation,
    *,
    code: str,
    name: str,
    side: str,
    type: str,  # noqa: A002 - the field's name
    effective_from: dt.date,
    effective_to: dt.date | None = None,
    province: str = "",
    components: Sequence[ComponentSpec | TaxComponent] = (),
    version: int | None = None,
    name_fr: str = "",
    **fields: Any,
) -> TaxCode:
    """Create a tax code version with its components (module docstring)."""
    parts = [item if isinstance(item, tuple) else (item, None) for item in components]
    if type == TaxCodeType.TAXABLE and not parts:
        raise TaxError(
            _("A taxable code needs at least one tax component."),
            code="tax.code.components_required",
        )
    with org_context(organisation), transaction.atomic():
        if version is None:
            latest = (
                TaxCode._base_manager.filter(organisation=organisation, code=code)
                .order_by("-version")
                .values_list("version", flat=True)
                .first()
            )
            version = (latest or 0) + 1
        names = {"en-ca": name}
        if name_fr:
            names["fr-ca"] = name_fr
        tax_code = TaxCode(
            organisation=organisation,
            code=code,
            version=version,
            name_i18n=names,
            side=side,
            type=type,
            province=province.upper(),
            effective_from=effective_from,
            effective_to=effective_to,
            **fields,
        )
        tax_code.save()
        for position, (component, pct) in enumerate(parts, start=1):
            TaxCodeComponent(
                organisation=organisation,
                tax_code=tax_code,
                component=component,
                position=position,
                recoverable_pct=pct,
            ).save()
        return tax_code
