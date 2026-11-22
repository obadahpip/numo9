"""Permissions of the shared document grid (D-01)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

SALES_DOCUMENTS_VIEW = register(
    Permission(
        "sales.document.view",
        _("See quotes, invoices and credit notes and how their amounts are worked out"),
        "sales",
        Risk.LOW,
    )
)

PURCHASE_DOCUMENTS_VIEW = register(
    Permission(
        "purchases.document.view",
        _("See bills, purchase orders and supplier credits and how their amounts are worked out"),
        "purchases",
        Risk.LOW,
    )
)
