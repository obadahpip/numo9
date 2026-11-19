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

ACCOUNTS_VIEW = register(
    Permission(
        "accounting.accounts.view",
        _("See the chart of accounts and account balances"),
        "accounting",
        Risk.LOW,
    )
)

ACCOUNTS_MANAGE = register(
    Permission(
        "accounting.accounts.manage",
        _("Add, edit, renumber, archive and restore accounts"),
        "accounting",
        Risk.MEDIUM,
    )
)
