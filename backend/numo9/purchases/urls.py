"""Purchases routes (E-02 bills), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}bills/check-number", api.BillNumberCheckView.as_view(), name="bill-check-number"),
]
