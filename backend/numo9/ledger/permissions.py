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

JOURNALS_POST = register(
    Permission(
        "accounting.journals.post",
        _("Write and post manual journals"),
        "accounting",
        Risk.MEDIUM,
    )
)

JOURNALS_APPROVE = register(
    Permission(
        "accounting.journals.approve",
        _("Approve or send back manual journals waiting for approval (within an approval limit)"),
        "accounting",
        Risk.MEDIUM,
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

# ---- Period close and year-end (C-06) -----------------------------------------------------------

PERIOD_CLOSE_VIEW = register(
    Permission(
        "accounting.period_close.view",
        _("See closed periods and the close checklist"),
        "accounting",
        Risk.LOW,
    )
)

PERIOD_CLOSE_MANAGE = register(
    Permission(
        "accounting.period_close.manage",
        _("Close periods and the fiscal year (advisers reopen them)"),
        "accounting",
        Risk.HIGH,
    )
)

# ---- Find & recode (C-07-T09) --------------------------------------------------------------------

RECODE = register(
    Permission(
        "accounting.recode",
        _("Find and recode posted transactions in bulk, and undo a recode"),
        "accounting",
        Risk.HIGH,
    )
)
