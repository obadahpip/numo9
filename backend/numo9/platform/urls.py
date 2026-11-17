"""Platform console API routes (U-06), mounted under /api/v1/."""

from django.urls import path

from . import api

urlpatterns = [
    path("platform/me", api.PlatformMeView.as_view(), name="platform-me"),
    path(
        "platform/organisations",
        api.PlatformOrganisationListView.as_view(),
        name="platform-organisations",
    ),
    path(
        "platform/organisations/<uuid:org_id>",
        api.PlatformOrganisationDetailView.as_view(),
        name="platform-organisation",
    ),
    path("platform/metrics", api.PlatformMetricsView.as_view(), name="platform-metrics"),
    path(
        "platform/metrics/<str:metric>/organisations",
        api.PlatformMetricDrillDownView.as_view(),
        name="platform-metric-drill-down",
    ),
    path(
        "platform/impersonation", api.ImpersonationStartView.as_view(), name="platform-impersonate"
    ),
    path(
        "platform/impersonation/current",
        api.ImpersonationCurrentView.as_view(),
        name="platform-impersonation-current",
    ),
    path(
        "platform/impersonation/end",
        api.ImpersonationEndView.as_view(),
        name="platform-impersonation-end",
    ),
    path("platform/practices", api.PlatformPracticeListView.as_view(), name="platform-practices"),
]
