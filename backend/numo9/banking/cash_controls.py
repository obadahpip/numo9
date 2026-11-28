"""Negative-balance & cash controls (F-07).

**Policy** (F-07-T01) — per organisation and bank-account type, ``CashControlPolicy`` says what
a posting that would take an account below zero meets, by level: ``standard`` (people who aren't
advisers) and ``adviser``. ``DEFAULTS`` when the organisation never changed it:

=================  ==========  =========
account type       standard    adviser
=================  ==========  =========
Cash / petty cash  BLOCK       WARN
Chequing           WARN        WARN
Savings            WARN        WARN
Clearing           WARN        WARN
=================  ==========  =========

Credit cards, lines of credit and loans are liabilities and are never checked. A ledger bank
account without a bank profile (a template account no one attached yet) is treated as Cash —
the strictest — which is also what the C-03 journal guard did for every bank account.

``effective_policies(organisation)`` — the action pair for every controlled type (row or
default); ``seed_cash_policies(organisation)`` writes the default rows — for every new
organisation (``post_save``) and, by the data migration, every existing one (idempotent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from numo9.tenancy.context import org_context

from .models import (
    CONTROLLED_TYPES,
    BankAccountType,
    CashControlAction,
    CashControlPolicy,
)

A = CashControlAction
T = BankAccountType

STANDARD = "standard"
ADVISER = "adviser"
LEVELS = (STANDARD, ADVISER)


@dataclass(frozen=True)
class Actions:
    standard: str
    adviser: str

    def for_level(self, level: str) -> str:
        return self.adviser if level == ADVISER else self.standard


DEFAULTS: dict[str, Actions] = {
    T.CASH: Actions(A.BLOCK, A.WARN),
    T.CHEQUING: Actions(A.WARN, A.WARN),
    T.SAVINGS: Actions(A.WARN, A.WARN),
    T.CLEARING: Actions(A.WARN, A.WARN),
}
#: The type a ledger bank account without a bank profile is treated as (module docstring).
UNPROFILED_TYPE = T.CASH


def is_controlled(account_type: str) -> bool:
    return account_type in CONTROLLED_TYPES


def effective_policies(organisation: Any) -> dict[str, Actions]:
    """``{account type: Actions}`` for every controlled type: the stored row, else the default."""
    with org_context(organisation):
        rows = {
            row.account_type: Actions(row.standard_action, row.adviser_action)
            for row in CashControlPolicy.objects.all()
        }
    return {kind: rows.get(kind, DEFAULTS[kind]) for kind in CONTROLLED_TYPES}


def seed_cash_policies(organisation: Any, model: Any = None) -> int:
    """Create the default rows the organisation lacks (by type); returns how many were made.

    Written as one bulk insert by the platform when the organisation is created (no audit event
    per row, like the default payment terms); ``model`` lets the data migration pass its
    historical model. Changes people make afterwards are audited (``AuditedModel``)."""
    model = model or CashControlPolicy
    have = set(
        model._base_manager.filter(organisation_id=organisation.pk).values_list(
            "account_type", flat=True
        )
    )
    rows = [
        model(
            organisation_id=organisation.pk,
            account_type=kind,
            standard_action=DEFAULTS[kind].standard,
            adviser_action=DEFAULTS[kind].adviser,
        )
        for kind in CONTROLLED_TYPES
        if kind not in have
    ]
    if rows:
        model._base_manager.bulk_create(rows, ignore_conflicts=True)
    return len(rows)
