"""Imports routes (B-03-T11), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"
RUN = f"{ORG}imports/<uuid:public_id>"

urlpatterns = [
    path(f"{ORG}imports", api.ImportUploadView.as_view(), name="imports"),
    path(f"{ORG}imports/template", api.ImportTemplateView.as_view(), name="imports-template"),
    path(RUN, api.ImportDetailView.as_view(), name="import"),
    path(f"{RUN}/dry-run", api.ImportDryRunView.as_view(), name="import-dry-run"),
    path(f"{RUN}/rows", api.ImportRowsView.as_view(), name="import-rows"),
    path(f"{RUN}/apply", api.ImportApplyView.as_view(), name="import-apply"),
    path(f"{RUN}/errors.csv", api.ImportErrorsView.as_view(), name="import-errors"),
    path(f"{ORG}contacts/export", api.ContactExportView.as_view(), name="contacts-export"),
]
