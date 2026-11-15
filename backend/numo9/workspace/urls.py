"""Accountant workspace API routes, mounted under /api/v1/ (V-01)."""

from django.urls import path

from . import api, views_api

urlpatterns = [
    path("practice/orgs", api.DirectoryView.as_view(), name="practice-orgs"),
    path("practice/views", views_api.SavedViewListView.as_view(), name="practice-views"),
    path(
        "practice/views/<uuid:view_id>",
        views_api.SavedViewDetailView.as_view(),
        name="practice-view",
    ),
]
