"""B-01-T12 — merge service: FK re-pointing via a registry, history kept, alias, one transaction.

Acceptance: a failure mid-merge rolls back fully. People, addresses, certificates… move to the
survivor; posted journal lines (append-only) keep the merged contact, which stays an archived alias
resolving to the survivor; chosen fields come from the merged contact, roles are the union; one
audit event lists what moved, and each record's own history is untouched; different currencies,
the same contact and an already-merged contact are refused; every foreign key to Contact is in the
registry (introspected); the API previews counts and merges.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.contacts import merge as merge_module
from numo9.contacts.merge import (
    REGISTRY,
    MergeRefused,
    merge_contacts,
    preview,
    references_to_contact,
    resolve,
)
from numo9.contacts.models import Address, Contact, ContactPerson
from numo9.ledger.models import JournalLine
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def _pair(org: Organisation) -> tuple[Contact, Contact]:
    survivor = contact(org, "Maple Supply Ltd.", roles=["customer"], legal_name="Maple Supply")
    merged = contact(org, "Maple Suply Ltd", roles=["supplier"], legal_name="Maple Supply Limited")
    ContactPerson(organisation=org, contact=survivor, first_name="Dana", email="dana@m.ca").save()
    ContactPerson(organisation=org, contact=merged, first_name="Sam", email="sam@m.ca").save()
    Address(organisation=org, contact=merged, kind="billing", city="Toronto", province="ON").save()
    return survivor, merged


def _post_with(org: Organisation, who: Contact) -> None:
    bank = account(org, "1000", "Chequing", subtype="bank", gifi_id="1001")
    sales = account(org, "4000", "Sales", subtype="revenue", gifi_id="8000")
    post_journal(
        JournalSpec(
            date=dt.date(2026, 3, 31),
            lines=[
                LineSpec(account=bank, debit=D("10.00"), contact=who),
                LineSpec(account=sales, credit=D("10.00"), contact=who),
            ],
        ),
        user=None,
    )


def test_every_foreign_key_to_contact_is_registered() -> None:
    assert references_to_contact() == set(REGISTRY)


def test_merge_moves_records_keeps_posted_lines_on_the_alias(org: Organisation) -> None:
    survivor, merged = _pair(org)
    _post_with(org, merged)
    rows = {r["records"]: r for r in preview(survivor, merged)}
    assert rows["people"]["count"] == 1 and rows["people"]["moves"] is True
    assert rows["journal lines"] == {"records": "journal lines", "count": 2, "moves": False}

    outcome = merge_contacts(survivor, merged, fields={"legal_name": "merged"})
    survivor.refresh_from_db()
    merged.refresh_from_db()
    assert survivor.legal_name == "Maple Supply Limited"
    assert sorted(survivor.roles) == ["customer", "supplier"]
    assert sorted(p.first_name for p in ContactPerson.objects.filter(contact=survivor)) == [
        "Dana",
        "Sam",
    ]
    assert ContactPerson.objects.get(contact=survivor, is_primary=True).first_name == "Dana"
    assert Address.objects.filter(contact=survivor).count() == 1
    assert JournalLine.objects.filter(contact=merged).count() == 2  # append-only: kept
    assert (merged.merged_into_id, merged.status) == (survivor.pk, "archived")
    assert resolve(merged) == survivor
    assert outcome["moved"]["contacts.ContactPerson"] == 1
    event = AuditEvent.objects.filter(action="contacts.contact.merged").get()
    assert event.meta["merged"]["number"] == merged.number
    assert event.meta["kept_on_alias"] == {"ledger.JournalLine": 2}
    # The moved person's own history is untouched (its creation is still there).
    sam = ContactPerson.objects.get(first_name="Sam")
    assert AuditEvent.objects.filter(object_id=str(sam.public_id)).count() >= 2


def test_a_failure_mid_merge_rolls_back_fully(
    org: Organisation, monkeypatch: pytest.MonkeyPatch
) -> None:
    survivor, merged = _pair(org)
    real = merge_module._queryset

    def failing(reference: Any, who: Contact) -> Any:
        if reference.model == "contacts.Address":
            raise RuntimeError("disk full")
        return real(reference, who)

    monkeypatch.setattr(merge_module, "_queryset", failing)
    with pytest.raises(RuntimeError):
        merge_contacts(survivor, merged, fields={"legal_name": "merged"})
    survivor.refresh_from_db()
    merged.refresh_from_db()
    assert survivor.legal_name == "Maple Supply" and survivor.roles == ["customer"]
    assert merged.merged_into_id is None and merged.status == "active"
    assert ContactPerson.objects.filter(contact=merged).count() == 1  # the person didn't move
    assert not AuditEvent.objects.filter(action="contacts.contact.merged").exists()


@pytest.mark.parametrize("case", ["same", "currency", "already"])
def test_refused(org: Organisation, case: str) -> None:
    survivor, merged = _pair(org)
    if case == "same":
        merged = survivor
    elif case == "currency":
        merged.currency = "USD"
        merged.save()
    else:
        third = contact(org, "Third Ltd.")
        merge_contacts(third, merged)
        merged.refresh_from_db()
    with pytest.raises(MergeRefused) as caught:
        merge_contacts(survivor, merged)
    assert caught.value.code.startswith("contacts.merge.")


def test_api_preview_and_merge(org: Organisation) -> None:
    survivor, merged = _pair(org)
    user = User.objects.create_user("owner@maple.ca", password="x" * 12, name="Owner")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    browser = Client()
    browser.force_login(user)
    base = f"/api/v1/o/{org.public_id}/contacts/merge"
    ids = {"survivor": str(survivor.public_id), "merged": str(merged.public_id)}
    counts = browser.get(f"{base}/preview", ids).json()["records"]
    assert {"records": "people", "count": 1, "moves": True} in counts
    done = browser.post(
        base, {**ids, "field_sources": {"display_name": "merged"}}, content_type="application/json"
    )
    assert done.status_code == 200, done.json()
    assert done.json()["survivor"]["display_name"] == "Maple Suply Ltd"
    again = browser.post(base, ids, content_type="application/json")
    assert again.status_code == 400
    assert again.json()["non_field_errors"][0]
