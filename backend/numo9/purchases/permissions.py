"""Permissions of purchase orders and receipts (E-01), bills (E-02) and expense claims (E-04)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

PO_VIEW = register(
    Permission(
        "purchases.orders.view", _("See purchase orders and goods receipts"), "purchases", Risk.LOW
    )
)
PO_WRITE = register(
    Permission(
        "purchases.orders.write",
        _("Create, edit, send and cancel purchase orders"),
        "purchases",
        Risk.MEDIUM,
    )
)
PO_APPROVE = register(
    Permission(
        "purchases.orders.approve",
        _("Approve purchase orders, within an approval limit"),
        "purchases",
        Risk.HIGH,
    )
)
PO_RECEIVE = register(
    Permission(
        "purchases.orders.receive",
        _("Record and reverse goods receipts"),
        "purchases",
        Risk.MEDIUM,
    )
)

# ---- Bills (E-02) ------------------------------------------------------------------------------

BILLS_VIEW = register(
    Permission("purchases.bills.view", _("See supplier bills"), "purchases", Risk.LOW)
)
BILLS_WRITE = register(
    Permission(
        "purchases.bills.write",
        _("Enter, edit and void supplier bills and release holdbacks"),
        "purchases",
        Risk.MEDIUM,
    )
)
BILLS_APPROVE = register(
    Permission(
        "purchases.bills.approve",
        _("Approve supplier bills for payment, within an approval limit"),
        "purchases",
        Risk.HIGH,
    )
)

# ---- Expense claims (E-04) ---------------------------------------------------------------------

EXPENSES_VIEW = register(
    Permission(
        "purchases.expenses.view", _("See expense claims and their receipts"), "purchases", Risk.LOW
    )
)
EXPENSES_WRITE = register(
    Permission(
        "purchases.expenses.write",
        _("Enter and submit expense claims for others"),
        "purchases",
        Risk.MEDIUM,
    )
)
EXPENSES_APPROVE = register(
    Permission(
        "purchases.expenses.approve",
        _("Approve or reject expense claims, within an approval limit"),
        "purchases",
        Risk.HIGH,
    )
)
EXPENSES_OWN = register(
    Permission(
        "purchases.expenses.own",
        _("Enter, submit and see your own expense claims"),
        "purchases",
        Risk.LOW,
    )
)
