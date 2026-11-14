"""Documents routes (A-06), under /api/v1/."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/files/"

urlpatterns = [
    # Inbound email from the provider (A-06-T07): not organisation-scoped, HMAC-signed.
    path("inbound/email", api.InboundEmailWebhookView.as_view(), name="files-inbound-email"),
    path("o/<uuid:org>/files", api.DocumentListView.as_view(), name="files-list"),
    path(f"{ORG}uploads", api.UploadView.as_view(), name="files-uploads"),
    path(f"{ORG}bulk", api.BulkView.as_view(), name="files-bulk"),
    path(f"{ORG}tags", api.TagListView.as_view(), name="files-tags"),
    path(f"{ORG}attachments", api.AttachmentListView.as_view(), name="files-attachments"),
    path(
        f"{ORG}attachments/<uuid:public_id>",
        api.AttachmentDetailView.as_view(),
        name="files-attachment",
    ),
    path(f"{ORG}inbound-address", api.InboundAddressView.as_view(), name="files-inbound-address"),
    path(
        f"{ORG}inbound-address/rotate",
        api.InboundAddressRotateView.as_view(),
        name="files-inbound-address-rotate",
    ),
    path(f"{ORG}<uuid:public_id>", api.DocumentDetailView.as_view(), name="files-detail"),
    path(f"{ORG}<uuid:public_id>/finalize", api.FinalizeView.as_view(), name="files-finalize"),
    path(f"{ORG}<uuid:public_id>/url", api.SignedUrlView.as_view(), name="files-url"),
    path(f"{ORG}<uuid:public_id>/actions", api.FileActionsView.as_view(), name="files-actions"),
]
