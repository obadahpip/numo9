"""Sales routes (D-03a), under /api/v1/: invoices CRUD and actions (T11), email (T12)."""

from django.urls import path

from . import api, invoices_api

ORG = "o/<uuid:org>/"
INVOICE = f"{ORG}invoices/<uuid:public_id>"

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
    path("q/<str:token>", api.PublicQuoteView.as_view(), name="quote-public"),
]
