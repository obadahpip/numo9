"""V-02-T03 — ``Tag`` + ``OrgTag`` (practice-scoped, colour enum).

Acceptance: a tag name is unique per practice — case, accents and spaces ignored, in the service
and in the database — while another practice may use the same name. Also: the 12 named colours
(nothing else); rename and recolour; tags only on the practice's clients, once each; another
practice's tags on the same client are its own; stopping service removes the practice's tags on
that client.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.tenancy.models import Organisation, Practice, PracticeAssignment
from numo9.workspace.models import OrgTag, Tag, TagColour
from numo9.workspace.tags import (
    TagError,
    create_tag,
    recolour_tag,
    rename_tag,
    tag_organisation,
    tags_of,
    untag_organisation,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def practice() -> Practice:
    return Practice.objects.create(name="Abuodeh CPA")


def code(error: pytest.ExceptionInfo[TagError]) -> str:
    return str(error.value.code)


def test_name_unique_per_practice(practice: Practice) -> None:
    quebec = create_tag(practice, "  Québec  clients ", "violet")
    assert (quebec.name, quebec.name_key, quebec.colour) == (
        "Québec clients",
        "quebec clients",
        "violet",
    )
    for clash in ("québec clients", "QUEBEC CLIENTS", "Quebec   clients"):
        with pytest.raises(TagError) as taken:
            create_tag(practice, clash)
        assert code(taken) == "workspace.tag.name_taken"
    with pytest.raises(IntegrityError), transaction.atomic():
        Tag.objects.create(practice=practice, name="QUÉBEC clients")
    other = Practice.objects.create(name="Other CPA")
    assert create_tag(other, "Québec clients").practice == other


def test_names_and_colours(practice: Practice) -> None:
    assert len(TagColour.values) == 12
    with pytest.raises(TagError) as colour:
        create_tag(practice, "VIP", "gold")
    assert code(colour) == "workspace.tag.colour"
    for bad, expected in (
        ("", "workspace.tag.name_required"),
        ("x" * 41, "workspace.tag.name_long"),
    ):
        with pytest.raises(TagError) as refused:
            create_tag(practice, bad)
        assert code(refused) == expected
    vip = create_tag(practice, "VIP", "green")
    payroll = create_tag(practice, "Payroll")
    assert payroll.colour == "slate"
    with pytest.raises(TagError):
        rename_tag(payroll, "vip")
    assert rename_tag(vip, "Very important").name_key == "very important"
    assert recolour_tag(vip, "blue").colour == "blue"
    with pytest.raises(IntegrityError), transaction.atomic():
        Tag.objects.filter(pk=vip.pk).update(colour="gold")


def test_tags_on_clients(practice: Practice) -> None:
    maple = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    stranger = Organisation.objects.create(name="Not a client Inc.")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=maple)
    other = Practice.objects.create(name="Other CPA")
    PracticeAssignment.objects.create(practice=other, organisation=maple)
    year_end, payroll = (
        create_tag(practice, "Year-end soon", "red"),
        create_tag(practice, "Payroll"),
    )
    theirs = create_tag(other, "Their tag")
    tag_organisation(year_end, maple)
    tag_organisation(year_end, maple)  # once
    tag_organisation(payroll, maple)
    tag_organisation(theirs, maple)
    assert [t.name for t in tags_of(practice, maple)] == ["Payroll", "Year-end soon"]
    assert [t.name for t in tags_of(other, maple)] == ["Their tag"]
    with pytest.raises(TagError) as outsider:
        tag_organisation(year_end, stranger)
    assert code(outsider) == "workspace.tag.not_served"
    assert untag_organisation(payroll, maple) == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        OrgTag.objects.create(tag=year_end, organisation=maple)
    assignment.delete()
    assert list(OrgTag.objects.values_list("tag__name", flat=True)) == ["Their tag"]
