"""Notification centre routes (A-07-T01), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}notifications", api.NotificationListView.as_view(), name="notifications"),
    path(
        f"{ORG}notifications/unread-count",
        api.UnreadCountView.as_view(),
        name="notifications-unread-count",
    ),
    path(
        f"{ORG}notifications/read-all",
        api.MarkAllReadView.as_view(),
        name="notifications-read-all",
    ),
    path(
        f"{ORG}notifications/preferences",
        api.PreferencesView.as_view(),
        name="notifications-preferences",
    ),
    path(
        f"{ORG}notifications/<uuid:public_id>/read",
        api.MarkReadView.as_view(),
        name="notification-read",
    ),
]
