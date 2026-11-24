"""Permissions of reports (K-01)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

REPORTS_VIEW = register(
    Permission(
        "reports.reports.view",
        _("Run reports and drill down to their lines"),
        "reports",
        Risk.LOW,
    )
)

LAYOUTS_MANAGE = register(
    Permission(
        "reports.layouts.manage",
        _("Edit, publish and save report layouts and notes"),
        "reports",
        Risk.MEDIUM,
    )
)
