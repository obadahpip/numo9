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
