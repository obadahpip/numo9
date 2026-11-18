"""Bulk actions (V-03-T04, T06): what each action changes in one organisation.

Every action has

- ``practice_permission`` — checked once, for the practice, when the job is created;
- ``org_permission`` — checked **per organisation** (settings: ``organisation.settings.manage``
  there), on top of the directory access every row needs (rows the user can't reach are
  ``skipped: no_access``);
- ``clean(practice, params)`` — validates and resolves the parameters (unknown group, tag or
  member → ``400 bulk.bad_action``);
- ``diff(ctx)`` — the change it would make, computed **without writing** (the preview);
- ``apply(ctx)`` — makes it (the executor, one organisation per transaction).

``diff`` and ``apply`` answer a ``Change`` (before → after) or a ``Skip`` (reason code); a change
whose before equals its after is "no change".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.utils.translation import gettext as _

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.orgsettings.models import OrganisationSettings
from numo9.rbac.resolver import has_perm
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeAssignment,
    PracticeMember,
)
from numo9.workspace.models import OrgGroup, OrgGroupMembership, OrgTag, Tag

from .models import BulkAction
from .safe_settings import SAFE_SETTINGS, clean_settings

DIRECTORY_VIEW = "practice.directory.view"
GROUPS_MANAGE = "practice.groups.manage"
CLIENTS_ASSIGN = "practice.clients.assign"
SETTINGS_MANAGE = "organisation.settings.manage"


@dataclass(frozen=True)
class Change:
    before: dict[str, Any]
    after: dict[str, Any]

    @property
    def changed(self) -> bool:
        return self.before != self.after


@dataclass(frozen=True)
class Skip:
    reason: str


@dataclass
class Context:
    organisation: Organisation
    practice: Practice
    user: Any
    params: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)


def _bad(message: str) -> Exception:
    return api_error(errors.BULK_BAD_ACTION, message=message)


def _ids(value: Any, message: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise _bad(message)
    return value


def _one(model: Any, practice: Practice, value: Any, message: str, **lookup: Any) -> Any:
    import uuid

    try:
        key = uuid.UUID(str(value))
    except ValueError:
        raise _bad(message) from None
    found = model.objects.filter(practice=practice, **{lookup.get("field", "public_id"): key})
    row = found.first()
    if row is None:
        raise _bad(message)
    return row


class Action:
    key: str
    practice_permission: str = DIRECTORY_VIEW
    org_permission: str | None = None

    def clean(self, practice: Practice, params: Any) -> dict[str, Any]:
        raise NotImplementedError

    def diff(self, ctx: Context) -> Change | Skip:
        raise NotImplementedError

    def apply(self, ctx: Context) -> Change | Skip:
        raise NotImplementedError


# ---- group -------------------------------------------------------------------------------------


def _group_names(practice: Practice, organisation: Organisation) -> list[str]:
    return sorted(
        OrgGroupMembership.objects.filter(
            group__practice=practice, organisation=organisation
        ).values_list("group__name", flat=True)
    )


class GroupAction(Action):
    """``{"group": id, "mode": "add" | "move" | "remove"}`` — *move* leaves the practice's other
    groups."""

    key = BulkAction.GROUP
    practice_permission = GROUPS_MANAGE

    def clean(self, practice: Practice, params: Any) -> dict[str, Any]:
        params = params if isinstance(params, dict) else {}
        mode = params.get("mode", "move")
        if mode not in ("add", "move", "remove"):
            raise _bad(_("Choose whether to add, move or remove."))
        group = _one(
            OrgGroup, practice, params.get("group"), _("Choose one of the practice's groups.")
        )
        return {"group": str(group.public_id), "mode": mode}

    def _group(self, ctx: Context) -> OrgGroup:
        group: OrgGroup = OrgGroup.objects.get(practice=ctx.practice, public_id=ctx.params["group"])
        return group

    def diff(self, ctx: Context) -> Change:
        group = self._group(ctx)
        before = _group_names(ctx.practice, ctx.organisation)
        mode = ctx.params["mode"]
        if mode == "remove":
            after = [name for name in before if name != group.name]
        elif mode == "add":
            after = sorted({*before, group.name})
        else:
            after = [group.name]
        return Change({"groups": before}, {"groups": after})

    def apply(self, ctx: Context) -> Change:
        from numo9.workspace import groups

        change = self.diff(ctx)
        group = self._group(ctx)
        mode = ctx.params["mode"]
        if mode == "remove":
            groups.remove_organisation(group, ctx.organisation)
            return change
        if mode == "move":
            for other in OrgGroup.objects.filter(
                practice=ctx.practice, memberships__organisation=ctx.organisation
            ).exclude(pk=group.pk):
                groups.remove_organisation(other, ctx.organisation)
        groups.add_organisation(group, ctx.organisation)
        return change


# ---- tags --------------------------------------------------------------------------------------


def _tag_names(practice: Practice, organisation: Organisation) -> list[str]:
    return sorted(
        OrgTag.objects.filter(tag__practice=practice, organisation=organisation).values_list(
            "tag__name", flat=True
        )
    )


class TagsAction(Action):
    """``{"add": [tag ids], "remove": [tag ids]}``."""

    key = BulkAction.TAGS
    practice_permission = GROUPS_MANAGE

    def clean(self, practice: Practice, params: Any) -> dict[str, Any]:
        params = params if isinstance(params, dict) else {}
        message = _("Choose tags of the practice.")
        add = [_one(Tag, practice, v, message) for v in _ids(params.get("add", []), message)]
        remove = [_one(Tag, practice, v, message) for v in _ids(params.get("remove", []), message)]
        if not add and not remove:
            raise _bad(_("Choose at least one tag to add or remove."))
        if {t.pk for t in add} & {t.pk for t in remove}:
            raise _bad(_("A tag can't be added and removed at once."))
        return {
            "add": [str(t.public_id) for t in add],
            "remove": [str(t.public_id) for t in remove],
        }

    def _tags(self, ctx: Context, which: str) -> list[Tag]:
        return list(Tag.objects.filter(practice=ctx.practice, public_id__in=ctx.params[which]))

    def diff(self, ctx: Context) -> Change:
        before = _tag_names(ctx.practice, ctx.organisation)
        removed = {t.name for t in self._tags(ctx, "remove")}
        after = sorted({*before, *(t.name for t in self._tags(ctx, "add"))} - removed)
        return Change({"tags": before}, {"tags": after})

    def apply(self, ctx: Context) -> Change:
        from numo9.workspace import tags

        change = self.diff(ctx)
        for tag in self._tags(ctx, "add"):
            tags.tag_organisation(tag, ctx.organisation)
        for tag in self._tags(ctx, "remove"):
            tags.untag_organisation(tag, ctx.organisation)
        return change


# ---- staff -------------------------------------------------------------------------------------


def _assignment(ctx: Context) -> PracticeAssignment | None:
    return PracticeAssignment.objects.filter(
        practice=ctx.practice, organisation=ctx.organisation, active=True
    ).first()


def _staff_names(assignment: PracticeAssignment) -> list[str]:
    return sorted(
        member.user.name or member.user.email
        for member in assignment.assigned_staff.select_related("user")
    )


class StaffAction(Action):
    """``{"member": user id, "mode": "assign" | "unassign"}`` — a staff member of the practice on
    the organisation's assignment (direct access, A-01)."""

    key = BulkAction.STAFF
    practice_permission = CLIENTS_ASSIGN

    def clean(self, practice: Practice, params: Any) -> dict[str, Any]:
        params = params if isinstance(params, dict) else {}
        mode = params.get("mode", "assign")
        if mode not in ("assign", "unassign"):
            raise _bad(_("Choose whether to assign or unassign."))
        member = _one(
            PracticeMember,
            practice,
            params.get("member"),
            _("Choose a staff member of the practice."),
            field="user__public_id",
        )
        return {"member": str(member.user.public_id), "mode": mode}

    def _member(self, ctx: Context) -> PracticeMember:
        return PracticeMember.objects.select_related("user").get(
            practice=ctx.practice, user__public_id=ctx.params["member"]
        )

    def diff(self, ctx: Context) -> Change | Skip:
        assignment = _assignment(ctx)
        if assignment is None:
            return Skip("not_served")
        member = self._member(ctx)
        before = _staff_names(assignment)
        name = member.user.name or member.user.email
        if ctx.params["mode"] == "assign":
            after = sorted({*before, name})
        else:
            after = [n for n in before if n != name]
        return Change({"staff": before}, {"staff": after})

    def apply(self, ctx: Context) -> Change | Skip:
        change = self.diff(ctx)
        assignment = _assignment(ctx)
        if isinstance(change, Skip) or assignment is None:
            return change
        member = self._member(ctx)
        if ctx.params["mode"] == "assign":
            assignment.assigned_staff.add(member)
        else:
            assignment.assigned_staff.remove(member)
        return change


# ---- settings ----------------------------------------------------------------------------------


class SettingsAction(Action):
    """``{"settings": {key: value}}`` — safe settings only (``safe_settings``)."""

    key = BulkAction.SETTINGS
    org_permission = SETTINGS_MANAGE

    def clean(self, practice: Practice, params: Any) -> dict[str, Any]:
        params = params if isinstance(params, dict) else {}
        return {"settings": clean_settings(params.get("settings"))}

    def _settings(self, ctx: Context, create: bool = False) -> OrganisationSettings:
        """The organisation's settings — unsaved defaults when it has none yet, for the preview
        (which never writes); created when applying."""
        from numo9.orgsettings.service import get_settings

        if create:
            return get_settings(ctx.organisation)
        existing = OrganisationSettings._base_manager.filter(organisation=ctx.organisation).first()
        return existing or OrganisationSettings(
            organisation=ctx.organisation, time_zone=ctx.organisation.time_zone
        )

    def diff(self, ctx: Context) -> Change | Skip:
        current = self._settings(ctx)
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for key, value in ctx.params["settings"].items():
            setting = SAFE_SETTINGS[key]
            reason = setting.guard(ctx.organisation) if setting.guard else None
            if reason:
                return Skip(reason)
            before[key] = setting.read(current)
            after[key] = value
        return Change(before, after)

    def apply(self, ctx: Context) -> Change | Skip:
        change = self.diff(ctx)
        if isinstance(change, Skip) or not change.changed:
            return change
        current = self._settings(ctx, create=True)
        fields: list[str] = []
        for key, value in ctx.params["settings"].items():
            fields += SAFE_SETTINGS[key].write(current, value)
        current.validate(update_fields=fields)
        current.save()
        return change


# ---- message -----------------------------------------------------------------------------------


def recipients(organisation: Organisation) -> list[Any]:
    """Who a practice's message reaches: the organisation's owners and admins."""
    return [
        row.user
        for row in OrganisationMember.objects.select_related("user").filter(
            organisation=organisation,
            role__in=[OrganisationRole.OWNER, OrganisationRole.ADMIN],
            user__is_active=True,
        )
    ]


class MessageAction(Action):
    """``{"subject": "...", "body": "..."}`` — a notification (in-app and email, A-07) to each
    organisation's owners and admins."""

    key = BulkAction.MESSAGE

    def clean(self, practice: Practice, params: Any) -> dict[str, Any]:
        params = params if isinstance(params, dict) else {}
        subject = str(params.get("subject") or "").strip()
        body = str(params.get("body") or "").strip()
        if not subject or len(subject) > 150:
            raise _bad(_("Write a subject of up to 150 characters."))
        if not body or len(body) > 5000:
            raise _bad(_("Write a message of up to 5,000 characters."))
        return {"subject": subject, "body": body}

    def diff(self, ctx: Context) -> Change | Skip:
        people = recipients(ctx.organisation)
        if not people:
            return Skip("no_recipients")
        return Change({}, {"recipients": len(people), "subject": ctx.params["subject"]})

    def apply(self, ctx: Context) -> Change | Skip:
        from numo9.notifications.services import notify

        change = self.diff(ctx)
        if isinstance(change, Skip):
            return change
        notify(
            "practice.message",
            recipients(ctx.organisation),
            organisation=ctx.organisation,
            params={
                "practice": ctx.practice.name,
                "subject": ctx.params["subject"],
                "body": ctx.params["body"],
            },
        )
        return change


# ---- export ------------------------------------------------------------------------------------

EXPORT_COLUMNS = ("name", "business_number", "status", "groups", "tags", "staff")


class ExportAction(Action):
    """``{"format": "csv" | "xlsx"}`` — one line per organisation in the results file."""

    key = BulkAction.EXPORT

    def clean(self, practice: Practice, params: Any) -> dict[str, Any]:
        params = params if isinstance(params, dict) else {}
        fmt = params.get("format", "csv")
        if fmt not in ("csv", "xlsx"):
            raise _bad(_("Choose CSV or Excel."))
        return {"format": fmt}

    def diff(self, ctx: Context) -> Change:
        from numo9.workspace.models import OrgDirectorySummary

        summary = OrgDirectorySummary.objects.filter(
            practice=ctx.practice, organisation=ctx.organisation
        ).first()
        assignment = _assignment(ctx)
        return Change(
            {},
            {
                "name": ctx.organisation.name,
                "business_number": getattr(summary, "bn", "") or "",
                "status": getattr(summary, "status", "") or "",
                "groups": ", ".join(_group_names(ctx.practice, ctx.organisation)),
                "tags": ", ".join(_tag_names(ctx.practice, ctx.organisation)),
                "staff": ", ".join(_staff_names(assignment)) if assignment else "",
            },
        )

    def apply(self, ctx: Context) -> Change:
        return self.diff(ctx)


ACTIONS: dict[str, Action] = {
    action.key: action
    for action in (
        GroupAction(),
        TagsAction(),
        StaffAction(),
        SettingsAction(),
        MessageAction(),
        ExportAction(),
    )
}


def get_action(key: str) -> Action:
    action = ACTIONS.get(key)
    if action is None:
        raise _bad(_("Choose one of the bulk actions."))
    return action


def org_permitted(action: Action, user: Any, organisation: Organisation) -> bool:
    return action.org_permission is None or has_perm(user, organisation, action.org_permission)
