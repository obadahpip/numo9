"""Reports routes (K-01), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}reports/<slug:report>/drill", api.ReportDrillView.as_view(), name="report-drill"),
]
