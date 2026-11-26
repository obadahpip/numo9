from typing import Any

from django.apps import AppConfig


class SalesConfig(AppConfig):
    """Sales documents (D-03a…): invoices on the shared document base (D-01), their numbering,
    approval and posting, PDF and email."""

    name = "numo9.sales"
    label = "sales"
    verbose_name = "Sales"

    def ready(self) -> None:
        from django.utils.translation import gettext_lazy as _

        from numo9.contacts.merge import register_reference

        # A payment received and a customer credit keep their contact on a merge, like the
        # journal lines they posted (D-05-T01).
        register_reference("sales.CustomerPayment", "contact", "keep", _("payments received"))
        register_reference("sales.CustomerCredit", "contact", "keep", _("customer credits"))

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
        SWEEP_FACTORIES["sales.Quote"] = _sweep_quote  # the quotes API (D-02-T11)
        SWEEP_FACTORIES["sales.RecurringInvoiceTemplate"] = _sweep_recurring_invoice


def _sweep_customer(organisation: Any) -> Any:
    import uuid

    from numo9.contacts.models import Contact

    customer = Contact(
        organisation=organisation,
        display_name=f"Sweep {uuid.uuid4().hex[:8]}",
        roles=["customer"],
    )
    customer.save()
    return customer


def _sweep_recurring_invoice(organisation: Any) -> Any:
    import datetime as dt

    from numo9.tenancy.context import org_context

    from .models import RecurringInvoiceTemplate

    with org_context(organisation):
        template = RecurringInvoiceTemplate(
            organisation=organisation,
            name="Sweep",
            contact=_sweep_customer(organisation),
            rrule="FREQ=MONTHLY",
            start_date=dt.date(2026, 6, 15),
        )
        template.save()
        return template


def _sweep_invoice(organisation: Any) -> Any:
    import datetime as dt

    from numo9.tenancy.context import org_context

    from .models import Invoice

    with org_context(organisation):
        customer = _sweep_customer(organisation)
        invoice = Invoice(
            organisation=organisation,
            contact=customer,
            date=dt.date(2026, 6, 15),
            due_date=dt.date(2026, 7, 15),
        )
        invoice.save()
        return invoice


def _sweep_quote(organisation: Any) -> Any:
    import datetime as dt

    from numo9.tenancy.context import org_context

    from .quotes import create_quote

    with org_context(organisation):
        invoice = _sweep_invoice(organisation)  # its customer
        return create_quote(
            organisation,
            contact=invoice.contact,
            date=dt.date(2026, 6, 15),
            expiry_date=dt.date(2026, 7, 15),
        )
