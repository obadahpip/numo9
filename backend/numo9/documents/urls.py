"""Document calculation routes (D-01-T09), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(
        f"{ORG}documents/sales/calculate",
        api.SalesCalculateView.as_view(),
        name="documents-sales-calculate",
    ),
    path(
        f"{ORG}documents/sales/posting-preview",
        api.SalesPreviewView.as_view(),
        name="documents-sales-posting-preview",
    ),
    path(
        f"{ORG}documents/purchases/calculate",
        api.PurchaseCalculateView.as_view(),
        name="documents-purchases-calculate",
    ),
    path(
        f"{ORG}documents/purchases/posting-preview",
        api.PurchasePreviewView.as_view(),
        name="documents-purchases-posting-preview",
    ),
]
