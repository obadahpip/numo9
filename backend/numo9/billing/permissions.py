"""Permissions of billing (U-04): the organisation's owner only — never practice staff.

Both are ``owner_only``: the owner system role has them; admins and practice admins (who get every
organisation permission but the owner-only ones) don't. A custom role may grant them.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

BILLING_VIEW = register(
    Permission(
        "organisation.billing.view",
        _("See the subscription, payment method and Numo9 invoices"),
        "settings",
        Risk.HIGH,
        owner_only=True,
    )
)
BILLING_MANAGE = register(
    Permission(
        "organisation.billing.manage",
        _("Subscribe, change the package or payment method, cancel the subscription"),
        "settings",
        Risk.CRITICAL,
        owner_only=True,
    )
)
