"""Permissions of the documents inbox and attachments (A-06)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

FILES_VIEW = register(
    Permission(
        "documents.file.view",
        _("See the documents inbox, attached files and their previews"),
        "documents",
        Risk.LOW,
    )
)
FILES_UPLOAD = register(
    Permission(
        "documents.file.upload",
        _("Upload documents and see the inbox's email address"),
        "documents",
        Risk.MEDIUM,
    )
)
FILES_MANAGE = register(
    Permission(
        "documents.file.manage",
        _("Tag, archive and attach documents, and change the inbox's email address"),
        "documents",
        Risk.MEDIUM,
    )
)
