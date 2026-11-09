"""Tenancy API routes, mounted under /api/v1/ (A-01-T13)."""

from django.urls import path

from . import api

urlpatterns = [
    path("me/organisations", api.MyOrganisationsView.as_view(), name="me-organisations"),
    path("practices", api.PracticeCreateView.as_view(), name="practices"),
    path("organisations", api.OrganisationCreateView.as_view(), name="organisations"),
]
