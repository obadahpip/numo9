"""F-07-T10 — exceptions rule registration ``NEG_CASH`` (rule body in K-09-T06), read with the
F-07 projector.

Acceptance: the rule is listed in the catalogue — the engine's registry (from the ``cash`` rule
module, first in catalogue order), the rules API and the rules page (docs/specs/assurance-rules.md).
Also: its history comes from ``minimum_running_balance`` (the same figures as a day-by-day replay).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pytest

from numo9.assurance.rules import RULE_MODULES
from numo9.assurance.rules import cash as cash_rules
from numo9.assurance.rules.base import registry
from numo9.banking.projector import minimum_running_balance
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay

REPO = Path(__file__).resolve().parents[2]


def test_neg_cash_is_in_the_catalogue() -> None:
    assert "NEG_CASH" in registry.codes()
    rule = registry.get("NEG_CASH")
    assert type(rule).__module__ == "numo9.assurance.rules.cash"
    assert RULE_MODULES[0] == "cash"
    assert rule.has_fix and rule.default_severity == "critical"
    page = (REPO / "docs" / "specs" / "assurance-rules.md").read_text(encoding="utf-8")
    assert "| `NEG_CASH` |" in page


@pytest.mark.django_db
def test_history_uses_the_projector() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        from numo9.ledger.services import post_journal

        post_journal(pay(accounts["petty"], accounts["sales"], "100.00", dt.date(2026, 6, 1)))
        post_journal(pay(accounts["office"], accounts["petty"], "417.22", dt.date(2026, 6, 3)))
        post_journal(pay(accounts["petty"], accounts["sales"], "50.00", dt.date(2026, 6, 20)))
        with mock.patch(
            "numo9.assurance.rules.cash.minimum_running_balance", wraps=minimum_running_balance
        ) as projector:
            found = cash_rules.history(accounts["petty"], dt.date(2026, 6, 30))
        assert projector.called
        assert found == {
            "lowest": Decimal("-317.22"),
            "lowest_on": dt.date(2026, 6, 3),
            "first_negative_on": dt.date(2026, 6, 3),
            "today_balance": Decimal("-267.22"),
        }
        assert cash_rules.history(accounts["chequing"], dt.date(2026, 6, 30)) is None


@pytest.mark.django_db
def test_rules_api_lists_neg_cash() -> None:
    from django.test import Client

    from tests.journal_helpers import people

    org = Organisation.objects.create(name="Refined Interiors Inc.")
    client = Client()
    client.force_login(people(org)["adviser"])
    rules = client.get(f"/api/v1/o/{org.public_id}/assurance/rules").json()["rules"]
    assert "NEG_CASH" in [rule["code"] for rule in rules]
