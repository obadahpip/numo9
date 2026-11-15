"""Entitlements routes (U-03-T09), under /api/v1/."""

from django.urls import path

from . import api

urlpatterns = [
    path(
        "o/<uuid:org>/entitlements",
        api.EntitlementsView.as_view(),
        name="organisation-entitlements",
    ),
]
