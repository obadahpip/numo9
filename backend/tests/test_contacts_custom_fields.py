"""B-01-T09 — custom field definitions and values (JSONB checked against the definitions).

Acceptance: type mismatch rejected. Also: the four types and their canonical stored forms; unknown
keys refused; empty values removed; required fields on creation and when emptied (not blocking
older records); unchanged values stay valid after a settings change; removed fields keep their
values but take no new ones; definitions — key format, unique and locked, English label required,
choice lists, at most 30 per record type, type locked once used; labels per language; audit.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.utils import translation

from numo9.audit.models import AuditEvent
from numo9.contacts.models import Contact, CustomFieldDefinition, CustomFieldType
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db

INDUSTRIES = [
    {"value": "construction", "labels": {"en-ca": "Construction", "fr-ca": "Construction"}},
    {"value": "retail", "labels": {"en-ca": "Retail", "fr-ca": "Commerce de détail"}},
]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def field(org: Organisation, key: str, field_type: str, **extra: Any) -> CustomFieldDefinition:
    extra.setdefault("label_i18n", {"en-ca": key.replace("_", " ").title() or "Label"})
    d = CustomFieldDefinition(organisation=org, key=key, field_type=field_type, **extra)
    d.save()
    return d


@pytest.fixture
def fields(org: Organisation) -> dict[str, CustomFieldDefinition]:
    return {
        "region_code": field(org, "region_code", CustomFieldType.TEXT),
        "employees": field(org, "employees", CustomFieldType.NUMBER),
        "since": field(org, "since", CustomFieldType.DATE),
        "industry": field(org, "industry", CustomFieldType.SELECT, options=INDUSTRIES),
    }


def codes(excinfo: pytest.ExceptionInfo[ValidationError]) -> dict[str, list[str]]:
    return {f: [e.code or "" for e in errs] for f, errs in excinfo.value.error_dict.items()}


# ---- acceptance: type mismatch rejected --------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("employees", "twelve"),
        ("employees", True),
        ("employees", [12]),
        ("since", "2026-02-30"),
        ("since", "14/11/2026"),
        ("since", 20261114),
        ("industry", "mining"),
        ("industry", 1),
        ("region_code", 42),
        ("region_code", {"a": 1}),
    ],
)
def test_a_value_of_the_wrong_type_is_rejected(
    org: Organisation, fields: dict[str, CustomFieldDefinition], key: str, value: Any
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple", custom_fields={key: value})
    assert codes(excinfo) == {f"custom_fields.{key}": ["contacts.custom_field.type_mismatch"]}
    assert not Contact.objects.exists()


def test_the_message_names_the_field_and_what_it_needs(
    org: Organisation, fields: dict[str, CustomFieldDefinition]
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple", custom_fields={"employees": "twelve"})
    assert "Employees needs a number" in str(excinfo.value)


# ---- values -------------------------------------------------------------------------------------


def test_values_are_stored_in_canonical_form(
    org: Organisation, fields: dict[str, CustomFieldDefinition]
) -> None:
    item = contact(
        org,
        "Maple",
        custom_fields={
            "region_code": "  GTA   west ",
            "employees": "1,250.50",
            "since": date(2019, 4, 1),
            "industry": "construction",
        },
    )
    item.refresh_from_db()
    assert item.custom_fields == {
        "region_code": "GTA west",
        "employees": "1250.50",
        "since": "2019-04-01",
        "industry": "construction",
    }
    assert contact(org, "Other", custom_fields={"employees": 12}).custom_fields == {
        "employees": "12"
    }


def test_unknown_keys_are_refused_and_empty_values_removed(
    org: Organisation, fields: dict[str, CustomFieldDefinition]
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple", custom_fields={"colour": "blue"})
    assert codes(excinfo) == {"custom_fields.colour": ["contacts.custom_field.unknown"]}
    item = contact(org, "Maple", custom_fields={"region_code": " ", "employees": None})
    assert item.custom_fields == {}
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "List", custom_fields=["a"])
    assert codes(excinfo) == {"custom_fields": ["contacts.custom_field.not_an_object"]}


def test_text_is_limited_to_500_characters(
    org: Organisation, fields: dict[str, CustomFieldDefinition]
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "Maple", custom_fields={"region_code": "x" * 501})
    assert codes(excinfo) == {"custom_fields.region_code": ["contacts.custom_field.too_long"]}


def test_required_fields(org: Organisation, fields: dict[str, CustomFieldDefinition]) -> None:
    old = contact(org, "Before the rule")
    field(org, "account_manager", CustomFieldType.TEXT, required=True)
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "New")
    assert codes(excinfo) == {"custom_fields.account_manager": ["contacts.custom_field.required"]}
    old.display_name = "Renamed"
    old.save()  # an older record isn't blocked by a field added later
    item = contact(org, "New", custom_fields={"account_manager": "Anne"})
    item.custom_fields = {}
    with pytest.raises(ValidationError) as excinfo:
        item.save()
    assert codes(excinfo) == {"custom_fields.account_manager": ["contacts.custom_field.required"]}


def test_unchanged_values_stay_valid_after_a_settings_change(
    org: Organisation, fields: dict[str, CustomFieldDefinition]
) -> None:
    item = contact(org, "Maple", custom_fields={"industry": "retail", "employees": "5"})
    industry = fields["industry"]
    industry.options = INDUSTRIES[:1]
    industry.save()
    fields["employees"].soft_delete()
    item.display_name = "Maple Supply Ltd."
    item.save()  # "retail" and the removed field's value are kept as they were
    item.refresh_from_db()
    assert item.custom_fields == {"industry": "retail", "employees": "5"}
    item.custom_fields = {"industry": "retail", "employees": "6"}
    with pytest.raises(ValidationError) as excinfo:
        item.save()
    assert codes(excinfo) == {"custom_fields.employees": ["contacts.custom_field.removed"]}
    item.custom_fields = {"industry": "mining", "employees": "5"}
    with pytest.raises(ValidationError) as excinfo:
        item.save()
    assert codes(excinfo) == {"custom_fields.industry": ["contacts.custom_field.type_mismatch"]}


def test_values_belong_to_the_organisation(
    org: Organisation, fields: dict[str, CustomFieldDefinition]
) -> None:
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other), pytest.raises(ValidationError) as excinfo:
        contact(other, "Elsewhere", custom_fields={"employees": "3"})
    assert codes(excinfo) == {"custom_fields.employees": ["contacts.custom_field.unknown"]}


# ---- definitions --------------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["industry-type", "1st", "with space", "x" * 41, ""])
def test_keys_have_a_fixed_format(org: Organisation, key: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        field(org, key, CustomFieldType.TEXT)
    assert "contacts.custom_field.key_format" in codes(excinfo).get("key", [])


def test_keys_are_tidied_to_lower_case(org: Organisation) -> None:
    assert field(org, " Industry ", CustomFieldType.TEXT).key == "industry"


def test_keys_are_unique_even_after_removal_and_never_change(org: Organisation) -> None:
    d = field(org, "industry", CustomFieldType.TEXT)
    with pytest.raises(ValidationError) as excinfo:
        field(org, "industry", CustomFieldType.NUMBER)
    assert codes(excinfo) == {"key": ["contacts.custom_field.key_taken"]}
    d.key = "sector"
    with pytest.raises(ValidationError) as excinfo:
        d.save()
    assert codes(excinfo) == {"key": ["contacts.custom_field.key_locked"]}
    d.refresh_from_db()
    d.soft_delete()
    with pytest.raises(ValidationError):
        field(org, "industry", CustomFieldType.TEXT)


def test_an_english_label_is_required_and_labels_follow_the_language(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        field(org, "industry", CustomFieldType.TEXT, label_i18n={"fr-ca": "Secteur"})
    assert codes(excinfo) == {"label_i18n": ["contacts.custom_field.label_required"]}
    d = field(
        org,
        "industry",
        CustomFieldType.SELECT,
        label_i18n={"en-ca": "Industry", "fr-ca": "Secteur"},
        options=INDUSTRIES,
    )
    with translation.override("fr-ca"):
        assert d.label == "Secteur"
    assert d.label_in("en-ca") == "Industry"
    assert d.option_label("retail", "fr-ca") == "Commerce de détail"
    no_fr = field(org, "region_code", CustomFieldType.TEXT)
    assert no_fr.label_in("fr-ca") == "Region Code"  # English until Phase 6 fills French


@pytest.mark.parametrize(
    ("options", "code"),
    [
        ([], "contacts.custom_field.options_required"),
        ([{"value": "a"}], "contacts.custom_field.option_invalid"),
        (
            [{"value": "a", "labels": {"en-ca": "A"}}, {"value": "a", "labels": {"en-ca": "A"}}],
            "contacts.custom_field.option_duplicate",
        ),
        (
            [{"value": f"v{i}", "labels": {"en-ca": f"V{i}"}} for i in range(101)],
            "contacts.custom_field.options_limit",
        ),
    ],
)
def test_choice_lists_are_checked(org: Organisation, options: list[Any], code: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        field(org, "industry", CustomFieldType.SELECT, options=options)
    assert codes(excinfo) == {"options": [code]}


def test_options_are_dropped_from_other_types(org: Organisation) -> None:
    assert field(org, "note", CustomFieldType.TEXT, options=INDUSTRIES).options == []


def test_at_most_30_custom_fields_per_record_type(org: Organisation) -> None:
    created = [field(org, f"field_{i}", CustomFieldType.TEXT) for i in range(30)]
    with pytest.raises(ValidationError) as excinfo:
        field(org, "field_31", CustomFieldType.TEXT)
    assert codes(excinfo) == {"key": ["contacts.custom_field.limit"]}
    created[0].soft_delete()
    assert field(org, "field_31", CustomFieldType.TEXT).key == "field_31"


def test_the_type_is_locked_once_a_record_has_a_value(
    org: Organisation, fields: dict[str, CustomFieldDefinition]
) -> None:
    unused = fields["since"]
    unused.field_type = CustomFieldType.TEXT
    unused.save()  # no values yet: allowed
    contact(org, "Maple", custom_fields={"employees": "12"})
    employees = fields["employees"]
    employees.field_type = CustomFieldType.TEXT
    with pytest.raises(ValidationError) as excinfo:
        employees.save()
    assert codes(excinfo) == {"field_type": ["contacts.custom_field.type_locked"]}


def test_definitions_and_values_are_audited(
    org: Organisation, fields: dict[str, CustomFieldDefinition]
) -> None:
    item = contact(org, "Maple", custom_fields={"employees": "12"})
    item.custom_fields = {"employees": "13"}
    item.save()
    assert AuditEvent.objects.filter(action="contacts.customfielddefinition.created").count() == 4
    last = AuditEvent.objects.filter(object_id=str(item.public_id)).order_by("id").last()
    assert last is not None
    assert last.changes == {"custom_fields": [{"employees": "12"}, {"employees": "13"}]}
