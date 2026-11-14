"""Reading organisation settings (A-05-T01).

``get_settings()`` returns the active organisation's ``OrganisationSettings``, creating the row on
first use from what the organisation already knows (its name and time zone). Every later change
goes through the model (validated, audited, mirrored onto the organisation).
"""

from __future__ import annotations

from django.db import IntegrityError, transaction

from numo9.tenancy.context import TenantContextMissing, current_org
from numo9.tenancy.models import Organisation

from .models import OrganisationSettings


def _has_letters(value: str) -> bool:
    return any(character.isalpha() for character in value)


def get_settings(organisation: Organisation | None = None) -> OrganisationSettings:
    """The organisation's settings row (the active organisation by default)."""
    org = organisation or current_org()
    if org is None:
        raise TenantContextMissing("get_settings() needs an active organisation.")
    existing = OrganisationSettings._base_manager.filter(organisation=org).first()
    if existing is not None:
        return existing
    settings = OrganisationSettings(
        organisation=org,
        display_name=org.name,
        # A name with no letters (an imported "1001633222") is no legal name (gap-55).
        legal_name=org.name if _has_letters(org.name) else "",
        time_zone=org.time_zone,
    )
    try:
        with transaction.atomic():
            settings.save()
    except IntegrityError:  # created at the same moment by another request
        return OrganisationSettings._base_manager.get(organisation=org)
    return settings
