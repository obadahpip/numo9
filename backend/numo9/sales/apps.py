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
