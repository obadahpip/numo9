"""Contacts routes (B-01-T11, T12), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}contacts", api.ContactListView.as_view(), name="contacts"),
    path(
        f"{ORG}contacts/duplicates", api.ContactDuplicatesView.as_view(), name="contact-duplicates"
    ),
    path(f"{ORG}contacts/<uuid:public_id>", api.ContactDetailView.as_view(), name="contact"),
    path(
        f"{ORG}contacts/<uuid:public_id>/archive",
        api.ContactArchiveView.as_view(),
        name="contact-archive",
    ),
    path(
        f"{ORG}contacts/<uuid:public_id>/restore",
        api.ContactArchiveView.as_view(restore=True),
        name="contact-restore",
    ),
]
