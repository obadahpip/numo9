"""Conversion balances routes (C-05-T09), under /api/v1/o/<org>/conversion/."""

from django.urls import path

from . import api

BASE = "o/<uuid:org>/conversion/"

urlpatterns = [
    path(BASE, api.ConversionView.as_view(), name="conversion"),
    path(f"{BASE}lines", api.ConversionLinesView.as_view(), name="conversion-lines"),
    path(f"{BASE}documents", api.ConversionDocumentsView.as_view(), name="conversion-documents"),
    path(
        f"{BASE}documents/remove",
        api.ConversionDocumentsRemoveView.as_view(),
        name="conversion-documents-remove",
    ),
    path(f"{BASE}difference", api.ConversionDifferenceView.as_view(), name="conversion-difference"),
    path(f"{BASE}finalise", api.ConversionFinaliseView.as_view(), name="conversion-finalise"),
    path(
        f"{BASE}import/mapping",
        api.ConversionImportMappingView.as_view(),
        name="conversion-import-mapping",
    ),
    path(f"{BASE}import", api.ConversionImportView.as_view(), name="conversion-import"),
    path(
        f"{BASE}corrections",
        api.ConversionCorrectionsView.as_view(),
        name="conversion-corrections",
    ),
]
