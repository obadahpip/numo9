"""C-04-T04 — RecurringJournalTemplate: lines JSON validated (shape, one side, two decimals,
balanced, this organisation's accounts and contacts), RFC 5545 rule validated (supported
frequencies, no DTSTART of its own), system types refused, end after start; a valid template
saves, organisation-scoped and audited.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from numo9.audit.models import AuditEvent
from numo9.ledger.models import RecurringJournalTemplate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.journal_helpers import chart

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def accounts(org: Organisation) -> dict[str, Any]:
    with org_context(org):
        return chart(org)


def lines(accounts: dict[str, Any], amount: str = "2400.00") -> list[dict[str, Any]]:
    return [
        {"account": str(accounts["rent"].public_id), "debit": amount, "description": "Rent"},
        {"account": str(accounts["chequing"].public_id), "credit": amount},
    ]


def template(org: Organisation, **fields: Any) -> RecurringJournalTemplate:
    values: dict[str, Any] = {
        "organisation": org,
        "name": "Monthly rent",
        "rrule": "FREQ=MONTHLY;INTERVAL=1",
        "start_date": dt.date(2026, 1, 31),
    }
    values.update(fields)
    return RecurringJournalTemplate(**values)


def codes(error: ValidationError) -> set[str]:
    return {e.code for errors in error.error_dict.values() for e in errors if e.code}


def test_a_valid_template_saves_normalised_and_audited(
    org: Organisation, accounts: dict[str, Any]
) -> None:
    with org_context(org):
        item = template(org, lines=lines(accounts, "2400"))
        item.full_clean()
        item.save()
        assert item.lines[0] == {
            "account": str(accounts["rent"].public_id),
            "debit": "2400.00",
            "credit": "0.00",
            "book": "both",
            "contact": None,
            "description": "Rent",
        }
        assert (item.mode, item.paused, item.version) == ("draft", False, 1)
        assert AuditEvent.objects.filter(
            object_type="ledger.RecurringJournalTemplate", object_id=str(item.public_id)
        ).exists()


@pytest.mark.parametrize(
    "rule",
    [
        "",
        "FREQ=FORTNIGHTLY",
        "FREQ=MONTHLY;INTERVAL=x",
        "FREQ=HOURLY",
        "DTSTART:20260101T000000\nRRULE:FREQ=MONTHLY",
        "not a rule",
    ],
)
def test_invalid_rules_are_refused(org: Organisation, accounts: dict[str, Any], rule: str) -> None:
    with org_context(org), pytest.raises(ValidationError) as caught:
        template(org, rrule=rule, lines=lines(accounts)).full_clean()
    assert "ledger.recurring.rrule_invalid" in codes(caught.value)


@pytest.mark.parametrize(
    "rule",
    ["FREQ=MONTHLY", "RRULE:FREQ=WEEKLY;BYDAY=MO", "FREQ=YEARLY;COUNT=3", "FREQ=DAILY;INTERVAL=7"],
)
def test_supported_rules(org: Organisation, accounts: dict[str, Any], rule: str) -> None:
    with org_context(org):
        template(org, rrule=rule, lines=lines(accounts)).full_clean()


def test_bad_lines(org: Organisation, accounts: dict[str, Any]) -> None:
    rent, bank = str(accounts["rent"].public_id), str(accounts["chequing"].public_id)
    cases: list[tuple[Any, str]] = [
        ([], "ledger.recurring.lines_invalid"),
        ([{"account": rent, "debit": "10.00"}], "ledger.recurring.lines_invalid"),
        (
            [{"account": rent, "debit": "10", "credit": "10"}, {"account": bank, "credit": "0"}],
            "ledger.recurring.lines_invalid",
        ),
        (
            [{"account": rent, "debit": "10.001"}, {"account": bank, "credit": "10.001"}],
            "ledger.recurring.lines_invalid",
        ),
        (
            [{"account": rent, "debit": "-5"}, {"account": bank, "credit": "-5"}],
            "ledger.recurring.lines_invalid",
        ),
        (
            [{"account": rent, "debit": "10", "colour": "red"}, {"account": bank, "credit": "10"}],
            "ledger.recurring.lines_invalid",
        ),
        (
            [{"account": rent, "debit": "10", "book": "x"}, {"account": bank, "credit": "10"}],
            "ledger.recurring.lines_invalid",
        ),
        (
            [{"account": rent, "debit": "10.00"}, {"account": bank, "credit": "9.50"}],
            "ledger.recurring.unbalanced",
        ),
        (
            [
                {"account": "00000000-0000-4000-8000-000000000000", "debit": "1"},
                {"account": bank, "credit": "1"},
            ],
            "ledger.recurring.account_unknown",
        ),
        (
            [{"account": "nope", "debit": "1"}, {"account": bank, "credit": "1"}],
            "ledger.recurring.account_unknown",
        ),
        (
            [
                {"account": rent, "debit": "1", "contact": "00000000-0000-4000-8000-000000000000"},
                {"account": bank, "credit": "1"},
            ],
            "ledger.recurring.contact_unknown",
        ),
    ]
    with org_context(org):
        for bad, code in cases:
            with pytest.raises(ValidationError) as caught:
                template(org, lines=bad).full_clean()
            assert code in codes(caught.value), (bad, caught.value)


def test_contact_type_and_dates(org: Organisation, accounts: dict[str, Any]) -> None:
    other = Organisation.objects.create(name="Other Co.")
    with org_context(other):
        stranger = contact(other, "Not ours")
    with org_context(org):
        mine = contact(org, "Kingsway Properties", roles=["supplier"])
        good = lines(accounts)
        good[0]["contact"] = str(mine.public_id)
        template(org, lines=good).full_clean()
        good[0]["contact"] = str(stranger.public_id)  # another organisation's: not found here
        with pytest.raises(ValidationError) as caught:
            template(org, lines=good).full_clean()
        assert "ledger.recurring.contact_unknown" in codes(caught.value)
        with pytest.raises(ValidationError) as caught:
            template(org, lines=lines(accounts), journal_type="payroll").full_clean()
        assert "ledger.recurring.type_invalid" in codes(caught.value)
        with pytest.raises(ValidationError) as caught:
            template(org, lines=lines(accounts), end_date=dt.date(2025, 12, 31)).full_clean()
        assert "ledger.recurring.end_before_start" in codes(caught.value)
