from django.apps import AppConfig


class EntitlementsConfig(AppConfig):
    """Entitlement engine (U-03): subscriptions, overrides, read retention, resolution and cache."""

    name = "numo9.entitlements"
    label = "entitlements"
    verbose_name = "Entitlements"

    def ready(self) -> None:
        from . import cache

        cache.connect_signals()
        from django.db.models.signals import pre_save

        from numo9.orgsettings.models import TaxRegistration

        from .trials import bn_entered

        # A BN entered after the trial started is checked then (U-05-T06).
        pre_save.connect(bn_entered, sender=TaxRegistration, dispatch_uid="numo9.trial.bn")
