"""Organisation settings routes (A-05), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(
        f"{ORG}settings/lock-dates/impact",
        api.LockImpactView.as_view(),
        name="settings-lock-impact",
    ),
]
