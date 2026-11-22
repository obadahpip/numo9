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


def revise_code(
    current: TaxCode,
    *,
    effective_from: dt.date,
    components: Sequence[ComponentSpec | TaxComponent],
    name: str | None = None,
    name_fr: str | None = None,
    itc_restriction_pct: Decimal | None | object = ...,
) -> TaxCode:
    """A new version of ``current``'s code from ``effective_from`` with new components (G-01-T10).

    The version in force on that date is closed the day before; versions are never edited, so a
    line that stored the old version recalculates exactly as before. ``effective_from`` must be
    after the closed version's start (``tax.code.revision_date``)."""
    organisation = current.organisation
    with org_context(organisation), transaction.atomic():
        versions = list(
            TaxCode._base_manager.select_for_update()
            .filter(organisation=organisation, code=current.code)
            .order_by("version")
        )
        open_version = next((v for v in versions if v.is_active_on(effective_from)), None)
        if open_version is None or effective_from <= open_version.effective_from:
            raise TaxError(
                _(
                    "Choose a date after %(start)s, inside the version in force: the new version "
                    "starts there and the current one ends the day before."
                ),
                code="tax.code.revision_date",
                params={"start": (open_version or current).effective_from.isoformat()},
            )
        end = open_version.effective_to
        open_version.effective_to = effective_from - dt.timedelta(days=1)
        open_version.save(update_fields=["effective_to", "updated_at"])
        names = dict(open_version.name_i18n or {})
        if name is not None:
            names["en-ca"] = name
        if name_fr is not None:
            names["fr-ca"] = name_fr
        restriction = (
            open_version.itc_restriction_pct if itc_restriction_pct is ... else itc_restriction_pct
        )
        return define_code(
            organisation,
            code=open_version.code,
            name=names.get("en-ca", ""),
            name_fr=names.get("fr-ca", ""),
            side=open_version.side,
            type=open_version.type,
            province=open_version.province,
            effective_from=effective_from,
            effective_to=end,
            components=components,
            version=max(v.version for v in versions) + 1,
            itc_restriction_pct=restriction,
        )
