from django.apps import AppConfig


class BillingConfig(AppConfig):
    """Subscription billing with Stripe (U-04)."""

    name = "numo9.billing"
    label = "billing"
    verbose_name = "Billing"

    def ready(self) -> None:
        # Event handlers register themselves with the processing registry (U-04-T07, T08).
        from . import dunning, export, invoices, subscriptions  # noqa: F401
