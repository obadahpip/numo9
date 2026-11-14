"""A-05-T02 — validators of the organisation settings.

Acceptance: the legal name "1001633222" is refused (gap-55). Also: a legal name needs letters
(accented letters count); Canadian postal codes are validated in the Canada Post format and stored
normalised (``A1A 1A1``); [EXTRA] the first letter must belong to the province; the province is a
Canadian province or territory; addresses outside Canada are not held to Canadian rules; telephone
numbers are parsed as Canadian by default, refused when invalid and stored as E.164.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError

from numo9.orgsettings.models import OrganisationSettings
from numo9.orgsettings.validators import (
    POSTAL_PREFIX_PROVINCES,
    Province,
    normalise_phone,
    normalise_postal_code,
    validate_legal_name,
    validate_postal_code,
    validate_postal_code_province,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def build(org: Organisation, **fields: object) -> OrganisationSettings:
    return OrganisationSettings(organisation=org, display_name="Maple Bakery", **fields)


def error_codes(excinfo: pytest.ExceptionInfo[ValidationError], field: str) -> list[str]:
    return [str(e.code) for e in excinfo.value.error_dict[field]]


# ---- acceptance: legal name (gap-55) ------------------------------------------------------------


@pytest.mark.gap("gap-55")
def test_numeric_legal_name_is_refused(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        build(org, legal_name="1001633222").save()
    assert error_codes(excinfo, "legal_name") == ["orgsettings.legal_name.numeric"]
    assert "1001633222" in excinfo.value.error_dict["legal_name"][0].messages[0]
    assert not OrganisationSettings.objects.exists()


@pytest.mark.gap("gap-55")
@pytest.mark.parametrize("value", ["1001633222", "123 456", "123-456-789", "#1", "  42  ", "(1)"])
def test_names_without_letters_are_refused(value: str) -> None:
    with pytest.raises(ValidationError):
        validate_legal_name(value.strip())


@pytest.mark.parametrize(
    "value",
    ["Maple Bakery Inc.", "1001633222 Ontario Inc.", "Boulangerie Érable ltée", "3M Canada", ""],
)
def test_names_with_letters_are_accepted(org: Organisation, value: str) -> None:
    validate_legal_name(value)
    item = build(org, legal_name=value)
    item.save()
    assert item.legal_name == value


# ---- postal code --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("m5x1a9", "M5X 1A9"),
        (" M5X  1A9 ", "M5X 1A9"),
        ("h2y-1c6", "H2Y 1C6"),
        ("K1A 0B1", "K1A 0B1"),
    ],
)
def test_postal_code_is_normalised(given: str, stored: str) -> None:
    assert normalise_postal_code(given) == stored


@pytest.mark.parametrize(
    "value", ["M5X 1A9", "K1A 0B1", "H2Y 1C6", "V6B 4Y8", "X0A 0H0", "T2P 2M5"]
)
def test_valid_postal_codes(value: str) -> None:
    validate_postal_code(value)


@pytest.mark.parametrize(
    "value",
    [
        "12345",  # a ZIP code
        "M5X 1A",  # too short
        "D5X 1A9",  # D never used
        "W5X 1A9",  # W never starts a code
        "Z5X 1A9",  # Z never starts a code
        "M5O 1A9",  # O never used
        "M5X 1U9",  # U never used
        "5MX 1A9",  # digit first
    ],
)
def test_invalid_postal_codes(value: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_postal_code(normalise_postal_code(value))
    assert excinfo.value.code == "orgsettings.postal_code.invalid"


def test_every_province_has_postal_letters() -> None:
    covered = set().union(*POSTAL_PREFIX_PROVINCES.values())
    assert covered == set(Province.values)


@pytest.mark.parametrize(
    ("postal_code", "province"),
    [
        ("M5X 1A9", "ON"),
        ("K1A 0B1", "ON"),
        ("H2Y 1C6", "QC"),
        ("G1R 4P5", "QC"),
        ("V6B 4Y8", "BC"),
        ("T2P 2M5", "AB"),
        ("S4P 3V7", "SK"),
        ("R3C 4T3", "MB"),
        ("E1C 4M3", "NB"),
        ("B3J 3K5", "NS"),
        ("C1A 7N8", "PE"),
        ("A1C 5M2", "NL"),
        ("Y1A 2C6", "YT"),
        ("X1A 2L9", "NT"),
        ("X0A 0H0", "NU"),
    ],
)
def test_postal_code_matches_its_province(postal_code: str, province: str) -> None:
    validate_postal_code_province(postal_code, province)


def test_postal_code_in_another_province_is_refused() -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_postal_code_province("M5X 1A9", "QC")
    assert excinfo.value.code == "orgsettings.postal_code.province_mismatch"
    message = excinfo.value.messages[0]
    assert "Ontario" in message and "Quebec" in message


def test_settings_store_a_normalised_canadian_address(org: Organisation) -> None:
    item = build(
        org,
        mailing_line1=" 100 King St W ",
        mailing_city="Toronto",
        mailing_province="on",
        mailing_postal_code="m5x1a9",
    )
    item.save()
    item.refresh_from_db()
    assert (item.mailing_line1, item.mailing_province, item.mailing_postal_code) == (
        "100 King St W",
        "ON",
        "M5X 1A9",
    )


def test_settings_refuse_a_postal_code_outside_the_province(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        build(org, mailing_province="QC", mailing_postal_code="M5X 1A9").save()
    assert error_codes(excinfo, "mailing_postal_code") == [
        "orgsettings.postal_code.province_mismatch"
    ]


def test_settings_refuse_a_zip_code_and_a_state(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        build(org, mailing_province="NY", mailing_postal_code="10001").save()
    assert error_codes(excinfo, "mailing_province") == ["orgsettings.province.invalid"]
    assert error_codes(excinfo, "mailing_postal_code") == ["orgsettings.postal_code.invalid"]


def test_physical_address_is_checked_only_when_separate(org: Organisation) -> None:
    build(org, physical_province="QC", physical_postal_code="M5X 1A9").save()  # ignored: same
    with pytest.raises(ValidationError) as excinfo:
        build(
            org,
            physical_same_as_mailing=False,
            physical_province="QC",
            physical_postal_code="M5X 1A9",
        ).clean()
    assert "physical_postal_code" in excinfo.value.error_dict


def test_address_outside_canada_is_not_held_to_canadian_rules(org: Organisation) -> None:
    item = build(
        org,
        mailing_country="us",
        mailing_province="New York",
        mailing_postal_code="10001",
    )
    item.save()
    assert (item.mailing_country, item.mailing_postal_code) == ("US", "10001")


def test_country_must_be_a_two_letter_code(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        build(org, mailing_country="C1").save()
    assert error_codes(excinfo, "mailing_country") == ["orgsettings.country.invalid"]


def test_province_without_postal_code_and_postal_code_without_province(org: Organisation) -> None:
    build(org, mailing_province="ON").save()
    org2 = Organisation.objects.create(name="Second Ltd.")
    with org_context(org2):
        build(org2, mailing_postal_code="M5X 1A9").save()


# ---- telephone ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("416 555 0123", "+14165550123"),
        ("(416) 979-1234", "+14169791234"),
        ("1-613-555-0199", "+16135550199"),
        ("+1 604 555 0142", "+16045550142"),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_phone_numbers_are_stored_as_e164(given: str, stored: str) -> None:
    assert normalise_phone(given) == stored


@pytest.mark.parametrize("value", ["123", "555-0123", "phone", "+1 999 555 0123", "416 555 01234"])
def test_invalid_phone_numbers_are_refused(value: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        normalise_phone(value)
    assert excinfo.value.code == "orgsettings.phone.invalid"


def test_settings_store_the_phone_as_e164(org: Organisation) -> None:
    item = build(org, phone="416 555 0123")
    item.save()
    item.refresh_from_db()
    assert item.phone == "+14165550123"


def test_settings_refuse_an_invalid_phone(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        build(org, phone="123").save()
    assert error_codes(excinfo, "phone") == ["orgsettings.phone.invalid"]


def test_all_errors_are_reported_together(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        build(org, legal_name="1001633222", phone="123", mailing_postal_code="12345").save()
    assert {"legal_name", "phone", "mailing_postal_code"} <= set(excinfo.value.error_dict)
