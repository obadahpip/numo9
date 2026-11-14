"""B-01-T03 — people at a contact (ContactPerson).

Acceptance: more than 5 people allowed. Also: the first person is primary; marking another primary
unmarks the previous one; removing or unmarking the primary promotes the earliest remaining person;
the database refuses two primaries; a person needs a name or an email; email in lower case,
telephone as E.164; include-in-emails defaults on; the person belongs to the contact's
organisation; changes are audited; the table has row-level security.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from numo9.audit.models import AuditEvent
from numo9.contacts.models import Contact, ContactPerson
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def maple(org: Organisation) -> Contact:
    return contact(org, "Maple Supply Ltd.")


def person(item: Contact, first: str = "", **fields: object) -> ContactPerson:
    p = ContactPerson(contact=item, first_name=first, **fields)
    p.save()
    return p


def primaries(item: Contact) -> list[str]:
    return list(
        item.people.filter(is_primary=True, deleted_at__isnull=True).values_list(
            "first_name", flat=True
        )
    )


# ---- acceptance -------------------------------------------------------------------------------


def test_more_than_five_people_are_allowed(maple: Contact) -> None:
    for i in range(12):
        person(maple, f"Person {i}", email=f"p{i}@maplesupply.ca")
    assert maple.people.count() == 12
    assert primaries(maple) == ["Person 0"]


# ---- primary person -----------------------------------------------------------------------------


def test_the_first_person_is_primary_and_others_are_not(maple: Contact) -> None:
    anne = person(maple, "Anne")
    raj = person(maple, "Raj")
    assert anne.is_primary and not raj.is_primary
    assert [p.first_name for p in maple.people.all()] == ["Anne", "Raj"]  # primary first


def test_marking_another_person_primary_unmarks_the_previous_one(maple: Contact) -> None:
    person(maple, "Anne")
    raj = person(maple, "Raj")
    raj.make_primary()
    assert primaries(maple) == ["Raj"]
    person(maple, "Lea", is_primary=True)
    assert primaries(maple) == ["Lea"]


def test_removing_the_primary_promotes_the_earliest_remaining_person(maple: Contact) -> None:
    anne = person(maple, "Anne")
    person(maple, "Raj")
    person(maple, "Lea")
    anne.soft_delete()
    assert primaries(maple) == ["Raj"]
    anne.refresh_from_db()
    assert anne.is_primary is False and anne.deleted_at is not None


def test_unmarking_the_primary_keeps_one_primary(maple: Contact) -> None:
    anne = person(maple, "Anne")
    person(maple, "Raj")
    anne.is_primary = False
    anne.save()
    assert primaries(maple) == ["Raj"]
    only = contact(maple.organisation, "Solo")
    alone = person(only, "Alone", is_primary=False)
    assert alone.is_primary  # the only person is always primary


def test_the_database_refuses_two_primaries(maple: Contact) -> None:
    person(maple, "Anne")
    raj = person(maple, "Raj")
    with pytest.raises(IntegrityError), transaction.atomic():
        ContactPerson.objects.filter(pk=raj.pk).update(is_primary=True)


def test_each_contact_has_its_own_primary(org: Organisation, maple: Contact) -> None:
    other = contact(org, "Érable Distribution inc.")
    person(maple, "Anne")
    person(other, "Marie")
    assert primaries(maple) == ["Anne"] and primaries(other) == ["Marie"]


# ---- fields -------------------------------------------------------------------------------------


def test_a_person_needs_a_name_or_an_email(maple: Contact) -> None:
    with pytest.raises(ValidationError) as excinfo:
        person(maple, "  ")
    assert excinfo.value.error_dict["first_name"][0].code == "contacts.person.name_or_email"
    assert person(maple, email="AP@MapleSupply.ca ").email == "ap@maplesupply.ca"
    assert person(maple, last_name="Tremblay").full_name == "Tremblay"


def test_email_and_telephone_are_checked(maple: Contact) -> None:
    anne = person(maple, "Anne", last_name="Tremblay", phone="416 555 0123")
    assert anne.phone == "+14165550123"
    assert anne.full_name == "Anne Tremblay" and str(anne) == "Anne Tremblay"
    with pytest.raises(ValidationError) as excinfo:
        person(maple, "Bad", phone="12", email="not-an-email")
    assert set(excinfo.value.error_dict) == {"phone", "email"}


def test_include_in_emails_defaults_on(maple: Contact) -> None:
    assert person(maple, "Anne").include_in_emails is True
    assert person(maple, "Raj", include_in_emails=False).include_in_emails is False


def test_the_person_takes_the_contact_organisation(org: Organisation, maple: Contact) -> None:
    anne = person(maple, "Anne")
    assert anne.organisation_id == org.pk
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    stray = ContactPerson(contact=maple, organisation=other, first_name="Stray")
    with pytest.raises(ValidationError) as excinfo:
        stray.save()
    assert excinfo.value.error_dict["contact"][0].code == "contacts.person.contact"


# ---- audit, RLS --------------------------------------------------------------------------------


def test_people_changes_are_audited(maple: Contact) -> None:
    anne = person(maple, "Anne")
    anne.job_title = "Controller"
    anne.save()
    actions = list(
        AuditEvent.objects.filter(
            object_type="contacts.ContactPerson", object_id=str(anne.public_id)
        )
        .order_by("id")
        .values_list("action", flat=True)
    )
    assert actions == ["contacts.contactperson.created", "contacts.contactperson.updated"]


def test_the_people_table_has_row_level_security() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["contacts_contactperson"],
        )
        assert cursor.fetchone() == (True, True)
