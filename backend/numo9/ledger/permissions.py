"""Permissions of the general ledger (C-01, C-02)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

JOURNALS_VIEW = register(
    Permission(
        "accounting.journals.view",
        _("See journals and every posted entry"),
        "accounting",
        Risk.LOW,
    )
)
