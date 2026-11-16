"""Billing routes (U-04), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}billing/checkout", api.CheckoutView.as_view(), name="billing-checkout"),
]
