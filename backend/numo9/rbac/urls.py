"""Roles and permissions API routes, mounted under /api/v1/ (A-03-T09)."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(
        "permissions/catalogue",
        api.PermissionCatalogueView.as_view(),
        name="permissions-catalogue",
    ),
    path(f"{ORG}roles", api.RoleListView.as_view(), name="roles"),
    path(f"{ORG}roles/<uuid:role_id>", api.RoleDetailView.as_view(), name="role"),
    path(f"{ORG}members", api.MemberListView.as_view(), name="members"),
    path(
        f"{ORG}members/<uuid:user_id>/roles",
        api.MemberRolesView.as_view(),
        name="member-roles",
    ),
    path(
        f"{ORG}members/<uuid:user_id>/roles/<uuid:role_id>",
        api.MemberRoleDetailView.as_view(),
        name="member-role",
    ),
    path(f"{ORG}my-permissions", api.MyPermissionsView.as_view(), name="my-permissions"),
    path(f"{ORG}invitations", api.PendingInvitationsView.as_view(), name="pending-invitations"),
    path(f"{ORG}approval-limits", api.ApprovalLimitListView.as_view(), name="approval-limits"),
    path(
        f"{ORG}approval-limits/<uuid:public_id>",
        api.ApprovalLimitDetailView.as_view(),
        name="approval-limit",
    ),
]
