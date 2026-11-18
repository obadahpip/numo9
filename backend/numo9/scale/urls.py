"""Scale tooling routes, under /api/v1/ (S-06-T09): the perf-only posting endpoint."""

from django.urls import path

from . import api

urlpatterns = [
    path("o/<uuid:org>/perf/journal", api.PerfJournalView.as_view(), name="perf-journal"),
]
