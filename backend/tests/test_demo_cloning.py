"""U-07-T05 — template-org cloning: a demo from the prebuilt hidden template.

Acceptance: creation < 10 s p95 (k6 against the entry endpoint in staging; measured here over
several creations); the clone is the seed exactly (same pristine hash as the template, trial
balance zero, posted journal numbered 1, contacts numbered, FKs inside the copy); the template is
built once per seed version and is hidden (demo, no members); a seed table pointing at a
non-seed organisation table is refused.
"""

from __future__ import annotations

import statistics
import time
from decimal import Decimal

import pytest

from numo9.contacts.models import Address, Contact
from numo9.demo import cloning, seeders
from numo9.demo.cloning import CloneError, clone, create_demo, pristine_hash, template_for
from numo9.demo.models import DemoTemplate
from numo9.demo.seeders import Seeder
from numo9.ledger.models import Account, Book, JournalEntry, JournalLine
from numo9.ledger.trial_balance import trial_balance
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember, OrganisationStatus

pytestmark = pytest.mark.django_db


def test_clone_is_the_seed_exactly() -> None:
    template = template_for()
    demo = create_demo()
    assert demo.is_demo and demo.status == OrganisationStatus.DEMO
    assert demo.demo_seed_version == 1 and demo.last_active_at is not None
    assert pristine_hash(demo) == template.pristine_hash == pristine_hash(template.organisation)
    with org_context(demo):
        assert trial_balance(Book.ACCOUNTING).total_balance == Decimal("0.00")
        assert trial_balance(Book.TAX).balanced
        entry = JournalEntry.objects.get()
        assert (entry.number, entry.status) == (1, "posted")
        assert {line.account.organisation_id for line in JournalLine.objects.all()} == {demo.pk}
        assert {a.contact.organisation_id for a in Address.objects.all()} == {demo.pk}
        assert Contact.objects.count() == 25
        children = Account.objects.exclude(parent=None)
        assert all(a.parent is not None and a.parent.organisation_id == demo.pk for a in children)
    # Nothing of the template moved, and the template is hidden.
    with org_context(template.organisation):
        assert Contact.objects.count() == 25
    assert not OrganisationMember.objects.filter(organisation=template.organisation).exists()


def test_template_built_once_per_version() -> None:
    first = template_for()
    create_demo()
    assert template_for() == first
    assert DemoTemplate.objects.count() == 1


def test_creation_under_ten_seconds_p95() -> None:
    template_for()
    timings = []
    for _ in range(5):
        started = time.perf_counter()
        create_demo()
        timings.append(time.perf_counter() - started)
    p95 = statistics.quantiles(timings, n=20)[-1] if len(timings) > 1 else timings[0]
    print(f"demo creation: median {statistics.median(timings):.2f} s, p95 {p95:.2f} s")
    assert p95 < 10.0


def test_a_seed_table_pointing_outside_the_seed_is_refused() -> None:
    template = template_for()
    demo = create_demo()
    # Pretend the contacts seeder forgot to list PaymentTerm while a contact points at one.
    contacts = seeders._registry["contacts"]
    with org_context(template.organisation):
        from numo9.contacts.models import PaymentTerm

        term = PaymentTerm._base_manager.filter(organisation=template.organisation).first()
        assert term is not None
        Contact._base_manager.filter(organisation=template.organisation).update(
            sales_payment_term=term
        )
    seeders._registry["contacts"] = Seeder(
        contacts.key,
        contacts.run,
        after=contacts.after,
        models=tuple(m for m in contacts.models if m != "contacts.PaymentTerm"),
    )
    try:
        with pytest.raises(CloneError, match="sales_payment_term points at contacts.PaymentTerm"):
            clone(template.organisation, demo)
    finally:
        seeders._registry["contacts"] = contacts


def test_only_a_demo_is_wiped() -> None:
    from numo9.tenancy.models import Organisation

    real = Organisation.objects.create(name="Real Ltd.")
    with pytest.raises(CloneError):
        cloning.wipe(real)
