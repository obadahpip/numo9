"""General ledger routes (C-02), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}journals", api.JournalListView.as_view(), name="journals"),
    path(f"{ORG}journals/<uuid:public_id>", api.JournalDetailView.as_view(), name="journal"),
]
