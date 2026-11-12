"""Job tray API routes, mounted under /api/v1/ (A-08-T06)."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}jobs", api.JobListView.as_view(), name="jobs"),
    path(f"{ORG}jobs/events", api.JobEventsView.as_view(), name="jobs-events"),
    path(f"{ORG}jobs/<uuid:public_id>", api.JobDetailView.as_view(), name="job"),
    path(f"{ORG}jobs/<uuid:public_id>/retry", api.JobRetryView.as_view(), name="job-retry"),
]
