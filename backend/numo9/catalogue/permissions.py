"""Permissions of the product catalogue (U-01-T10, T11)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, Scope, register

CATALOGUE_VIEW = register(
    Permission(
        "platform.catalogue.view",
        _("See products, feature keys and the feature matrix, and export it"),
        "platform",
        Risk.LOW,
        Scope.PLATFORM,
    )
)
