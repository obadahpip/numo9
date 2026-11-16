from typing import Any

from django.apps import AppConfig


class OrgSettingsConfig(AppConfig):
    """Organisation settings, tax registrations, lock dates and numbering (A-05)."""

    name = "numo9.orgsettings"
    label = "orgsettings"
    verbose_name = "Organisation settings"

    def ready(self) -> None:
        # Tenant sweep (A-01-T09): a tax registration needs a valid BN.
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["orgsettings.TaxRegistration"] = _sweep_registration
        SWEEP_FACTORIES["orgsettings.OrganisationSettings"] = _sweep_settings


def _sweep_registration(organisation: Any) -> Any:
    from .models import TaxRegistration

    existing = TaxRegistration._base_manager.filter(
        organisation=organisation, type="bn", deleted_at__isnull=True
    ).first()
    if existing is not None:  # one BN per period: reuse it for every endpoint of the sweep
        return existing
    row = TaxRegistration(organisation=organisation, type="bn", number="123456782")
    row.save()
    return row


def _sweep_settings(organisation: Any) -> Any:
    from .service import get_settings

    return get_settings(organisation)
