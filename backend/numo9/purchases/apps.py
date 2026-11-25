from django.apps import AppConfig


class PurchasesConfig(AppConfig):
    """Purchases (E-01…): purchase orders on the shared document base (D-01), their numbering
    and approval, goods receipts, commitments, PDF and email."""

    name = "numo9.purchases"
    label = "purchases"
    verbose_name = "Purchases"

    def ready(self) -> None:
        from .approvables import (
            register_bill_approvals,
            register_expense_claim_approvals,
            register_purchase_order_approvals,
        )

        register_purchase_order_approvals()  # POs in the approvals inbox (E-01-T15)
        register_bill_approvals()  # bills routed to the approver's role (E-02-T14)
        register_expense_claim_approvals()  # expense claims awaiting approval (E-04-T11)
        from .search import register_bill_search

        register_bill_search()  # bills in the global search (E-02-T16)
        from numo9.reports.drill import register_source

        # A report figure's bill lines open the bill (K-01-T05 drill-down, E-02-T10).
        register_source(
            "purchases.bill", lambda org, sid: f"/o/{org.public_id}/purchases/bills/{sid}"
        )
