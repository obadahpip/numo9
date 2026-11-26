"""The organisation dashboard's widget library and role defaults (K-05-T02; wireframes:
``docs/design/wireframes/K-05-dashboard.md`` §2–3).

Every widget has a key, a name, the feature key that gates it (the API answers its gate, never an
error, K-05-T06) and the settings it accepts with their defaults. Nothing in the library
advertises anything (gap-04); Bank & cash is on the default of every role that may see banking.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from .models import DashboardRole

CORE = "@core"
MAX_WATCHLIST = 10


class BadSetting(ValueError):
    """``(widget key, setting name)`` of a refused setting."""


def _choice(*allowed: Any) -> Callable[[Any], Any]:
    def check(value: Any) -> Any:
        if value not in allowed:
            raise ValueError(value)
        return value

    return check


def _accounts(value: Any) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_WATCHLIST:
        raise ValueError(value)
    clean = [str(uuid.UUID(str(item))) for item in value]
    return list(dict.fromkeys(clean))


@dataclass(frozen=True)
class WidgetType:
    key: str
    name: Promise
    description: Promise
    feature: str
    #: Setting name → (default, validator returning the clean value or raising ``ValueError``).
    settings: dict[str, tuple[Any, Callable[[Any], Any]]] = field(default_factory=dict)

    def default_settings(self) -> dict[str, Any]:
        return {
            name: default
            for name, (default, _check) in self.settings.items()
            if default is not None
        }

    def clean_settings(self, given: Any) -> dict[str, Any]:
        """The widget's settings: defaults for the missing ones; unknown or invalid → BadSetting."""
        if given is None:
            given = {}
        if not isinstance(given, dict):
            raise BadSetting(self.key, "settings")
        clean = self.default_settings()
        for name, value in given.items():
            if name not in self.settings:
                raise BadSetting(self.key, str(name)[:40])
            try:
                clean[name] = self.settings[name][1](value)
            except (TypeError, ValueError):
                raise BadSetting(self.key, name) from None
        return clean


LIBRARY: dict[str, WidgetType] = {
    widget.key: widget
    for widget in (
        WidgetType(
            "bank_cash",
            _("Bank & cash balances"),
            _("Every bank, card and cash account, petty cash included."),
            "accounting.banking.read",
        ),
        WidgetType(
            "cash_in_out",
            _("Cash in and out"),
            _("Money in and out per month."),
            "accounting.banking.read",
            {"months": (6, _choice(3, 6, 12))},
        ),
        WidgetType(
            "invoices_owed",
            _("Invoices owed to you"),
            _("Awaiting payment and overdue invoices by age."),
            "accounting.sales_invoices.read",
        ),
        WidgetType(
            "bills_to_pay",
            _("Bills to pay"),
            _("Awaiting payment and overdue bills by age."),
            "accounting.bills.read",
        ),
        WidgetType(
            "deadlines",
            _("Tax and filing deadlines"),
            _("The next GST/HST and QST returns and payments, due soon or overdue."),
            "tax.returns.read",
        ),
        WidgetType(
            "pnl_snapshot",
            _("Profit and loss"),
            _("Income, expenses and net profit, month or year to date."),
            CORE,
            {"period": ("mtd", _choice("mtd", "ytd"))},
        ),
        WidgetType(
            "account_watchlist",
            _("Account watchlist"),
            _("The balances of up to 10 accounts you choose."),
            CORE,
            {"accounts": (None, _accounts)},
        ),
        WidgetType(
            "exceptions",
            _("Exceptions"),
            _("Open exceptions by severity."),
            CORE,
        ),
        WidgetType(
            "approvals",
            _("Awaiting my approval"),
            _("Documents waiting for your approval."),
            CORE,
        ),
    )
}

#: The default layout of each role, in order (wireframes §2).
ROLE_DEFAULTS: dict[str, tuple[str, ...]] = {
    DashboardRole.OWNER: (
        "bank_cash",
        "cash_in_out",
        "invoices_owed",
        "bills_to_pay",
        "deadlines",
        "pnl_snapshot",
        "approvals",
        "exceptions",
    ),
    DashboardRole.ACCOUNTANT: (
        "bank_cash",
        "exceptions",
        "deadlines",
        "pnl_snapshot",
        "account_watchlist",
        "invoices_owed",
        "bills_to_pay",
        "approvals",
    ),
    DashboardRole.SALES: ("invoices_owed", "approvals"),
    DashboardRole.PURCHASING: ("bills_to_pay", "approvals"),
    DashboardRole.BASIC: ("approvals", "deadlines"),
}

#: Organisation membership role → role default (practices serving the organisation: accountant).
MEMBER_ROLES: dict[str, str] = {
    "owner": DashboardRole.OWNER,
    "admin": DashboardRole.OWNER,
    "accountant_delegate": DashboardRole.ACCOUNTANT,
    "sales": DashboardRole.SALES,
    "purchasing": DashboardRole.PURCHASING,
}


def default_widgets(role: str) -> list[dict[str, Any]]:
    """The role's default layout as stored: ``[{"key", "settings"}]`` in order."""
    return [
        {"key": key, "settings": LIBRARY[key].default_settings()}
        for key in ROLE_DEFAULTS.get(role, ROLE_DEFAULTS[DashboardRole.BASIC])
    ]
