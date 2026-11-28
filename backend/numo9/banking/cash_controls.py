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

**Pre-post hook** (F-07-T03) — ``assess(checked, organisation, person, today)`` is the posting
pipeline's cash policy (registered in ``numo9.ledger.policy.CASH_POLICY`` by the banking app):
for every bank/cash account (asset, sub-type Bank, accounting view) a posting of **any source**
takes money out of, the projector's lowest balance from the posting's date on (F-07-T02 — the
worst of that date, every later day and today) and, when it goes below zero, the action of the
account type's policy for the person's level (``adviser`` for advisers, ``standard`` for
everyone else). ``numo9.ledger.policy.cash_rule`` turns them into ``NegativeBalanceBlocked``
(BLOCK, or WARN for someone without ``accounting.banking.allow_negative``) or
``NegativeBalanceWarning`` (WARN without a reason). Liabilities (cards, lines of credit, loans)
are never sub-type Bank assets, so never checked.

**Concurrency** (F-07-T05) — ``assess`` locks the bank account rows first (``lock_accounts``):
the check and the post are serialised per account.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from dataclasses import replace as _replace
from decimal import Decimal
from typing import Any

from numo9.tenancy.context import org_context

from .models import (
    CONTROLLED_TYPES,
    BankAccount,
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


def level_of(person: Any, organisation: Any) -> str:
    from numo9.orgsettings.locks import is_adviser

    return ADVISER if is_adviser(person, organisation) else STANDARD


def _changes(checked: Any) -> dict[int, tuple[Any, Decimal]]:
    from numo9.ledger.cash_guard import ACCOUNTING_VIEW, is_cash

    changes: dict[int, tuple[Any, Decimal]] = {}
    for line in checked.lines:
        if line.book not in ACCOUNTING_VIEW or not is_cash(line.account):
            continue
        account, change = changes.get(line.account.pk, (line.account, Decimal("0.00")))
        changes[line.account.pk] = (account, change + line.debit - line.credit)
    return changes


def lock_accounts(organisation: Any, ledger_ids: list[int]) -> dict[int, str]:
    """F-07-T05: ``SELECT … FOR UPDATE`` on the bank account rows (the ledger account's row for
    a bank account without a profile) of the accounts a posting takes money out of, in id order
    (no deadlock between two postings on the same accounts). The posting service runs the check
    and the insert in one transaction, so the lock is held until the posting commits: a second
    posting on the account waits, then projects with the first one's lines — two concurrent
    spends can't both pass a BLOCK. Returns ``{ledger account id: bank-account type}``."""
    from numo9.ledger.models import Account

    with org_context(organisation):
        banks = list(
            BankAccount._base_manager.select_for_update()
            .filter(organisation_id=organisation.pk, gl_account_id__in=ledger_ids)
            .order_by("pk")
            .values_list("gl_account_id", "type")
        )
        types = dict(banks)
        loose = [pk for pk in ledger_ids if pk not in types]
        if loose:
            list(
                Account._base_manager.select_for_update()
                .filter(organisation_id=organisation.pk, pk__in=loose)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
    return types


def assess(checked: Any, organisation: Any, person: Any, today: dt.date) -> list[Any]:
    """The posting's bank/cash accounts that go below zero, with the policy's action
    (``numo9.ledger.cash_guard.Projection`` with ``action`` and ``account_type``)."""
    from numo9.ledger.cash_guard import Projection

    from .projector import minimum_running_balance

    taken = {pk: v for pk, v in _changes(checked).items() if v[1] < 0}
    if not taken:
        return []
    types = lock_accounts(organisation, sorted(taken))
    policies = effective_policies(organisation)
    level = level_of(person, organisation)
    date = checked.spec.date
    found: list[Any] = []
    for pk, (account, change) in taken.items():
        kind = types.get(pk, UNPROFILED_TYPE)
        if not is_controlled(kind):
            continue
        projected = minimum_running_balance(account, date, change, today=today)
        if not projected.goes_negative:
            continue
        projection = Projection(
            account,
            change,
            projected.at_date,
            date,
            projected.at_today,
            today,
            projected.lowest,
            projected.lowest_on,
        )
        found.append(
            _replace(projection, action=policies[kind].for_level(level), account_type=kind)
        )
    return found
