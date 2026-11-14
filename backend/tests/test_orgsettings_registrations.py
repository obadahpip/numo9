"""A-05-T03 — the TaxRegistration model and the Business Number check digit.

Acceptance: an invalid BN is refused (a wrong check digit, [EXTRA] Luhn). Also: every type has its
number format and a canonical stored form (``123456782RT0001``) with a readable display
(``123456782 RT 0001``); program accounts carry their own program letters, a valid BN and a
non-zero reference, and must match the organisation's BN; QST and provincial numbers are checked;
periods of one registration may not overlap and may not end before they start (also in the
database); registration changes — status changes above all — are audited with their author.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction

from numo9.accounts.models import User
from numo9.audit.context import audit_context
from numo9.audit.models import ActorKind, AuditEvent
from numo9.orgsettings.models import RegistrationStatus, RegistrationType, TaxRegistration
from numo9.orgsettings.validators import (
    display_registration_number,
    luhn_valid,
    normalise_registration_number,
    validate_business_number,
)
from numo9.tenancy.context import TenantContextMissing, org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db

BN = "123456782"  # valid check digit
OTHER_BN = "876543216"  # valid check digit
BAD_BN = "123456789"  # wrong check digit


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def register(org: Organisation, kind: str, number: str, **fields: object) -> TaxRegistration:
    item = TaxRegistration(organisation=org, type=kind, number=number, **fields)
    item.save()
    return item


def codes(excinfo: pytest.ExceptionInfo[ValidationError], field: str = "number") -> list[str]:
    return [str(e.code) for e in excinfo.value.error_dict[field]]


# ---- migration ----------------------------------------------------------------------------------


def test_migration_creates_the_table() -> None:
    assert "orgsettings_taxregistration" in connection.introspection.table_names()
    out = StringIO()
    call_command("makemigrations", "orgsettings", "--check", "--dry-run", stdout=out)
    assert "No changes detected" in out.getvalue()


# ---- acceptance: BN check digit -----------------------------------------------------------------


def test_invalid_bn_is_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        register(org, RegistrationType.BN, BAD_BN)
    assert codes(excinfo) == ["orgsettings.registration.bn_check_digit"]
    assert not TaxRegistration.objects.exists()


def test_valid_bn_is_stored(org: Organisation) -> None:
    item = register(org, RegistrationType.BN, "123 456 782")
    assert item.number == BN and item.display_number == BN and item.business_number == BN


@pytest.mark.parametrize("bn", [BN, OTHER_BN, "100163328", "046454286"])
def test_luhn_accepts_valid_numbers(bn: str) -> None:
    assert luhn_valid(bn)
    validate_business_number(bn)


@pytest.mark.parametrize(
    ("bn", "code"),
    [
        (BAD_BN, "orgsettings.registration.bn_check_digit"),
        ("123456783", "orgsettings.registration.bn_check_digit"),
        ("000000000", "orgsettings.registration.bn_check_digit"),
        ("12345678", "orgsettings.registration.bn_format"),
        ("1234567820", "orgsettings.registration.bn_format"),
        ("12345678A", "orgsettings.registration.bn_format"),
    ],
)
def test_invalid_business_numbers(bn: str, code: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_business_number(bn)
    assert excinfo.value.code == code


def test_every_single_digit_typo_is_caught() -> None:
    for position in range(9):
        for digit in "0123456789":
            typo = BN[:position] + digit + BN[position + 1 :]
            if typo != BN:
                assert not luhn_valid(typo), typo


# ---- program accounts ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "given", "stored", "shown"),
    [
        ("rt", "123456782 RT 0001", "123456782RT0001", "123456782 RT 0001"),
        ("rp", "123456782rp0001", "123456782RP0001", "123456782 RP 0001"),
        ("rc", "123456782-RC-0002", "123456782RC0002", "123456782 RC 0002"),
        ("qst", "1234567890 TQ 0001", "1234567890TQ0001", "1234567890 TQ 0001"),
        ("pst_bc", "pst 1234 5678", "PST-1234-5678", "PST-1234-5678"),
        ("pst_bc", "12345678", "PST-1234-5678", "PST-1234-5678"),
        ("pst_sk", "1234567", "1234567", "1234567"),
        ("rst_mb", "123456-7", "1234567", "1234567"),
    ],
)
def test_numbers_are_stored_canonically_and_shown_readably(
    kind: str, given: str, stored: str, shown: str
) -> None:
    assert normalise_registration_number(kind, given) == stored
    assert display_registration_number(kind, stored) == shown


@pytest.mark.parametrize(
    ("kind", "value", "code"),
    [
        ("rt", "123456782 RP 0001", "orgsettings.registration.program_mismatch"),
        ("rt", "123456789 RT 0001", "orgsettings.registration.bn_check_digit"),
        ("rt", "123456782 RT 0000", "orgsettings.registration.reference_zero"),
        ("rt", "123456782 RT 001", "orgsettings.registration.program_format"),
        ("rt", "123456782", "orgsettings.registration.program_format"),
        ("qst", "1234567890 RT 0001", "orgsettings.registration.qst_format"),
        ("qst", "1234567890 TQ 0000", "orgsettings.registration.qst_format"),
        ("pst_bc", "PST-1234-567", "orgsettings.registration.pst_bc_format"),
        ("pst_sk", "12345", "orgsettings.registration.digits_format"),
        ("rst_mb", "ABC1234", "orgsettings.registration.digits_format"),
        ("bn", "  ", "orgsettings.registration.required"),
    ],
)
def test_invalid_registration_numbers(kind: str, value: str, code: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        normalise_registration_number(kind, value)
    assert excinfo.value.code == code


def test_program_account_must_carry_the_organisations_bn(org: Organisation) -> None:
    register(org, RegistrationType.BN, BN)
    register(org, RegistrationType.RT, f"{BN}RT0001")
    with pytest.raises(ValidationError) as excinfo:
        register(org, RegistrationType.RP, f"{OTHER_BN}RP0001")
    assert codes(excinfo) == ["orgsettings.registration.bn_mismatch"]


def test_bn_must_match_the_program_accounts_already_there(org: Organisation) -> None:
    register(org, RegistrationType.RT, f"{BN}RT0001")
    with pytest.raises(ValidationError) as excinfo:
        register(org, RegistrationType.BN, OTHER_BN)
    assert codes(excinfo) == ["orgsettings.registration.bn_mismatch"]
    register(org, RegistrationType.BN, BN)


def test_several_gst_hst_accounts_are_allowed(org: Organisation) -> None:
    register(org, RegistrationType.BN, BN)
    register(org, RegistrationType.RT, f"{BN}RT0001")
    register(org, RegistrationType.RT, f"{BN}RT0002")  # a branch that files separately
    assert TaxRegistration.objects.filter(type="rt").count() == 2


# ---- periods ------------------------------------------------------------------------------------


def test_the_same_registration_may_not_overlap(org: Organisation) -> None:
    register(org, RegistrationType.RT, f"{BN}RT0001", effective_from=dt.date(2020, 1, 1))
    with pytest.raises(ValidationError) as excinfo:
        register(org, RegistrationType.RT, f"{BN}RT0001", effective_from=dt.date(2024, 1, 1))
    assert codes(excinfo, "effective_from") == ["orgsettings.registration.overlap"]


def test_only_one_bn_at_a_time(org: Organisation) -> None:
    register(org, RegistrationType.BN, BN, effective_to=dt.date(2023, 12, 31))
    register(org, RegistrationType.BN, OTHER_BN, effective_from=dt.date(2024, 1, 1))
    with pytest.raises(ValidationError) as excinfo:
        register(org, RegistrationType.BN, "100163328", effective_from=dt.date(2025, 1, 1))
    assert codes(excinfo, "effective_from") == ["orgsettings.registration.overlap"]


def test_a_closed_period_can_be_registered_again(org: Organisation) -> None:
    register(
        org,
        RegistrationType.QST,
        "1234567890TQ0001",
        effective_from=dt.date(2019, 1, 1),
        effective_to=dt.date(2021, 6, 30),
        status=RegistrationStatus.CLOSED,
    )
    register(org, RegistrationType.QST, "1234567890TQ0001", effective_from=dt.date(2021, 7, 1))
    assert TaxRegistration.objects.count() == 2


def test_a_deleted_registration_does_not_block(org: Organisation) -> None:
    first = register(org, RegistrationType.BN, BN)
    first.soft_delete()
    register(org, RegistrationType.BN, OTHER_BN)


def test_end_before_start_is_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        register(
            org,
            RegistrationType.BN,
            BN,
            effective_from=dt.date(2024, 1, 1),
            effective_to=dt.date(2023, 1, 1),
        )
    assert codes(excinfo, "effective_to") == ["orgsettings.registration.period_invalid"]


def test_database_refuses_end_before_start_and_unknown_values(org: Organisation) -> None:
    item = register(org, RegistrationType.BN, BN, effective_from=dt.date(2024, 1, 1))
    for update in (
        {"effective_to": dt.date(2023, 1, 1)},
        {"type": "vat"},
        {"status": "maybe"},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            TaxRegistration.objects.filter(pk=item.pk).update(**update)


def test_unknown_type_is_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        register(org, "vat", "123")
    assert "type" in excinfo.value.error_dict


# ---- scoping and audit --------------------------------------------------------------------------


def test_registrations_are_scoped_to_the_active_organisation(org: Organisation) -> None:
    register(org, RegistrationType.BN, BN)
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        assert TaxRegistration.objects.count() == 0
        register(other, RegistrationType.BN, BN)  # the same BN elsewhere is another org's business
    with org_context(None), pytest.raises(TenantContextMissing):
        TaxRegistration.objects.count()


@pytest.mark.gap("gap-44")
def test_status_change_is_audited_with_its_author(org: Organisation) -> None:
    user = User.objects.create_user("avery@maple.ca", password="x" * 12, name="Avery Owner")
    item = register(org, RegistrationType.RT, f"{BN}RT0001")
    with audit_context(kind=ActorKind.USER, user=user, label="Avery Owner (avery@maple.ca)"):
        item.status = RegistrationStatus.CLOSED
        item.effective_to = dt.date(2026, 6, 30)
        item.save()
    event = AuditEvent.objects.filter(action="orgsettings.taxregistration.updated").get()
    assert event.actor_user == user and event.actor_label == "Avery Owner (avery@maple.ca)"
    assert event.changes == {
        "effective_to": [None, "2026-06-30"],
        "status": ["active", "closed"],
    }
    assert event.object_label == "GST/HST program account (RT) 123456782 RT 0001"
