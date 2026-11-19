"""S-06-T08 — ``make_fixture_practice --orgs N --lines M`` generator.

Acceptance: generates the practice for V-01 perf (2,000 organisations on staging; a small run
here): every organisation assigned to the practice, M posted journal lines each numbered 1..n
gap-free and balanced, contacts numbered, deterministic names; a second run adds to the same
practice; refused without --scratch and outside DEBUG unless NUMO9_ALLOW_FIXTURES=1.
"""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db.models import Sum

from numo9.contacts.models import Contact
from numo9.ledger.models import Book, JournalEntry, JournalLine
from numo9.ledger.trial_balance import trial_balance
from numo9.scale import fixtures
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, PracticeAssignment, PracticeMember

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NUMO9_ALLOW_FIXTURES", "1")


def test_generates_orgs_lines_and_contacts() -> None:
    out = StringIO()
    call_command(
        "make_fixture_practice",
        "--orgs",
        "3",
        "--lines",
        "40",
        "--contacts",
        "2",
        "--scratch",
        stdout=out,
    )
    assert "3 organisations, 120 journal lines, 6 contacts" in out.getvalue()
    assignments = PracticeAssignment.objects.filter(practice__name="Fixture Practice LLP")
    assert assignments.count() == 3
    assert PracticeMember.objects.filter(practice__name="Fixture Practice LLP").count() == 1
    for assignment in assignments:
        organisation = assignment.organisation
        assert organisation.name.startswith("Fixture ")
        with org_context(organisation):
            numbers = sorted(JournalEntry.objects.values_list("number", flat=True))
            assert numbers == list(range(1, 21))
            totals = JournalLine.objects.aggregate(d=Sum("debit"), c=Sum("credit"))
            assert totals["d"] == totals["c"] > Decimal("0")
            assert trial_balance(Book.ACCOUNTING).balanced
            assert trial_balance(Book.TAX).balanced
            assert Contact.objects.count() == 2
            assert all(c.number for c in Contact.objects.all())


def test_second_run_extends_the_practice_and_names_are_deterministic() -> None:
    first = fixtures.make_practice_fixture(orgs=2, lines=4, contacts=0, seed=7)
    second = fixtures.make_practice_fixture(orgs=1, lines=4, contacts=0, seed=7)
    assert first.practice == second.practice
    assert PracticeAssignment.objects.filter(practice=first.practice).count() == 3
    names = list(
        Organisation.objects.filter(pk__in=first.organisations)
        .order_by("pk")
        .values_list("name", flat=True)
    )
    import random

    rng = random.Random(7)  # noqa: S311
    assert names == [fixtures.org_name(rng, 1), fixtures.org_name(rng, 2)]


def test_refused_without_scratch_or_outside_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(CommandError, match="--scratch"):
        call_command("make_fixture_practice", "--orgs", "1")
    monkeypatch.delenv("NUMO9_ALLOW_FIXTURES")
    with pytest.raises(CommandError, match="NUMO9_ALLOW_FIXTURES"):
        call_command("make_fixture_practice", "--orgs", "1", "--scratch")
    assert not Organisation.objects.filter(name__startswith="Fixture ").exists()
