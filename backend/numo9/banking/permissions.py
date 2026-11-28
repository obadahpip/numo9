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


BANKING_TRANSFER = register(
    Permission(
        "accounting.banking.transfer",
        _("Record and void transfers between bank, credit card, loan and cash accounts"),
        "accounting",
        Risk.MEDIUM,
    )
)

#: F-07: post past a negative-balance WARN with a reason ("bank.allow_negative" in the plan).
#: Advisers always may; every role that keeps the books gets it (not critical).
BANKING_ALLOW_NEGATIVE = register(
    Permission(
        "accounting.banking.allow_negative",
        _("Post a transaction that takes a bank or cash account below zero, with a reason"),
        "accounting",
        Risk.HIGH,
    )
)

#: F-07-T08: the Banking settings — the negative-balance policy per account type.
BANKING_SETTINGS = register(
    Permission(
        "accounting.banking.settings",
        _("Change banking settings: what happens when a posting would take an account below zero"),
        "accounting",
        Risk.HIGH,
    )
)
