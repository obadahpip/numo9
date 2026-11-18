"""Bulk actions API routes (V-03-T07), under /api/v1/."""

from django.urls import path

from . import api

JOB = "practice/bulk/<uuid:job_id>"

urlpatterns = [
    path("practice/bulk", api.BulkJobCreateView.as_view(), name="practice-bulk"),
    path(JOB, api.BulkJobDetailView.as_view(), name="practice-bulk-job"),
    path(f"{JOB}/confirm", api.BulkJobConfirmView.as_view(), name="practice-bulk-confirm"),
    path(f"{JOB}/cancel", api.BulkJobCancelView.as_view(), name="practice-bulk-cancel"),
    path(f"{JOB}/rows", api.BulkJobRowsView.as_view(), name="practice-bulk-rows"),
    path(f"{JOB}/results.csv", api.BulkJobResultsCsvView.as_view(), name="practice-bulk-csv"),
    path(f"{JOB}/export", api.BulkJobExportView.as_view(), name="practice-bulk-export"),
]
