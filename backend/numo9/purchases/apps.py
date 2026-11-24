from django.apps import AppConfig


class PurchasesConfig(AppConfig):
    """Purchases (E-01…): purchase orders on the shared document base (D-01), their numbering
    and approval, goods receipts, commitments, PDF and email."""

    name = "numo9.purchases"
    label = "purchases"
    verbose_name = "Purchases"
