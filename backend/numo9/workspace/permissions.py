"""Permissions of the accountant workspace (V-01)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, Scope, register

DIRECTORY_VIEW = register(
    Permission(
        "practice.directory.view",
        _("See the practice's client organisations in the directory"),
        "practice",
        Risk.LOW,
        Scope.PRACTICE,
    )
)
