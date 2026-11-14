"""People-facing texts of the catalogue (U-01-T13): translation key → gettext message.

Products and feature keys store an i18n key (``catalogue.product.<code>``,
``catalogue.feature.<key>``); the API, the exports and the error messages show the text found
here in the request's language. A key without a text falls back to the code (and
tests/test_catalogue_texts.py fails, so every seeded key has its EN and FR entry).
"""

from __future__ import annotations

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

PRODUCT_NAMES: dict[str, Promise] = {
    "catalogue.product.accounting": _("Accounting"),
    "catalogue.product.tax": _("Tax"),
    "catalogue.product.payroll": _("Payroll"),
    "catalogue.product.inventory": _("Inventory"),
    "catalogue.product.finance": _("Finance"),
    "catalogue.product.practice": _("Practice"),
    "catalogue.product.portal": _("Client portal"),
    "catalogue.product.app.commerce": _("Numo9 Commerce"),
    "catalogue.product.app.bank": _("Numo9 Bank"),
    "catalogue.product.app.receipts": _("Numo9 Receipts"),
}

#: Plain language for an organisation owner, in screen order (the seed migration's order).
FEATURE_DESCRIPTIONS: dict[str, Promise] = {
    "catalogue.feature.accounting.contacts.read": _(
        "See customers and suppliers, their activity and statements"
    ),
    "catalogue.feature.accounting.contacts.write": _(
        "Add, edit, import and archive customers and suppliers"
    ),
    "catalogue.feature.accounting.chart_of_accounts.read": _(
        "See the chart of accounts and its GIFI codes"
    ),
    "catalogue.feature.accounting.chart_of_accounts.write": _(
        "Add, edit and archive accounts in the chart of accounts"
    ),
    "catalogue.feature.accounting.journals.read": _("See manual journals and every posted entry"),
    "catalogue.feature.accounting.journals.write": _("Create and post manual journals"),
    "catalogue.feature.accounting.journals.approve": _(
        "Approve manual journals before they're posted"
    ),
    "catalogue.feature.accounting.documents.read": _("See the documents inbox and attached files"),
    "catalogue.feature.accounting.documents.write": _(
        "Upload documents, email them to the inbox and turn them into bills or receipts"
    ),
    "catalogue.feature.accounting.sales_quotes.read": _("See quotes"),
    "catalogue.feature.accounting.sales_quotes.write": _(
        "Create and send quotes and turn them into invoices"
    ),
    "catalogue.feature.accounting.sales_invoices.read": _("See invoices and their revisions"),
    "catalogue.feature.accounting.sales_invoices.write": _("Create, edit and send invoices"),
    "catalogue.feature.accounting.sales_invoices.approve": _(
        "Approve invoices before they're sent"
    ),
    "catalogue.feature.accounting.credit_notes.read": _("See credit notes"),
    "catalogue.feature.accounting.credit_notes.write": _(
        "Create credit notes and apply them to invoices"
    ),
    "catalogue.feature.accounting.invoice_reminders.read": _("See the reminders sent to customers"),
    "catalogue.feature.accounting.invoice_reminders.write": _(
        "Send invoice reminders before and after the due date"
    ),
    "catalogue.feature.accounting.payments_received.read": _(
        "See payments received from customers"
    ),
    "catalogue.feature.accounting.payments_received.write": _(
        "Record customer payments and allocate them to invoices"
    ),
    "catalogue.feature.accounting.purchase_orders.read": _(
        "See purchase orders and what was received"
    ),
    "catalogue.feature.accounting.purchase_orders.write": _(
        "Create and send purchase orders and record what was received"
    ),
    "catalogue.feature.accounting.purchase_orders.approve": _(
        "Approve purchase orders before they're sent"
    ),
    "catalogue.feature.accounting.bills.read": _("See supplier bills"),
    "catalogue.feature.accounting.bills.write": _("Enter and edit supplier bills and pay them"),
    "catalogue.feature.accounting.bills.approve": _("Approve supplier bills for payment"),
    "catalogue.feature.accounting.expense_claims.read": _("See expense claims and receipts"),
    "catalogue.feature.accounting.expense_claims.write": _("Submit expense claims with receipts"),
    "catalogue.feature.accounting.expense_claims.approve": _(
        "Approve expense claims for reimbursement"
    ),
    "catalogue.feature.accounting.banking.read": _(
        "See bank, credit card and cash accounts and their transactions"
    ),
    "catalogue.feature.accounting.banking.write": _(
        "Import bank statements, reconcile and record bank transactions"
    ),
    "catalogue.feature.accounting.projects.read": _("See projects and their profitability"),
    "catalogue.feature.accounting.projects.write": _(
        "Create projects and track time and costs against them"
    ),
    "catalogue.feature.accounting.multi_currency.read": _(
        "See amounts in foreign currencies and exchange gains and losses"
    ),
    "catalogue.feature.accounting.multi_currency.write": _(
        "Invoice, bill and bank in foreign currencies"
    ),
    "catalogue.feature.accounting.conversion_balances.read": _(
        "See the opening balances brought over from another system"
    ),
    "catalogue.feature.accounting.conversion_balances.write": _(
        "Enter opening balances when moving from another system"
    ),
    "catalogue.feature.accounting.period_close.read": _(
        "See period-close checklists and year-end status"
    ),
    "catalogue.feature.accounting.period_close.write": _("Close periods and the fiscal year"),
    "catalogue.feature.accounting.recode.write": _(
        "Find and recode transactions in bulk, with undo"
    ),
    "catalogue.feature.accounting.reports.read": _(
        "Run financial reports: balance sheet, income statement, trial balance"
    ),
    "catalogue.feature.accounting.assurance.read": _(
        "See data-quality findings and fix suggestions"
    ),
    "catalogue.feature.tax.codes.read": _("See GST/HST, QST and PST tax codes and rates"),
    "catalogue.feature.tax.codes.write": _("Add and edit tax codes and rates"),
    "catalogue.feature.tax.returns.read": _("See GST/HST and QST returns and filing periods"),
    "catalogue.feature.tax.returns.write": _("Prepare GST/HST and QST returns"),
    "catalogue.feature.tax.returns.approve": _("Review and mark returns as filed"),
    "catalogue.feature.tax.reports.read": _("Run tax reports"),
    "catalogue.feature.practice.directory.read": _("See the practice's organisation directory"),
    "catalogue.feature.practice.groups.read": _("See groups and tags of organisations"),
    "catalogue.feature.practice.groups.write": _(
        "Create groups and tags and organise client organisations"
    ),
    "catalogue.feature.practice.bulk_actions.write": _(
        "Change many organisations at once, with a preview"
    ),
    "catalogue.feature.practice.dashboards.read": _(
        "See deadlines and workload across client organisations"
    ),
    "catalogue.feature.practice.staff.read": _("See practice staff and who is assigned where"),
    "catalogue.feature.practice.staff.write": _("Invite staff and assign them to organisations"),
    "catalogue.feature.portal.documents.read": _(
        "Clients see the documents their accountant shares"
    ),
    "catalogue.feature.portal.documents.write": _("Clients upload documents for their accountant"),
    "catalogue.feature.portal.requests.read": _("Clients see their accountant's requests"),
    "catalogue.feature.portal.requests.write": _("Clients answer their accountant's requests"),
}


def text_for(i18n_key: str, fallback: str) -> str:
    """The translated text of a catalogue i18n key, or ``fallback`` when it has none."""
    message = PRODUCT_NAMES.get(i18n_key) or FEATURE_DESCRIPTIONS.get(i18n_key)
    return str(message) if message is not None else fallback


def product_name(code: str) -> str:
    return text_for(f"catalogue.product.{code}", code)
