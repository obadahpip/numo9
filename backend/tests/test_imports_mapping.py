"""B-03-T03 — ImportMapping model (org, entity, column → field, saved name) + auto-suggest.

Acceptance: "Courriel" maps to email. Also: the other French and English headers of a Quebec
export, accents/case/punctuation ignored, similar headers flagged as such, short names exact only
("NB" never becomes a Business Number), one field per column and one column per field, validation
(unknown field, field twice, required missing), saved mappings (unique name per organisation and
entity, header fingerprint, found again for the same headers in another order/case, use count,
organisation-scoped, audited).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.audit.models import AuditEvent
from numo9.imports import mapping
from numo9.imports.fields import ImportEntity, ImportField, UnknownEntity, get_entity
from numo9.imports.mapping import (
    Confidence,
    check_mapping,
    find_saved,
    header_key,
    join_names,
    normalise,
    resolve,
    save_mapping,
    similarity,
    suggest,
)
from numo9.imports.models import ImportMapping
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

CONTACT = "contacts.contact"


def fields_of(headers: list[str], entity: str = CONTACT) -> dict[str, tuple[str, str]]:
    return {s.header: (s.field, s.confidence.value) for s in suggest(entity, headers)}


# ---- auto-suggest (no database) ----------------------------------------------------------------


def test_courriel_maps_to_email() -> None:
    assert fields_of(["Courriel"]) == {"Courriel": ("email", "exact_fr")}


def test_quebec_export_headers() -> None:
    # The wireframe's file (frame 19).
    headers = [
        "Nom",
        "Courriel",
        "No client",
        "NE",
        "Province",
        "Code postal",
        "Devise",
        "Ref ancien",
        "Notes internes",
    ]
    assert fields_of(headers) == {
        "Nom": ("display_name", "exact_fr"),
        "Courriel": ("email", "exact_fr"),
        "No client": ("number", "similar"),
        "NE": ("bn", "exact_fr"),
        "Province": ("billing_province", "exact"),
        "Code postal": ("billing_postal_code", "exact_fr"),
        "Devise": ("currency", "exact_fr"),
        "Ref ancien": ("", "none"),
        "Notes internes": ("", "none"),
    }


def test_english_headers_and_template_labels() -> None:
    entity = get_entity(CONTACT)
    labels = [str(item.label) for item in entity.fields]
    assert [s.field for s in suggest(CONTACT, labels)] == list(entity.field_keys)
    assert all(s.confidence == Confidence.EXACT for s in suggest(CONTACT, labels))


@pytest.mark.parametrize(
    ("header", "field"),
    [
        ("E-mail", "email"),
        ("EMAIL ADDRESS", "email"),
        ("Adresse électronique", "email"),
        ("adresse electronique", "email"),
        ("  Téléphone ", "phone"),
        ("Postal_Code", "billing_postal_code"),
        ("Zip", "billing_postal_code"),
        ("Business Number", "bn"),
        ("Raison sociale", "legal_name"),
        ("Pays", "billing_country"),
        ("External ID", "external_id"),
        ("Contact number", "number"),
    ],
)
def test_accents_case_and_punctuation_are_ignored(header: str, field: str) -> None:
    assert suggest(CONTACT, [header])[0].field == field


@pytest.mark.parametrize(
    ("header", "field"),
    [
        ("Customer e-mail address", "email"),
        ("Emial", "email"),
        ("Postal cde", "billing_postal_code"),
        ("Contact numbr", "number"),
    ],
)
def test_similar_headers_are_suggested_as_similar(header: str, field: str) -> None:
    (only,) = suggest(CONTACT, [header])
    assert (only.field, only.confidence) == (field, Confidence.SIMILAR)
    assert mapping.SIMILAR_THRESHOLD <= only.score < 1


def test_short_names_only_match_exactly() -> None:
    # NB is New Brunswick or "note bene", never the Business Number (BN) nor NE.
    assert fields_of(["NB", "BM", "Te"]) == {
        "NB": ("", "none"),
        "BM": ("", "none"),
        "Te": ("", "none"),
    }
    assert similarity("nb", "bn") == 0.0


def test_one_field_per_column_and_one_column_per_field() -> None:
    result = fields_of(["Email", "Courriel", "E-mail address"])
    assert sorted(field for field, _ in result.values()) == ["", "", "email"]
    assert result["Email"] == ("email", "exact")  # English exact wins ties, first column first


def test_exact_beats_similar_for_the_same_field() -> None:
    result = fields_of(["Emial", "Courriel"])
    assert result == {"Emial": ("", "none"), "Courriel": ("email", "exact_fr")}


def test_people_entity() -> None:
    result = fields_of(
        ["Contact", "Prénom", "Nom de famille", "Courriel", "Poste"], "contacts.person"
    )
    assert result == {
        "Contact": ("contact_ref", "exact"),
        "Prénom": ("first_name", "exact_fr"),
        "Nom de famille": ("last_name", "exact_fr"),
        "Courriel": ("email", "exact_fr"),
        "Poste": ("job_title", "exact_fr"),
    }


def test_normalise_and_header_key() -> None:
    assert normalise("  N° de Client ") == "n de client"
    assert normalise("Œuvre—Café") == "oeuvre cafe"
    assert header_key(["Nom", "Courriel"]) == header_key(["courriel", " NOM "])
    assert header_key(["Nom", "Courriel"]) != header_key(["Nom", "Courriel", "Devise"])


def test_unknown_entity() -> None:
    with pytest.raises(UnknownEntity):
        suggest("nothing.here", ["Name"])


def test_join_names() -> None:
    assert join_names(["A"]) == "A"
    assert join_names(["A", "B"]) == "A and B"
    assert join_names(["A", "B", "C"]) == "A, B and C"


# ---- validation -------------------------------------------------------------------------------


def problems(columns: object, entity: str = CONTACT) -> list[str]:
    with pytest.raises(ValidationError) as error:
        check_mapping(entity, columns)
    return [e.code or "" for e in error.value.error_dict.get("columns", [])] or [
        e.code or "" for e in error.value.error_dict.get("entity", [])
    ]


def test_a_valid_mapping_passes() -> None:
    check_mapping(CONTACT, {"Nom": "display_name", "Courriel": "email", "Notes": ""})


def test_every_problem_is_reported_at_once() -> None:
    codes = problems({"Courriel": "email", "E-mail": "email", "X": "favourite_colour"})
    assert codes == [
        "imports.mapping.field_unknown",
        "imports.mapping.field_twice",
        "imports.mapping.required_missing",
    ]


def test_field_twice_message_names_the_columns() -> None:
    with pytest.raises(ValidationError) as error:
        check_mapping(CONTACT, {"Nom": "display_name", "Courriel": "email", "E-mail": "email"})
    (message,) = error.value.message_dict["columns"]
    assert message == "Courriel and E-mail map to the same field, Email — choose one."


def test_required_message_names_the_field() -> None:
    with pytest.raises(ValidationError) as error:
        check_mapping(CONTACT, {"Courriel": "email"})
    assert error.value.message_dict["columns"] == ["Map a column to Display name: it is required."]


def test_malformed_and_unknown_entity() -> None:
    assert problems(["not", "a", "dict"]) == ["imports.mapping.invalid"]
    assert problems({"Nom": 3}) == ["imports.mapping.invalid"]
    assert problems({"Nom": "x"}, "nothing.here") == ["imports.mapping.entity_unknown"]


def test_registry_refuses_duplicate_field_keys() -> None:
    from numo9.imports.fields import register_entity

    with pytest.raises(ValueError, match="duplicate field keys"):
        register_entity(ImportEntity("x.y", "X", (ImportField("a", "A"), ImportField("a", "B"))))


# ---- saved mappings (database) -----------------------------------------------------------------


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Érable Café inc.")


@pytest.fixture
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


QUEBEC = {"Nom": "display_name", "Courriel": "email", "Devise": "currency", "Notes internes": ""}


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_save_and_find_again_for_the_same_headers() -> None:
    saved = save_mapping(CONTACT, "Export from old system (Mar 2026)", QUEBEC)
    assert saved.header_key == header_key(QUEBEC)
    assert find_saved(CONTACT, ["notes internes", "DEVISE", "courriel", "nom"]) == saved
    assert find_saved(CONTACT, ["Nom", "Courriel"]) is None
    assert find_saved("contacts.person", list(QUEBEC)) is None


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_resolve_uses_the_saved_mapping_then_auto_suggest() -> None:
    save_mapping(CONTACT, "Old system", {**QUEBEC, "Notes internes": "legal_name"})
    result = resolve(CONTACT, ["nom", "Courriel", "Devise", "Notes internes"])
    assert [(s.field, s.confidence.value) for s in result] == [
        ("display_name", "saved"),
        ("email", "saved"),
        ("currency", "saved"),
        ("legal_name", "saved"),
    ]
    # Without a saved mapping for these headers: auto-suggest.
    assert resolve(CONTACT, ["Nom", "Courriel"])[1].confidence == Confidence.EXACT_FR


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_resolve_with_a_chosen_mapping_and_new_headers() -> None:
    saved = save_mapping(CONTACT, "Old system", QUEBEC)
    result = resolve(CONTACT, ["Nom", "Courriel", "Ville", "E-mail"], saved)
    assert mapping.as_columns(result) == {
        "Nom": "display_name",
        "Courriel": "email",
        "Ville": "billing_city",  # new header: suggested among the fields left free
        "E-mail": "",  # email is already taken by the saved mapping
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_names_are_unique_per_organisation_and_entity(org: Organisation) -> None:
    save_mapping(CONTACT, "Old system", QUEBEC)
    with pytest.raises(ValidationError) as error:
        save_mapping(CONTACT, "  old   SYSTEM ", QUEBEC)
    assert error.value.error_dict["name"][0].code == "imports.mapping.name_taken"
    # The same name for another entity is fine.
    save_mapping("contacts.person", "Old system", {"Contact": "contact_ref"})
    # The database repeats the rule.
    duplicate = ImportMapping(organisation=org, entity=CONTACT, name="OLD SYSTEM", columns=QUEBEC)
    with pytest.raises(IntegrityError), transaction.atomic():
        super(ImportMapping, duplicate).save()


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_invalid_mappings_are_not_saved() -> None:
    with pytest.raises(ValidationError) as error:
        save_mapping(CONTACT, "Bad", {"Courriel": "email"})
    assert "columns" in error.value.error_dict
    with pytest.raises(ValidationError) as error:
        save_mapping(CONTACT, "   ", QUEBEC)
    assert error.value.error_dict["name"][0].code == "imports.mapping.name_required"
    assert ImportMapping.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_update_a_mapping_and_count_uses() -> None:
    saved = save_mapping(CONTACT, "Old system", QUEBEC)
    save_mapping(CONTACT, "Old system v2", {**QUEBEC, "Ville": "billing_city"}, mapping=saved)
    saved.refresh_from_db()
    assert saved.name == "Old system v2"
    assert saved.header_key == header_key([*QUEBEC, "Ville"])
    mapping.record_use(saved)
    mapping.record_use(saved)
    assert saved.use_count == 2
    assert saved.last_used_at is not None


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_changes_are_audited_but_not_the_use_count() -> None:
    saved = save_mapping(CONTACT, "Old system", QUEBEC)
    mapping.record_use(saved)
    saved.name = "Renamed"
    saved.save()
    actions = sorted(
        AuditEvent.objects.filter(object_type="imports.ImportMapping").values_list(
            "action", flat=True
        )
    )
    assert actions == ["imports.importmapping.created", "imports.importmapping.updated"]


@pytest.mark.django_db
def test_mappings_are_organisation_scoped(org: Organisation) -> None:
    other = Organisation.objects.create(name="Nord Ltd.")
    with org_context(org):
        save_mapping(CONTACT, "Old system", QUEBEC)
    with org_context(other):
        assert find_saved(CONTACT, list(QUEBEC)) is None
        assert ImportMapping.objects.count() == 0
        save_mapping(CONTACT, "Old system", QUEBEC)  # the same name in another organisation
