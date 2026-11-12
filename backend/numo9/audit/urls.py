"""Audit log routes (A-04-T07…T11), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/audit/"

urlpatterns = [
    path(f"{ORG}events", api.AuditEventListView.as_view(), name="audit-events"),
    path(f"{ORG}events/<uuid:public_id>", api.AuditEventDetailView.as_view(), name="audit-event"),
    path(
        f"{ORG}records/<str:object_type>/<str:object_id>",
        api.AuditRecordHistoryView.as_view(),
        name="audit-record-history",
    ),
    path(
        f"{ORG}records/<str:object_type>/<str:object_id>/as-of",
        api.AuditRecordAsOfView.as_view(),
        name="audit-record-as-of",
    ),
    path(f"{ORG}filters", api.AuditFiltersView.as_view(), name="audit-filters"),
    path(f"{ORG}export/<str:kind>", api.AuditExportView.as_view(), name="audit-export"),
    path(
        "platform/audit/events", api.PlatformAuditListView.as_view(), name="platform-audit-events"
    ),
]
