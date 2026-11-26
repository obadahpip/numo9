"""Permissions of the conversion balances (C-05)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

CONVERSION_VIEW = register(
    Permission(
        "accounting.conversion.view",
        _("See the conversion balances, open documents and the difference"),
        "accounting",
        Risk.LOW,
    )
)

CONVERSION_MANAGE = register(
    Permission(
        "accounting.conversion.manage",
        _(
            "Enter and finalise the conversion balances (advisers post corrections after "
            "finalising)"
        ),
        "accounting",
        Risk.HIGH,
    )
)
