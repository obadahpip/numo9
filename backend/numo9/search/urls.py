"""Global search routes (A-09), under /api/v1/."""

from django.urls import path

from . import api

urlpatterns = [
    path("o/<uuid:org>/search", api.SearchView.as_view(), name="search"),
]
