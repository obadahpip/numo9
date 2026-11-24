"""K-01-T07 — legal-name validation in the organisation settings (A-05; gap-55): "1001633222" is
refused with a message naming it; a name needs at least two letters ("1001633222 A" too); real
names — numbered companies, accented letters, "3M Canada" — are accepted; the settings API answers
the message on the field.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from numo9.orgsettings.validators import validate_organisation_legal_name
from tests.journal_helpers import people
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db


@pytest.mark.gap("gap-55")
@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("1001633222", "orgsettings.legal_name.numeric"),
        ("123-456-789", "orgsettings.legal_name.numeric"),
        ("1001633222 A", "orgsettings.legal_name.too_few_letters"),
        ("Z", "orgsettings.legal_name.too_few_letters"),
    ],
)
def test_refused(value: str, code: str) -> None:
    with pytest.raises(ValidationError) as refused:
        validate_organisation_legal_name(value)
    assert refused.value.code == code
    assert value in refused.value.messages[0]


@pytest.mark.parametrize(
    "value", ["1001633222 Ontario Inc.", "Boulangerie Érable ltée", "3M Canada", "Ôz", ""]
)
def test_accepted(value: str) -> None:
    validate_organisation_legal_name(value)


@pytest.mark.gap("gap-55")
def test_settings_api_refuses_a_number() -> None:
    org = report_books()["org"]
    owner = people(org)["owner"]
    client = Client()
    client.force_login(owner)
    answer = client.patch(
        f"/api/v1/o/{org.public_id}/settings",
        {"legal_name": "1001633222"},
        content_type="application/json",
    )
    assert answer.status_code == 400
    assert "1001633222" in answer.json()["legal_name"][0]
