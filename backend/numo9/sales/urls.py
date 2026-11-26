"""Sales routes, under /api/v1/: invoices CRUD and actions (D-03a-T11), email (D-03a-T12); quotes
CRUD and actions, and the public quote link's endpoints (D-02-T11)."""

from django.urls import path

from . import api, invoices_api, quotes_api

ORG = "o/<uuid:org>/"
INVOICE = f"{ORG}invoices/<uuid:public_id>"
QUOTE = f"{ORG}quotes/<uuid:public_id>"
PUBLIC_QUOTE = "q/<str:token>"

urlpatterns = [
    path(f"{ORG}invoices", invoices_api.InvoiceListView.as_view(), name="invoices"),
    path(INVOICE, invoices_api.InvoiceDetailView.as_view(), name="invoice"),
    path(f"{INVOICE}/preview", invoices_api.InvoicePreviewView.as_view(), name="invoice-preview"),
    path(f"{INVOICE}/approve", invoices_api.InvoiceApproveView.as_view(), name="invoice-approve"),
    path(f"{INVOICE}/void", invoices_api.InvoiceVoidView.as_view(), name="invoice-void"),
    path(f"{INVOICE}/copy", invoices_api.InvoiceCopyView.as_view(), name="invoice-copy"),
    path(
        f"{ORG}invoices/<uuid:public_id>/email",
        api.InvoiceEmailView.as_view(),
        name="invoice-email",
    ),
    path(
        f"{ORG}invoices/<uuid:public_id>/credit",
        api.InvoiceCreditView.as_view(),
        name="invoice-credit",
    ),
    path(
        f"{ORG}invoices/<uuid:public_id>/credit/override",
        api.InvoiceCreditOverrideView.as_view(),
        name="invoice-credit-override",
    ),
    path(f"{ORG}invoices/<uuid:public_id>/pdf", api.InvoicePdfView.as_view(), name="invoice-pdf"),
    path("invoice-view/<str:token>", api.InvoiceViewLinkView.as_view(), name="invoice-view"),
    path(f"{ORG}quotes", quotes_api.QuoteListView.as_view(), name="quotes"),
    path(QUOTE, quotes_api.QuoteDetailView.as_view(), name="quote"),
    path(f"{QUOTE}/send", quotes_api.QuoteSendView.as_view(), name="quote-send"),
    path(f"{QUOTE}/link", quotes_api.QuoteLinkView.as_view(), name="quote-link"),
    path(f"{QUOTE}/accept", quotes_api.QuoteAcceptView.as_view(), name="quote-accept"),
    path(f"{QUOTE}/decline", quotes_api.QuoteDeclineView.as_view(), name="quote-decline"),
    path(f"{QUOTE}/invoice", quotes_api.QuoteInvoiceView.as_view(), name="quote-invoice"),
    path(f"{QUOTE}/copy", quotes_api.QuoteCopyView.as_view(), name="quote-copy"),
    path(f"{QUOTE}/revise", quotes_api.QuoteReviseView.as_view(), name="quote-revise"),
    path(f"{QUOTE}/pdf", quotes_api.QuotePdfView.as_view(), name="quote-pdf"),
    path(PUBLIC_QUOTE, api.PublicQuoteView.as_view(), name="quote-public"),
    path(
        f"{PUBLIC_QUOTE}/preview",
        quotes_api.PublicQuotePreviewView.as_view(),
        name="quote-public-preview",
    ),
    path(
        f"{PUBLIC_QUOTE}/accept",
        quotes_api.PublicQuoteAcceptView.as_view(),
        name="quote-public-accept",
    ),
    path(
        f"{PUBLIC_QUOTE}/decline",
        quotes_api.PublicQuoteDeclineView.as_view(),
        name="quote-public-decline",
    ),
    path(f"{PUBLIC_QUOTE}/pdf", quotes_api.PublicQuotePdfView.as_view(), name="quote-public-pdf"),
]
