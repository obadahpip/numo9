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
    path("platform/practices", api.PlatformPracticeListView.as_view(), name="platform-practices"),
]
