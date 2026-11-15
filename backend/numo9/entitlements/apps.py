from django.apps import AppConfig


class EntitlementsConfig(AppConfig):
    """Entitlement engine (U-03): subscriptions, overrides, read retention, resolution and cache."""

    name = "numo9.entitlements"
    label = "entitlements"
    verbose_name = "Entitlements"

    def ready(self) -> None:
        from . import cache

        cache.connect_signals()
