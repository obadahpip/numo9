"""Job tray (A-08-T06) and platform console job dashboard (A-08-T08) routes, under /api/v1/."""

from django.urls import path

from . import api, console

ORG = "o/<uuid:org>/"
CONSOLE = "platform/jobs"

urlpatterns = [
    path(f"{ORG}jobs", api.JobListView.as_view(), name="jobs"),
    path(f"{ORG}jobs/events", api.JobEventsView.as_view(), name="jobs-events"),
    path(f"{ORG}jobs/<uuid:public_id>", api.JobDetailView.as_view(), name="job"),
    path(f"{ORG}jobs/<uuid:public_id>/retry", api.JobRetryView.as_view(), name="job-retry"),
    path(f"{CONSOLE}", console.ConsoleJobListView.as_view(), name="console-jobs"),
    path(
        f"{CONSOLE}/overview", console.ConsoleOverviewView.as_view(), name="console-jobs-overview"
    ),
    path(f"{CONSOLE}/purge", console.ConsolePurgeView.as_view(), name="console-jobs-purge"),
    path(
        f"{CONSOLE}/<uuid:public_id>",
        console.ConsoleJobDetailView.as_view(),
        name="console-job",
    ),
    path(
        f"{CONSOLE}/<uuid:public_id>/retry",
        console.ConsoleJobRetryView.as_view(),
        name="console-job-retry",
    ),
]
