from typing import Any

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

        from .current import register_receivables

        register_receivables()  # statements and AR aging read current revisions (D-03b-T12)

        from .search import register_sales_search

        register_sales_search()  # invoices in the global search (D-03a-T17)
        from .search import register_quote_search

        register_quote_search()  # quotes in the global search (D-02-T16)

        from .recode import register_recode_exclusions

        register_recode_exclusions()  # find & recode exclusions (C-07-T03)

        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["sales.Invoice"] = _sweep_invoice


def _sweep_invoice(organisation: Any) -> Any:
    import datetime as dt
    import uuid

    from numo9.contacts.models import Contact
    from numo9.tenancy.context import org_context

    from .models import Invoice

    with org_context(organisation):
        customer = Contact(
            organisation=organisation,
            display_name=f"Sweep {uuid.uuid4().hex[:8]}",
            roles=["customer"],
        )
        customer.save()
        invoice = Invoice(
            organisation=organisation,
            contact=customer,
            date=dt.date(2026, 6, 15),
            due_date=dt.date(2026, 7, 15),
        )
        invoice.save()
        return invoice
