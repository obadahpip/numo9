"""B-01-T02 — the Contact model.

Acceptance: role required validation. Also: the migration creates the table (with row-level
security); defaults (CAD, warn, email statements, English, active); the contact number comes from
the organisation's contact sequence (C-0001…), skips numbers typed by hand and is unique per
organisation whatever the case; roles are stored once each in a fixed order and unknown roles are
refused (also by the database); Business Number with check digit; ISO 4217 currency; credit limit
never negative; archiving keeps the contact; every change is in the audit log; rows are scoped to
the active organisation.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction

from numo9.audit.models import AuditEvent
from numo9.contacts.models import (
    Contact,
    ContactRole,
    ContactStatus,
    CreditMode,
    StatementPreference,
)
from numo9.tenancy.context import TenantContextMissing, org_context
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


def errors_of(excinfo: pytest.ExceptionInfo[ValidationError]) -> dict[str, list[str]]:
    return {
        field: [e.code or "" for e in errors] for field, errors in excinfo.value.error_dict.items()
    }


# ---- migration --------------------------------------------------------------------------------


def test_migration_creates_the_table_with_row_level_security() -> None:
    assert "contacts_contact" in connection.introspection.table_names()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["contacts_contact"],
        )
        assert cursor.fetchone() == (True, True)


def test_models_and_migrations_are_in_step() -> None:
    out = StringIO()
    call_command("makemigrations", "contacts", "orgsettings", "--check", "--dry-run", stdout=out)
    assert "No changes detected" in out.getvalue()


# ---- acceptance: at least one role ------------------------------------------------------------


def test_a_contact_without_a_role_is_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple Supply Ltd.", roles=[])
    assert errors_of(excinfo) == {"roles": ["contacts.roles.required"]}
    assert not Contact.objects.exists()


def test_an_unknown_role_is_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple Supply Ltd.", roles=["customer", "reseller"])
    assert errors_of(excinfo) == {"roles": ["contacts.roles.invalid"]}
    assert "reseller" in str(excinfo.value)


def test_the_database_refuses_an_empty_or_unknown_role(org: Organisation) -> None:
    item = contact(org, "Maple Supply Ltd.")
    for roles in ([], ["reseller"]):
        with pytest.raises(IntegrityError), transaction.atomic():
            Contact.objects.filter(pk=item.pk).update(roles=roles)


def test_the_database_check_lists_every_role() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s",
            ["contacts_contact_roles_valid"],
        )
        (definition,) = cursor.fetchone()
    assert all(f"'{role}'" in definition for role in ContactRole.values)


def test_roles_are_stored_once_in_a_fixed_order(org: Organisation) -> None:
    item = contact(org, "Érable Distribution inc.", roles=["Supplier", "customer", "supplier"])
    item.refresh_from_db()
    assert item.roles == [ContactRole.CUSTOMER, ContactRole.SUPPLIER]
    assert item.is_customer and item.is_supplier
    assert not item.has_role(ContactRole.EMPLOYEE)


@pytest.mark.parametrize("role", ContactRole.values)
def test_every_role_alone_is_enough(org: Organisation, role: str) -> None:
    assert contact(org, f"Contact {role}", roles=[role]).roles == [role]


def test_roles_are_filterable_in_the_database(org: Organisation) -> None:
    contact(org, "Customer only", roles=["customer"])
    contact(org, "Both", roles=["customer", "supplier"])
    contact(org, "Agency", roles=["government_agency"])
    customers = Contact.objects.filter(roles__contains=[ContactRole.CUSTOMER])
    assert sorted(customers.values_list("display_name", flat=True)) == ["Both", "Customer only"]


# ---- defaults -----------------------------------------------------------------------------------


def test_defaults(org: Organisation) -> None:
    item = contact(org, "Maple Supply Ltd.")
    item.refresh_from_db()
    assert item.currency == "CAD"
    assert item.credit_limit is None
    assert item.credit_mode == CreditMode.WARN
    assert item.statement_pref == StatementPreference.EMAIL
    assert item.language == "en-ca"
    assert item.status == ContactStatus.ACTIVE
    assert item.t4a_flag is False and item.portal_enabled is False
    assert item.printed_name == "Maple Supply Ltd."


# ---- number ------------------------------------------------------------------------------------


def test_numbers_come_from_the_contact_sequence(org: Organisation) -> None:
    assert [contact(org, f"Contact {i}").number for i in range(3)] == [
        "C-0001",
        "C-0002",
        "C-0003",
    ]


def test_a_number_typed_by_hand_is_kept_and_skipped_by_the_sequence(org: Organisation) -> None:
    assert contact(org, "Typed", number="C-0002").number == "C-0002"
    assert contact(org, "First").number == "C-0001"
    assert contact(org, "Second").number == "C-0003"


def test_numbers_are_unique_per_organisation_whatever_the_case(org: Organisation) -> None:
    contact(org, "Maple Supply Ltd.", number="ms-1")
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Another", number="MS-1")
    assert errors_of(excinfo) == {"number": ["contacts.number.taken"]}
    with pytest.raises(IntegrityError), transaction.atomic():
        Contact.objects.bulk_create(
            [Contact(organisation=org, number="MS-1", display_name="X", roles=["customer"])]
        )
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        assert contact(other, "Elsewhere", number="MS-1").number == "MS-1"


# ---- fields ------------------------------------------------------------------------------------


def test_display_name_is_required_and_input_is_tidied(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "   ")
    assert "display_name" in errors_of(excinfo)
    item = contact(org, "  Maple   Supply  Ltd. ", legal_name=" Maple Supply Limited ")
    assert (item.display_name, item.legal_name) == ("Maple Supply Ltd.", "Maple Supply Limited")
    assert item.printed_name == "Maple Supply Limited"


def test_a_legal_name_needs_letters(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple", legal_name="1001633222")
    assert errors_of(excinfo) == {"legal_name": ["orgsettings.legal_name.numeric"]}


@pytest.mark.parametrize(
    ("typed", "stored"),
    [("123456782", "123456782"), ("123 456 782", "123456782"), ("123456782 RT 0001", "123456782")],
)
def test_business_number_is_normalised(org: Organisation, typed: str, stored: str) -> None:
    assert contact(org, "Maple", bn=typed).bn == stored


@pytest.mark.parametrize(
    ("typed", "code"),
    [("12345678", "contacts.bn.format"), ("123456789", "contacts.bn.check_digit")],
)
def test_a_wrong_business_number_is_refused(org: Organisation, typed: str, code: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple", bn=typed)
    assert errors_of(excinfo) == {"bn": [code]}


def test_currency_is_an_iso_4217_code(org: Organisation) -> None:
    assert contact(org, "US customer", currency="usd").currency == "USD"
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Nowhere", currency="ABC")
    assert errors_of(excinfo) == {"currency": ["contacts.currency.invalid"]}


def test_credit_limit_and_mode(org: Organisation) -> None:
    item = contact(org, "Maple", credit_limit=Decimal("10000.00"), credit_mode="block")
    item.refresh_from_db()
    assert (item.credit_limit, item.credit_mode) == (Decimal("10000.00"), CreditMode.BLOCK)
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Negative", credit_limit=Decimal("-1"))
    assert "credit_limit" in errors_of(excinfo)
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Odd mode", credit_mode="stop")
    assert "credit_mode" in errors_of(excinfo)


def test_every_problem_is_reported_at_once(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple", roles=[], bn="1", currency="XX")
    assert set(errors_of(excinfo)) == {"roles", "bn", "currency"}


# ---- archive, audit, scoping --------------------------------------------------------------------


def test_archive_keeps_the_contact_and_can_be_undone(org: Organisation) -> None:
    item = contact(org, "Maple")
    item.archive()
    item.refresh_from_db()
    assert item.is_archived and item.archived_at is not None and item.deleted_at is None
    item.unarchive()
    item.refresh_from_db()
    assert item.status == ContactStatus.ACTIVE and item.archived_at is None


def test_every_change_is_in_the_audit_log(org: Organisation) -> None:
    item = contact(org, "Maple", roles=["customer"])
    item.roles = ["customer", "supplier"]
    item.save()
    item.archive()
    events = list(
        AuditEvent.objects.filter(object_type="contacts.Contact", object_id=str(item.public_id))
        .order_by("id")
        .values_list("action", "changes")
    )
    assert [action for action, _ in events] == [
        "contacts.contact.created",
        "contacts.contact.updated",
        "contacts.contact.updated",
    ]
    created: dict[str, Any] = events[0][1]
    assert created["number"] == [None, "C-0001"] and created["roles"] == [None, ["customer"]]
    assert events[1][1] == {"roles": [["customer"], ["customer", "supplier"]]}
    assert events[2][1] == {"status": ["active", "archived"]}


def test_contacts_are_scoped_to_the_active_organisation(org: Organisation) -> None:
    contact(org, "Mine")
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        contact(other, "Theirs")
        assert list(Contact.objects.values_list("display_name", flat=True)) == ["Theirs"]
    assert list(Contact.objects.values_list("display_name", flat=True)) == ["Mine"]
    with org_context(None), pytest.raises(TenantContextMissing):
        Contact.objects.count()
