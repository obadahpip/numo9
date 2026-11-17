from django.apps import AppConfig


class PlatformConfig(AppConfig):
    """Platform-owner console (U-06): the console's own API (who may use it, organisations and
    practices across tenants, metrics, audited sign-in as a user, feature flags)."""

    name = "numo9.platform"
    label = "platform"
    verbose_name = "Platform console"
