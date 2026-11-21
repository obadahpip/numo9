"""A-09-T03 — providers for contacts, accounts, journals (narration + line descriptions),
organisations, users, documents.

Acceptance: journal narration found — and a line's description; each record type is indexed on
save with its permission and feature keys and its link; a contact's person re-indexes it; a
merged contact leaves the index; a draft journal edited keeps its document current.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.accounts.models import User
from numo9.ledger.services import post_journal, save_draft
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.search.models import SearchDocument
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


def doc(org: Organisation, object_type: str) -> list[SearchDocument]:
    with org_context(org):
        return list(SearchDocument.objects.filter(object_type=object_type))


def find(org: Organisation, word: str) -> list[str]:
    from django.contrib.postgres.search import SearchQuery

    with org_context(org):
        return list(
            SearchDocument.objects.filter(
                search_vector=SearchQuery(f"{word}:*", search_type="raw", config="simple")
            ).values_list("object_type", flat=True)
        )


def test_journal_narration_and_line_descriptions_are_found(org: Organisation) -> None:
    with org_context(org):
        bank = account(org, "1000", "Chequing", subtype="bank")
        rent = account(org, "5400", "Rent")
        post_journal(
            JournalSpec(
                date=dt.date(2026, 11, 2),
                narration="November rent for the Queen Street bakery",
                lines=(
                    LineSpec(rent, debit=Decimal("1130.00"), description="Landlord: Pinecrest"),
                    LineSpec(bank, credit=Decimal("1130.00")),
                ),
            ),
            organisation=org,
            user=None,
        )
    assert "ledger.journalentry" in find(org, "queen")
    assert "ledger.journalentry" in find(org, "pinecrest")
    (journal,) = doc(org, "ledger.journalentry")
    assert (journal.amount, journal.date) == (Decimal("1130.00"), dt.date(2026, 11, 2))
    assert journal.permission_key == "accounting.journals.view"
    assert journal.url.startswith(f"/o/{org.public_id}/accounting/journals/")
    accounts = {d.code: d for d in doc(org, "ledger.account")}
    assert accounts["5400"].title == "Rent" and accounts["5400"].feature_key.startswith(
        "accounting."
    )


def test_draft_edits_keep_the_document_current(org: Organisation) -> None:
    with org_context(org):
        bank = account(org, "1000", "Chequing", subtype="bank")
        rent = account(org, "5400", "Rent")
        spec = JournalSpec(
            date=dt.date(2026, 11, 2),
            narration="Draft one",
            lines=(LineSpec(rent, debit=Decimal("5")), LineSpec(bank, credit=Decimal("5"))),
        )
        entry = save_draft(spec, organisation=org, user=None)
        save_draft(
            JournalSpec(
                date=spec.date,
                narration="Draft two",
                lines=(
                    LineSpec(rent, debit=Decimal("7"), description="Snow removal"),
                    LineSpec(bank, credit=Decimal("7")),
                ),
            ),
            entry=entry,
            organisation=org,
            user=None,
        )
    (journal,) = doc(org, "ledger.journalentry")
    assert "Snow removal" in journal.body and journal.amount == Decimal("7")


def test_contacts_people_and_merges(org: Organisation) -> None:
    from numo9.contacts.models import ContactPerson

    with org_context(org):
        cedar = contact(org, "Cédar Roofing Co.")
        ContactPerson(
            organisation=org, contact=cedar, first_name="Léa", email="lea@cedar.ca"
        ).save()
    (row,) = doc(org, "contacts.contact")
    assert row.title == "Cédar Roofing Co." and "lea@cedar.ca" in row.body
    assert "contacts.contact" in find(org, "cedar")  # accents ignored
    with org_context(org):
        other = contact(org, "Cedar Roofing (dup)")
        other.merged_into = cedar
        other.save()
    assert [d.title for d in doc(org, "contacts.contact")] == ["Cédar Roofing Co."]


def test_organisation_users_and_documents(org: Organisation) -> None:
    person = User.objects.create_user("dana@maple.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=person, role="owner")
    assert [d.title for d in doc(org, "tenancy.organisation")] == ["Maple Bakery Inc."]
    (member,) = doc(org, "accounts.user")
    assert (member.title, member.subtitle, member.object_id) == (
        "Dana Lee",
        "dana@maple.ca",
        str(person.public_id),
    )
    person.name = "Dana Lee-Roy"
    person.save()
    assert doc(org, "accounts.user")[0].title == "Dana Lee-Roy"
    OrganisationMember.objects.filter(user=person).delete()  # queryset delete: no signal
    from numo9.files.models import Document

    with org_context(org):
        Document(organisation=org, file_key="k1", name="T4 summary 2025.pdf", size=10).save()
    assert [d.title for d in doc(org, "files.document")] == ["T4 summary 2025.pdf"]
