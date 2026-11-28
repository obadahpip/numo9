"""Permissions of banking (F-01)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

BANKING_VIEW = register(
    Permission(
        "accounting.banking.view",
        _("See bank, credit card and cash accounts, their balances and transactions"),
        "accounting",
        Risk.LOW,
    )
)

BANKING_MANAGE = register(
    Permission(
        "accounting.banking.manage",
        _("Add, rename, archive, restore and delete bank accounts"),
        "accounting",
        Risk.MEDIUM,
    )
)

BANKING_TRANSACT = register(
    Permission(
        "accounting.banking.transact",
        _("Record and void spend money and receive money"),
        "accounting",
        Risk.MEDIUM,
    )
)

BANKING_IMPORT = register(
    Permission(
        "accounting.banking.import",
        _("Import bank and credit-card statements, and undo an import"),
        "accounting",
        Risk.MEDIUM,
    )
)


BANKING_RULES = register(
    Permission(
        "accounting.banking.rules",
        _("Create, edit, reorder and delete bank rules"),
        "accounting",
        Risk.MEDIUM,
    )
)
