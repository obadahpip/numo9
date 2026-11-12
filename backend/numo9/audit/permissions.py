"""Permissions of the audit log (A-04-T07, T08)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, Scope, register

AUDIT_VIEW = register(
    Permission(
        "audit.log.view",
        _("See the audit log and the history of records"),
        "settings",
        Risk.MEDIUM,
    )
)
AUDIT_EXPORT = register(
    Permission("audit.log.export", _("Export the audit log"), "settings", Risk.MEDIUM)
)
PLATFORM_AUDIT_VIEW = register(
    Permission(
        "platform.audit.view",
        _("See the platform audit log: sign-ins, 2FA and practice events"),
        "platform",
        Risk.HIGH,
        Scope.PLATFORM,
    )
)
