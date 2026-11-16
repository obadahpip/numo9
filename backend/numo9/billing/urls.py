"""Billing routes (U-04), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}billing/checkout", api.CheckoutView.as_view(), name="billing-checkout"),
    path(f"{ORG}billing/change", api.ChangeView.as_view(), name="billing-change"),
    path(f"{ORG}billing/cancel", api.CancelView.as_view(), name="billing-cancel"),
    path(f"{ORG}billing/export", api.ExportView.as_view(), name="billing-export"),
    path(
        f"{ORG}billing/change/preview",
        api.ChangePreviewView.as_view(),
        name="billing-change-preview",
    ),
]
