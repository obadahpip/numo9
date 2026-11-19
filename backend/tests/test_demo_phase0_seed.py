"""U-07-T04 — Phase 0 seeders: settings, chart of accounts, contacts, opening balances.

Acceptance (data validation): the trial balance of a seeded organisation is zero in both books;
the seed is complete (25 contacts over six provinces, each with an address and a person; the ON
chart; the opening journal posted with its AR and AP contacts); settings carry the company.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.contacts.models import Address, Contact, ContactPerson
from numo9.demo.seeders import load_seed, order, run_seed
from numo9.ledger.models import Account, Book, JournalEntry, JournalLine
from numo9.ledger.trial_balance import trial_balance
from numo9.orgsettings.service import get_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = [pytest.mark.django_db, pytest.mark.data_validation]


@pytest.fixture
def seeded() -> Organisation:
    org = Organisation.objects.create(name="Demo")
    run_seed(org)
    return org


def test_phase0_seeders_in_order() -> None:
    keys = [s.key for s in order()]
    assert keys.index("settings") < keys.index("chart") < keys.index("contacts")
    assert keys.index("contacts") < keys.index("opening_balances")


def test_trial_balance_of_the_seeded_org_is_zero(seeded: Organisation) -> None:
    with org_context(seeded):
        for book in (Book.ACCOUNTING, Book.TAX):
            tb = trial_balance(book)
            assert tb.balanced
            assert tb.total_balance == Decimal("0.00")
        entry = JournalEntry.objects.get()
        assert (entry.number, entry.status) == (1, "posted")
        totals = [(line.debit, line.credit) for line in JournalLine.objects.all()]
        assert sum(d for d, _c in totals) == sum(c for _d, c in totals) == Decimal("153390.00")
        ar = JournalLine.objects.filter(account__code="1100")
        assert ar.count() == 3 and all(line.contact_id for line in ar)


def test_seed_is_complete(seeded: Organisation) -> None:
    seed = load_seed()
    with org_context(seeded):
        settings = get_settings(seeded)
        assert settings.display_name == "Maple & Pine Supply Co."
        assert (settings.fye_month, settings.fye_day) == (12, 31)
        assert Contact.objects.count() == 25
        assert Address.objects.count() == 25
        assert ContactPerson.objects.count() == 25
        provinces = set(Address.objects.values_list("province", flat=True))
        assert provinces == {"ON", "QC", "BC", "AB", "NS", "MB"}
        assert all(c.number for c in Contact.objects.all())
        assert Account.objects.filter(code="1100").exists()
        assert Account.objects.count() > 50
    assert seed["version"] == 1
