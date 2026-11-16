"""Notification centre routes (A-07-T01), under /api/v1/."""

from django.urls import path

from . import api, domains_api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}email-domains", domains_api.DomainListView.as_view(), name="email-domains"),
    path(
        f"{ORG}email-domains/<uuid:public_id>",
        domains_api.DomainDetailView.as_view(),
        name="email-domain",
    ),
    path(
        f"{ORG}email-domains/<uuid:public_id>/check",
        domains_api.DomainCheckView.as_view(),
        name="email-domain-check",
    ),
    path(
        f"{ORG}email-domains/<uuid:public_id>/refresh",
        domains_api.DomainRefreshView.as_view(),
        name="email-domain-refresh",
    ),
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
