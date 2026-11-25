"""Reports routes (K-01), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}reports", api.ReportCatalogueView.as_view(), name="report-catalogue"),
    path(
        f"{ORG}reports/layouts/<uuid:public_id>",
        api.ReportLayoutDetailView.as_view(),
        name="report-layout",
    ),
    path(
        f"{ORG}reports/layouts/<uuid:public_id>/publish",
        api.ReportLayoutPublishView.as_view(),
        name="report-layout-publish",
    ),
    path(f"{ORG}reports/<slug:report>/run", api.ReportRunView.as_view(), name="report-run"),
    path(
        f"{ORG}reports/<slug:report>/export", api.ReportExportView.as_view(), name="report-export"
    ),
    path(f"{ORG}reports/<slug:report>/drill", api.ReportDrillView.as_view(), name="report-drill"),
    path(
        f"{ORG}reports/<slug:report>/favourite",
        api.ReportFavouriteView.as_view(),
        name="report-favourite",
    ),
    path(
        f"{ORG}reports/<slug:report>/layouts",
        api.ReportLayoutListView.as_view(),
        name="report-layouts",
    ),
    path(f"{ORG}reports/<slug:report>/notes", api.ReportNoteView.as_view(), name="report-notes"),
]
