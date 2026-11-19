"""Contacts routes (B-01-T11, T12), under /api/v1/."""

from django.urls import path

from . import activity_api, api

ORG = "o/<uuid:org>/"
C = f"{ORG}contacts/<uuid:public_id>"

urlpatterns = [
    path(f"{ORG}contacts", api.ContactListView.as_view(), name="contacts"),
    path(
        f"{ORG}contacts/duplicates", api.ContactDuplicatesView.as_view(), name="contact-duplicates"
    ),
    path(f"{ORG}contacts/merge", api.ContactMergeView.as_view(), name="contacts-merge"),
    path(
        f"{ORG}contacts/merge/preview",
        api.ContactMergePreviewView.as_view(),
        name="contacts-merge-preview",
    ),
    path(f"{ORG}contacts/<uuid:public_id>", api.ContactDetailView.as_view(), name="contact"),
    path(
        f"{ORG}contacts/<uuid:public_id>/archive",
        api.ContactArchiveView.as_view(),
        name="contact-archive",
    ),
    path(
        f"{ORG}contacts/<uuid:public_id>/restore",
        api.ContactRestoreView.as_view(),
        name="contact-restore",
    ),
    # Activity, statements and supplier reconciliation (B-02-T09)
    path(f"{C}/activity", activity_api.ActivityView.as_view(), name="contact-activity"),
    path(f"{C}/statement", activity_api.StatementView.as_view(), name="contact-statement"),
    path(
        f"{C}/statement.pdf", activity_api.StatementPdfView.as_view(), name="contact-statement-pdf"
    ),
    path(
        f"{C}/statement/send",
        activity_api.StatementSendView.as_view(),
        name="contact-statement-send",
    ),
    path(f"{C}/statements", activity_api.StatementHistoryView.as_view(), name="contact-statements"),
    path(
        f"{C}/supplier-statements",
        activity_api.SupplierStatementsView.as_view(),
        name="contact-supplier-statements",
    ),
    path(
        f"{C}/supplier-statements/<uuid:statement_id>/reconciliation",
        activity_api.ReconciliationView.as_view(),
        name="contact-reconciliation",
    ),
    path(
        f"{C}/supplier-statements/<uuid:statement_id>/lines/<uuid:line_id>",
        activity_api.ReconciliationLineView.as_view(),
        name="contact-reconciliation-line",
    ),
]
