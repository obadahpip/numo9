"""Tenancy API routes, mounted under /api/v1/ (A-01-T13)."""

from django.urls import path

from . import api, invitations_api

urlpatterns = [
    path("me/organisations", api.MyOrganisationsView.as_view(), name="me-organisations"),
    path("practices", api.PracticeCreateView.as_view(), name="practices"),
    path("organisations", api.OrganisationCreateView.as_view(), name="organisations"),
    # Invitations (A-02-T09)
    path("invitations", invitations_api.InvitationCreateView.as_view(), name="invitations"),
    path(
        "invitations/preview",
        invitations_api.InvitationPreviewView.as_view(),
        name="invitations-preview",
    ),
    path(
        "invitations/accept",
        invitations_api.InvitationAcceptView.as_view(),
        name="invitations-accept",
    ),
    path(
        "invitations/<uuid:invitation_id>/resend",
        invitations_api.InvitationResendView.as_view(),
        name="invitations-resend",
    ),
    path(
        "invitations/<uuid:invitation_id>/revoke",
        invitations_api.InvitationRevokeView.as_view(),
        name="invitations-revoke",
    ),
]
