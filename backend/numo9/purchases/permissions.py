"""Permissions of purchase orders and receipts (E-01)."""

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
