"""Accountant workspace API routes, mounted under /api/v1/ (V-01)."""

from django.urls import path

from . import api, groups_api, views_api

urlpatterns = [
    path("practice/orgs", api.DirectoryView.as_view(), name="practice-orgs"),
    path("practice/views", views_api.SavedViewListView.as_view(), name="practice-views"),
    path(
        "practice/views/<uuid:view_id>",
        views_api.SavedViewDetailView.as_view(),
        name="practice-view",
    ),
    # Groups and tags (V-02-T07)
    path("practice/groups", groups_api.GroupListView.as_view(), name="practice-groups"),
    path(
        "practice/groups/<uuid:group_id>",
        groups_api.GroupDetailView.as_view(),
        name="practice-group",
    ),
    path(
        "practice/groups/<uuid:group_id>/impact",
        groups_api.GroupImpactView.as_view(),
        name="practice-group-impact",
    ),
    path(
        "practice/groups/<uuid:group_id>/organisations",
        groups_api.GroupOrganisationsView.as_view(),
        name="practice-group-organisations",
    ),
    path(
        "practice/groups/<uuid:group_id>/organisations/<uuid:org_id>",
        groups_api.GroupOrganisationView.as_view(),
        name="practice-group-organisation",
    ),
    path(
        "practice/groups/<uuid:group_id>/staff/<uuid:user_id>",
        groups_api.GroupStaffView.as_view(),
        name="practice-group-staff",
    ),
    path("practice/tags", groups_api.TagListView.as_view(), name="practice-tags"),
    path("practice/tags/<uuid:tag_id>", groups_api.TagDetailView.as_view(), name="practice-tag"),
    path(
        "practice/tags/<uuid:tag_id>/organisations",
        groups_api.TagOrganisationsView.as_view(),
        name="practice-tag-organisations",
    ),
    path(
        "practice/tags/<uuid:tag_id>/organisations/<uuid:org_id>",
        groups_api.TagOrganisationView.as_view(),
        name="practice-tag-organisation",
    ),
]
