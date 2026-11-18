"""Practice tags on client organisations (V-02-T03).

``create_tag(practice, name, colour)``, ``rename_tag``, ``recolour_tag``, ``tag_organisation``,
``untag_organisation``, ``tags_of(practice, organisation)``. Names are unique per practice with
case, accents and repeated spaces ignored (``workspace.tag.name_taken``; the database enforces it
on ``name_key``); 1–40 characters. Only organisations the practice actively serves can be tagged
(``workspace.tag.not_served``); when the practice stops serving one, its tags on it go. The
directory's search and tag filter read the practice's tags through the summary's tags provider.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from numo9.tenancy.models import Organisation, Practice, PracticeAssignment

from .models import OrgTag, Tag, TagColour

NAME_MAX = 40


class TagError(ValidationError):
    pass


def tag_key(name: str) -> str:
    folded = unicodedata.normalize("NFKD", " ".join((name or "").split()).casefold())
    return "".join(c for c in folded if not unicodedata.combining(c))[:NAME_MAX]


def _name(name: str) -> str:
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise TagError(_("Give the tag a name."), code="workspace.tag.name_required")
    if len(cleaned) > NAME_MAX:
        raise TagError(
            _("Use %(max)d characters or fewer.") % {"max": NAME_MAX},
            code="workspace.tag.name_long",
        )
    return cleaned


def _colour(colour: str) -> str:
    if colour not in TagColour.values:
        raise TagError(_("Choose one of the 12 colours."), code="workspace.tag.colour")
    return colour


def _taken(practice: Practice, name: str, exclude: Tag | None = None) -> None:
    clash = Tag.objects.filter(practice=practice, name_key=tag_key(name))
    if exclude is not None:
        clash = clash.exclude(pk=exclude.pk)
    found = clash.first()
    if found is not None:
        raise TagError(
            _("There's already a tag called %(name)s.") % {"name": found.name},
            code="workspace.tag.name_taken",
        )


def _save(tag: Tag, **kwargs: Any) -> Tag:
    try:
        with transaction.atomic():
            tag.save(**kwargs)
    except IntegrityError:  # two people creating the same name at once
        raise TagError(
            _("There's already a tag called %(name)s.") % {"name": tag.name},
            code="workspace.tag.name_taken",
        ) from None
    return tag


def _audit(
    action: str,
    tag: Tag,
    *,
    organisation: Organisation | None = None,
    changes: dict[str, Any] | None = None,
) -> None:
    """One audit event (V-02-T13); tagging also writes it in the organisation's log."""
    from numo9.audit.service import record

    record(
        f"workspace.tag.{action}",
        obj=tag,
        organisation=organisation,
        practice=tag.practice,
        changes=changes,
        meta={"tag": tag.name, **({"organisation": organisation.name} if organisation else {})},
    )


def create_tag(practice: Practice, name: str, colour: str = TagColour.SLATE) -> Tag:
    name, colour = _name(name), _colour(colour)
    _taken(practice, name)
    tag = _save(Tag(practice=practice, name=name, colour=colour))
    _audit("created", tag, changes={"name": [None, name], "colour": [None, colour]})
    return tag


def _directory_changed(tag: Tag, organisation_ids: Any = None) -> None:
    """The directory rows show tag names (search, tag filter): refresh the affected rows."""
    from .summary import tags_changed

    if organisation_ids is None:
        organisation_ids = list(
            OrgTag.objects.filter(tag=tag).values_list("organisation_id", flat=True)
        )
    tags_changed(tag.practice, organisation_ids)


def provide_tags(practice: Practice, organisation: Organisation) -> list[str]:
    """The directory's tags provider (``summary.register_tags_provider``): tag names."""
    return [tag.name for tag in tags_of(practice, organisation)]


def rename_tag(tag: Tag, name: str) -> Tag:
    name = _name(name)
    _taken(tag.practice, name, exclude=tag)
    before = tag.name
    tag.name = name
    saved = _save(tag, update_fields=["name", "updated_at"])
    if before != saved.name:
        _audit("renamed", saved, changes={"name": [before, saved.name]})
    _directory_changed(saved)
    return saved


def recolour_tag(tag: Tag, colour: str) -> Tag:
    before = tag.colour
    tag.colour = _colour(colour)
    saved = _save(tag, update_fields=["colour", "updated_at"])
    if before != saved.colour:
        _audit("recoloured", saved, changes={"colour": [before, saved.colour]})
    return saved


def tag_organisation(tag: Tag, organisation: Organisation) -> OrgTag:
    served = PracticeAssignment.objects.filter(
        practice_id=tag.practice_id, organisation=organisation, active=True
    ).exists()
    if not served:
        raise TagError(
            _("%(organisation)s isn't a client of this practice.")
            % {"organisation": organisation.name},
            code="workspace.tag.not_served",
        )
    row, created = OrgTag.objects.get_or_create(tag=tag, organisation=organisation)
    if created:
        _audit("organisation_tagged", tag, organisation=organisation)
        _directory_changed(tag, [organisation.pk])
    return row


def untag_organisation(tag: Tag, organisation: Organisation) -> int:
    rows = OrgTag.objects.filter(tag=tag, organisation=organisation)
    count = rows.count()
    rows.delete()
    if count:
        _audit("organisation_untagged", tag, organisation=organisation)
        _directory_changed(tag, [organisation.pk])
    return count


def delete_tag(tag: Tag) -> int:
    """Delete a tag; it comes off every organisation. Returns how many organisations had it."""
    affected = list(OrgTag.objects.filter(tag=tag).values_list("organisation_id", flat=True))
    _audit("deleted", tag, changes={"name": [tag.name, None]})
    tag.delete()
    _directory_changed(tag, affected)
    return len(affected)


def tags_of(practice: Practice, organisation: Organisation) -> list[Tag]:
    return list(
        Tag.objects.filter(practice=practice, assignments__organisation=organisation).order_by(
            "name_key"
        )
    )


def forget_organisation(practice_id: int, organisation_id: int) -> None:
    OrgTag.objects.filter(tag__practice_id=practice_id, organisation_id=organisation_id).delete()
