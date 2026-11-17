"""Organisation settings routes (A-05), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}settings", api.SettingsView.as_view(), name="settings"),
    path(
        f"{ORG}settings/registrations",
        api.RegistrationListView.as_view(),
        name="settings-registrations",
    ),
    path(
        f"{ORG}settings/registrations/<uuid:public_id>",
        api.RegistrationDetailView.as_view(),
        name="settings-registration",
    ),
    path(f"{ORG}settings/lock-dates", api.LockDatesView.as_view(), name="settings-lock-dates"),
    path(f"{ORG}settings/numbering", api.NumberingView.as_view(), name="settings-numbering"),
    path(
        f"{ORG}settings/lock-dates/impact",
        api.LockImpactView.as_view(),
        name="settings-lock-impact",
    ),
]
