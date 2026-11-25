"""Permissions of purchase orders and receipts (E-01) and bills (E-02)."""

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
