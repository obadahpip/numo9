"""F-07-T01 — ``CashControlPolicy`` per organisation and bank-account type (ALLOW / WARN / BLOCK
for people who aren't advisers and for advisers), defaults seeded.

Acceptance: defaults — Cash BLOCK (non-adviser) / WARN (adviser), Chequing WARN, Savings WARN.
Also: every new organisation gets the rows (seeding is idempotent); liabilities (credit card,
line of credit, loan) can't have a policy; a stored change wins over the default; one row per
organisation and type; organisation-scoped.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.banking.cash_controls import (
    ADVISER,
    DEFAULTS,
    STANDARD,
    effective_policies,
    is_controlled,
    seed_cash_policies,
)
from numo9.banking.models import CashControlPolicy
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def test_defaults_cash_block_warn_chequing_and_savings_warn() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    policies = effective_policies(org)
    assert (policies["cash"].for_level(STANDARD), policies["cash"].for_level(ADVISER)) == (
        "block",
        "warn",
    )
    for kind in ("chequing", "savings"):
        assert (policies[kind].standard, policies[kind].adviser) == ("warn", "warn")
    assert set(policies) == {"chequing", "savings", "cash", "clearing"}
    assert policies == DEFAULTS


def test_new_organisation_is_seeded_and_seeding_is_idempotent() -> None:
    org = Organisation.objects.create(name="Seeded Co.")
    with org_context(org):
        rows = {
            row.account_type: (row.standard_action, row.adviser_action)
            for row in CashControlPolicy.objects.all()
        }
    assert rows == {
        "cash": ("block", "warn"),
        "chequing": ("warn", "warn"),
        "savings": ("warn", "warn"),
        "clearing": ("warn", "warn"),
    }
    assert seed_cash_policies(org) == 0
    with org_context(org):
        assert CashControlPolicy.objects.count() == 4
    other = Organisation.objects.create(name="Other Co.")
    with org_context(other):
        assert CashControlPolicy.objects.count() == 4  # its own rows only


def test_liabilities_are_excluded_and_one_row_per_type() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    for kind in ("credit_card", "line_of_credit", "loan"):
        assert not is_controlled(kind)
        with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
            CashControlPolicy.objects.create(
                organisation=org, account_type=kind, standard_action="warn", adviser_action="warn"
            )
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        CashControlPolicy.objects.create(
            organisation=org, account_type="cash", standard_action="warn", adviser_action="warn"
        )


def test_a_stored_change_wins_over_the_default() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        row = CashControlPolicy.objects.get(account_type="chequing")
        row.standard_action = "block"
        row.save()
        CashControlPolicy.objects.filter(account_type="savings").delete()
    policies = effective_policies(org)
    assert policies["chequing"].standard == "block"
    assert policies["savings"] == DEFAULTS["savings"]  # a missing row reads as the default
