"""Permissions of the security baseline (S-03)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

SENSITIVE_REVEAL = register(
    Permission(
        "security.sensitive.reveal",
        _("Reveal hidden values such as SIN and bank account numbers (password confirmed, logged)"),
        "settings",
        Risk.HIGH,
    )
)
