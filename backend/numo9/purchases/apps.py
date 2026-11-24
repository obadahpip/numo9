from django.apps import AppConfig


class PurchasesConfig(AppConfig):
    """Purchases (E-01…): purchase orders on the shared document base (D-01), their numbering
    and approval, goods receipts, commitments, PDF and email."""

    name = "numo9.purchases"
    label = "purchases"
    verbose_name = "Purchases"

    def ready(self) -> None:
        from .approvables import register_purchase_order_approvals

        register_purchase_order_approvals()  # POs in the approvals inbox (E-01-T15)
        from numo9.reports.drill import register_source

        # A report figure's bill lines open the bill (K-01-T05 drill-down, E-02-T10).
        register_source(
            "purchases.bill", lambda org, sid: f"/o/{org.public_id}/purchases/bills/{sid}"
        )
