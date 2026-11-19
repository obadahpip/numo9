"""Permissions of contacts (B-01)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

CREDIT_OVERRIDE = register(
    Permission(
        "contacts.credit_limit.override",
        _("Approve sales over a customer's credit limit"),
        "contacts",
        Risk.CRITICAL,
    )
)

CONTACTS_VIEW = register(
    Permission(
        "contacts.contacts.view",
        _("See contacts: customers, suppliers and their people"),
        "contacts",
        Risk.LOW,
    )
)

CONTACTS_MANAGE = register(
    Permission(
        "contacts.contacts.manage",
        _("Add, edit, archive and merge contacts"),
        "contacts",
        Risk.MEDIUM,
    )
)
