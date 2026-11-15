from typing import Any

from django.apps import AppConfig


class FilesConfig(AppConfig):
    """File storage and the documents inbox (A-06): documents, attachments, storage, scanning,
    previews, inbound email."""

    name = "numo9.files"
    label = "files"
    verbose_name = "Files and documents"

    def ready(self) -> None:
        # Tenant sweep (A-01-T09, A-06-T14): a clean document of the organisation for every
        # documents endpoint (the generic factory can't fill the period and key formats).
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["files.Document"] = _sweep_document
        SWEEP_FACTORIES["files.InboundAddress"] = _sweep_inbound_address
        SWEEP_FACTORIES["files.Attachment"] = _sweep_attachment


def _sweep_document(organisation: Any) -> Any:
    from .models import Document, DocumentStatus
    from .storage import new_key

    document = Document(
        organisation=organisation,
        name="sweep.pdf",
        file_key=new_key(organisation, "sweep.pdf"),
        mime="application/pdf",
        size=10,
        status=DocumentStatus.CLEAN,
    )
    document.save()
    return document


def _sweep_inbound_address(organisation: Any) -> Any:
    from .inbound import inbound_address

    return inbound_address(organisation)


def _sweep_attachment(organisation: Any) -> Any:
    from django.contrib.contenttypes.models import ContentType

    from .models import Attachment, Document

    document = _sweep_document(organisation)
    link = Attachment(
        organisation=organisation,
        document=document,
        content_type=ContentType.objects.get_for_model(Document),
        object_public_id=document.public_id,
    )
    link.save()
    return link
