"""C-03-T16 — fixtures: the REFINED teardown journals (417.22, 576.95) and the negative-cash
scenarios; ``make fixtures-phase1`` (``manage.py load_phase1_fixtures``) loads them.

Acceptance: loading creates REFINED with the two posted journals exactly as the teardown found
them (lines, dates, narrations) and Petty Cash at −994.17; loading again changes nothing; every
scenario gets the cash guard answer it documents — account, lowest balance and day.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from numo9.ledger.cash_guard import balance, shortfalls
from numo9.ledger.models import Account, JournalEntry
from numo9.ledger.phase1_fixtures import ORG_NAME, SCENARIOS, _accounts, spec_of
from numo9.ledger.validation import validate_journal
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 10, 26)  # the teardown's "as at"


def test_load_is_the_teardown_and_idempotent() -> None:
    out = StringIO()
    call_command("load_phase1_fixtures", stdout=out)
    call_command("load_phase1_fixtures", stdout=StringIO())
    assert "Petty Cash -994.17" in out.getvalue()
    (org,) = Organisation.objects.filter(name=ORG_NAME)
    with org_context(org):
        journals = {j.narration: j for j in JournalEntry.objects.all()}
        assert set(journals) == {"Opening deposit", "Ontario Corporation", "Las Vegas Trade Show"}
        first = journals["Ontario Corporation"]
        assert first.date == dt.date(2026, 6, 3) and first.status == "posted"
        assert [(line.account.code, line.debit, line.credit) for line in first.lines.all()] == [
            ("5590", Decimal("300.00"), Decimal("0.00")),
            ("5515", Decimal("26.99"), Decimal("0.00")),
            ("5515", Decimal("89.10"), Decimal("0.00")),
            ("5515", Decimal("1.13"), Decimal("0.00")),
            ("1000", Decimal("0.00"), Decimal("417.22")),
        ]
        second = journals["Las Vegas Trade Show"]
        assert (second.date, sum(line.credit for line in second.lines.all())) == (
            dt.date(2026, 6, 15),
            Decimal("576.95"),
        )
        assert balance(Account.objects.get(code="1000"), TODAY) == Decimal("-994.17")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.key for s in SCENARIOS])
def test_each_scenario_gets_the_documented_answer(scenario: object) -> None:
    call_command("load_phase1_fixtures", stdout=StringIO())
    org = Organisation.objects.get(name=ORG_NAME)
    with org_context(org):
        accounts = _accounts(org)
        checked = validate_journal(
            spec_of(accounts, scenario.date, scenario.key, scenario.lines)  # type: ignore[attr-defined]
        )
        found = shortfalls(checked, org, today=TODAY)
    assert [(p.account.code, f"{p.lowest:.2f}", p.lowest_on) for p in found] == list(
        scenario.expect  # type: ignore[attr-defined]
    )


def test_make_target_loads_them() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text()
    assert "fixtures-phase1:" in makefile
    assert "load_phase1_fixtures" in makefile
