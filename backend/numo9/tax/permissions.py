"""Permissions of the tax engine (G-01)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

TAX_VIEW = register(
    Permission(
        "tax.codes.view",
        _("See tax codes, rates and their history"),
        "tax",
        Risk.LOW,
    )
)

TAX_MANAGE = register(
    Permission(
        "tax.manage",
        _("Add, version, archive and restore tax codes and rates"),
        "tax",
        Risk.HIGH,
    )
)

# ---- GST/HST returns (G-03-T10) ------------------------------------------------------------------

RETURNS_VIEW = register(
    Permission(
        "tax.returns.view",
        _("See GST/HST returns, their lines and documents"),
        "tax",
        Risk.LOW,
    )
)

RETURNS_PREPARE = register(
    Permission(
        "tax.returns.prepare",
        _("Prepare and recalculate GST/HST returns"),
        "tax",
        Risk.MEDIUM,
    )
)

RETURNS_FILE = register(
    Permission(
        "tax.returns.file",
        _("Review, file and amend GST/HST returns (the reviewer isn't the preparer)"),
        "tax",
        Risk.HIGH,
    )
)
