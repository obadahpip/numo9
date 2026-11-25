"""Sales routes (D-03a), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
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
