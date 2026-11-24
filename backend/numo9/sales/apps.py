from django.apps import AppConfig


class SalesConfig(AppConfig):
    """Sales documents (D-03a…): invoices on the shared document base (D-01), their numbering,
    approval and posting, PDF and email."""

    name = "numo9.sales"
    label = "sales"
    verbose_name = "Sales"

    def ready(self) -> None:
        from .credit import register_invoice_exposure

        register_invoice_exposure()  # what customers owe from invoices (D-03a-T06)
