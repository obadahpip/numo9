"""G-06-T03 — BN / program account / QST number validators: canonical numbers; an invalid
number is refused with an example of the right format in the message (an invalid RT names
"123456782 RT 0001"); the check endpoint writes nothing.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from numo9.tax.numbers import EXAMPLES, check_number, validate_number
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people


@pytest.mark.parametrize(
    ("kind", "typed", "number", "display"),
    [
        ("bn", "123 456 782", "123456782", "123456782"),
        ("rt", "123456782rt0001", "123456782RT0001", "123456782 RT 0001"),
        ("rp", "123456782-RP-0002", "123456782RP0002", "123456782 RP 0002"),
        ("qst", "1234567890 TQ 0001", "1234567890TQ0001", "1234567890 TQ 0001"),
        ("pst_bc", "pst12345678", "PST-1234-5678", "PST-1234-5678"),
    ],
)
def test_valid_numbers(kind: str, typed: str, number: str, display: str) -> None:
    result = check_number(kind, typed)
    assert (result.valid, result.number, result.display) == (True, number, display)


@pytest.mark.parametrize(
    ("kind", "typed", "code"),
    [
        ("rt", "123456782RT001", "orgsettings.registration.program_format"),
        ("rt", "123456782RP0001", "orgsettings.registration.program_mismatch"),
        ("rt", "123456789RT0001", "orgsettings.registration.bn_check_digit"),
        ("rt", "123456782RT0000", "orgsettings.registration.reference_zero"),
        ("bn", "12345678", "orgsettings.registration.bn_format"),
        ("bn", "123456789", "orgsettings.registration.bn_check_digit"),
        ("qst", "1234567890TQ0000", "orgsettings.registration.qst_format"),
        ("qst", "123456789TQ0001", "orgsettings.registration.qst_format"),
        ("pst_bc", "PST-12", "orgsettings.registration.pst_bc_format"),
    ],
)
def test_invalid_numbers_carry_an_example(kind: str, typed: str, code: str) -> None:
    result = check_number(kind, typed)
    assert not result.valid and result.code == code
    assert EXAMPLES[kind].replace(" ", "") in result.message.replace(" ", ""), result.message
    with pytest.raises(ValidationError) as caught:
        validate_number(kind, typed)
    assert caught.value.code == code


def test_invalid_rt_names_the_example() -> None:
    result = check_number("rt", "12345 RT 1")
    assert "123456782 RT 0001" in result.message


def test_unknown_kind() -> None:
    assert check_number("vat", "1").code == "orgsettings.registration.type_invalid"


@pytest.mark.django_db
def test_check_endpoint() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    client = Client()
    client.force_login(people(org)["owner"])
    url = f"/api/v1/o/{org.public_id}/tax/numbers/check"
    bad = client.post(
        url, {"type": "rt", "number": "123456782RT001"}, content_type="application/json"
    )
    assert bad.status_code == 200
    assert bad.json()["valid"] is False and "123456782 RT 0001" in bad.json()["message"]
    good = client.post(
        url, {"type": "qst", "number": "1234567890tq0001"}, content_type="application/json"
    )
    assert good.json() == {
        "type": "qst",
        "valid": True,
        "number": "1234567890TQ0001",
        "display": "1234567890 TQ 0001",
        "code": "",
        "message": "",
        "example": "1234567890 TQ 0001",
    }
