"""Practice groups of organisations (V-02-T02): create, rename, move, file organisations.

Rules (Phase 0 plan V-02):

- groups belong to one practice; a group's parent is a group of the same practice;
- depth 1 (top level) to ``GROUP_MAX_DEPTH`` (5) — a move is refused when the moved group's
  deepest descendant would end deeper (``workspace.group.too_deep``); the database checks the
  depth too;
- a group can't move inside itself or one of its descendants (``workspace.group.into_itself``);
  a materialised path can't hold a cycle anyway;
- names are unique among siblings, case and accents ignored (``workspace.group.name_taken``);
- only organisations the practice actively serves can be filed (``workspace.group.not_served``);
  when the practice stops serving an organisation its memberships in that practice's groups go
  (signal on ``PracticeAssignment``).

Every refusal is a ``GroupError`` (``ValidationError`` with a stable code) naming the reason.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.utils.translation import gettext as _

from numo9.tenancy.models import Organisation, Practice, PracticeAssignment

from .models import GROUP_MAX_DEPTH, OrgGroup, OrgGroupMembership


class GroupError(ValidationError):
    pass


def _key(name: str) -> str:
    folded = unicodedata.normalize("NFKD", " ".join(name.split()).casefold())
    return "".join(c for c in folded if not unicodedata.combining(c))


def _clean_name(name: str) -> str:
    cleaned = " ".join((name or "").split())
    if not cleaned:
        raise GroupError(_("Give the group a name."), code="workspace.group.name_required")
    if len(cleaned) > 80:
        raise GroupError(_("Use 80 characters or fewer."), code="workspace.group.name_long")
    return cleaned


def _siblings(practice: Practice, parent: OrgGroup | None) -> Any:
    if parent is None:
        return OrgGroup.objects.get_root_nodes().filter(practice=practice)
    return OrgGroup.objects.get_children(parent)


def _assert_name_free(
    practice: Practice, parent: OrgGroup | None, name: str, exclude: OrgGroup | None = None
) -> None:
    key = _key(name)
    for sibling in _siblings(practice, parent):
        if exclude is not None and sibling.pk == exclude.pk:
            continue
        if _key(sibling.name) == key:
            raise GroupError(
                _("There's already a group called %(name)s here.") % {"name": sibling.name},
                code="workspace.group.name_taken",
            )


def _subtree_height(group: OrgGroup) -> int:
    """Levels below and including ``group`` (a leaf: 1)."""
    deepest = (
        OrgGroup.objects.filter(path__startswith=group.path)
        .order_by("-depth")
        .values_list("depth", flat=True)
        .first()
    )
    height: int = int(deepest or group.depth) - int(group.depth) + 1
    return height


def _too_deep() -> GroupError:
    return GroupError(
        _("Groups can be %(max)d levels deep at most.") % {"max": GROUP_MAX_DEPTH},
        code="workspace.group.too_deep",
    )


@transaction.atomic
def create_group(practice: Practice, name: str, parent: OrgGroup | None = None) -> OrgGroup:
    name = _clean_name(name)
    if parent is not None:
        if parent.practice_id != practice.pk:
            raise GroupError(
                _("That group belongs to another practice."), code="workspace.group.other_practice"
            )
        if parent.depth + 1 > GROUP_MAX_DEPTH:
            raise _too_deep()
    _assert_name_free(practice, parent, name)
    if parent is None:
        group: OrgGroup = OrgGroup.objects.add_root({"practice": practice, "name": name})
    else:
        group = OrgGroup.objects.add_child(parent, {"practice": practice, "name": name})
    return group


@transaction.atomic
def rename_group(group: OrgGroup, name: str) -> OrgGroup:
    name = _clean_name(name)
    _assert_name_free(group.practice, OrgGroup.objects.get_parent(group), name, exclude=group)
    group.name = name
    group.save(update_fields=["name", "updated_at"])
    return group


@transaction.atomic
def move_group(group: OrgGroup, parent: OrgGroup | None) -> OrgGroup:
    """Move ``group`` (with its sub-groups) under ``parent``, or to the top level (None)."""
    group = OrgGroup.objects.select_for_update().get(pk=group.pk)
    if parent is not None:
        parent = OrgGroup.objects.get(pk=parent.pk)
        if parent.practice_id != group.practice_id:
            raise GroupError(
                _("That group belongs to another practice."), code="workspace.group.other_practice"
            )
        if parent.path.startswith(group.path):
            raise GroupError(
                _("A group can't move inside itself or one of its sub-groups."),
                code="workspace.group.into_itself",
            )
        if parent.depth + _subtree_height(group) > GROUP_MAX_DEPTH:
            raise _too_deep()
    _assert_name_free(group.practice, parent, group.name, exclude=group)
    if parent is None:
        if group.is_root():
            return group
        OrgGroup.objects.move(group, OrgGroup.objects.get_root_nodes().first(), "sorted-sibling")
    else:
        OrgGroup.objects.move(group, parent, "sorted-child")
    group.refresh_from_db()
    return group


def add_organisation(group: OrgGroup, organisation: Organisation) -> OrgGroupMembership:
    served = PracticeAssignment.objects.filter(
        practice_id=group.practice_id, organisation=organisation, active=True
    ).exists()
    if not served:
        raise GroupError(
            _("%(organisation)s isn't a client of this practice.")
            % {"organisation": organisation.name},
            code="workspace.group.not_served",
        )
    membership, _created = OrgGroupMembership.objects.get_or_create(
        group=group, organisation=organisation
    )
    return membership


def remove_organisation(group: OrgGroup, organisation: Organisation) -> int:
    rows = OrgGroupMembership.objects.filter(group=group, organisation=organisation)
    count = rows.count()
    rows.delete()
    return count


def groups_of(practice: Practice) -> list[OrgGroup]:
    """The practice's groups in tree order (depth-first, siblings by name)."""
    return list(OrgGroup.objects.filter(practice=practice).order_by("path"))


def _forget_organisation(practice_id: int, organisation_id: int) -> None:
    from .tags import forget_organisation

    OrgGroupMembership.objects.filter(
        group__practice_id=practice_id, organisation_id=organisation_id
    ).delete()
    forget_organisation(practice_id, organisation_id)  # its tags too (V-02-T03)


def _assignment_saved(sender: Any, instance: PracticeAssignment, **kwargs: Any) -> None:
    if kwargs.get("raw") or instance.active:
        return
    _forget_organisation(instance.practice_id, instance.organisation_id)


def _assignment_deleted(sender: Any, instance: PracticeAssignment, **kwargs: Any) -> None:
    _forget_organisation(instance.practice_id, instance.organisation_id)


def connect() -> None:
    post_save.connect(
        _assignment_saved, sender=PracticeAssignment, dispatch_uid="numo9.workspace.groups.saved"
    )
    post_delete.connect(
        _assignment_deleted,
        sender=PracticeAssignment,
        dispatch_uid="numo9.workspace.groups.deleted",
    )
