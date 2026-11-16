from django.apps import AppConfig


class BillingConfig(AppConfig):
    """Subscription billing with Stripe (U-04)."""

    name = "numo9.billing"
    label = "billing"
    verbose_name = "Billing"
