"""Permissions of sales invoices (D-03a)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

INVOICES_VIEW = register(
    Permission("sales.invoices.view", _("See invoices, their PDF and emails"), "sales", Risk.LOW)
)

INVOICES_WRITE = register(
    Permission("sales.invoices.write", _("Create and edit draft invoices"), "sales", Risk.MEDIUM)
)

INVOICES_APPROVE = register(
    Permission(
        "sales.invoices.approve",
        _("Approve, post and void invoices"),
        "sales",
        Risk.HIGH,
    )
)

INVOICES_SEND = register(
    Permission("sales.invoices.send", _("Email invoices to customers"), "sales", Risk.MEDIUM)
)

# ---- Quotes (D-02) -----------------------------------------------------------------------------

QUOTES_VIEW = register(
    Permission("sales.quotes.view", _("See quotes and their PDF"), "sales", Risk.LOW)
)
QUOTES_MANAGE = register(
    Permission(
        "sales.quotes.manage",
        _("Create, edit and send quotes, and turn accepted quotes into invoices"),
        "sales",
        Risk.MEDIUM,
    )
)
