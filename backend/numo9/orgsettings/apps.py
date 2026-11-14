from django.apps import AppConfig


class OrgSettingsConfig(AppConfig):
    """Organisation settings, tax registrations, lock dates and numbering (A-05)."""

    name = "numo9.orgsettings"
    label = "orgsettings"
    verbose_name = "Organisation settings"
