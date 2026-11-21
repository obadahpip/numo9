"""Founding offer routes (U-08), under /api/v1/."""

from django.urls import path

from . import api, public

urlpatterns = [
    # Public counter (U-08-T08): anyone, cached 30 s.
    path("public/founding", public.PublicFoundingCounterView.as_view(), name="public-founding"),
    # Platform console (U-08-T11).
    path("platform/founding", api.FoundingOverviewView.as_view(), name="platform-founding"),
    path(
        "platform/founding/export",
        api.FoundingExportView.as_view(),
        name="platform-founding-export",
    ),
    path(
        "platform/founding/slots/<int:slot_no>/release",
        api.FoundingReleaseView.as_view(),
        name="platform-founding-release",
    ),
]
