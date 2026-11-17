"""Preview of a bulk action (V-03-T04): every change computed, **nothing written**.

``selected_organisations(user, practice, selection)`` turns the selection into organisations:

- ``{"ids": [organisation ids]}`` — the rows the person ticked (order kept, duplicates dropped);
- ``{"query": {"q": "...", "status": [...], "group": [...], ...}}`` — *select all matching*: the
  directory's own query (``DirectoryQuery``, the same search and filters as the grid) evaluated
  on the server, never a list of ids sent by the browser.

An id the user can't see in the practice's directory stays in the selection and is reported as
``skipped: no_access`` (never silently dropped). At most ``MAX_SELECTION`` organisations.

``preview(user, practice, action, params, selection)`` answers one line per organisation —
``change`` (before → after), ``no_change`` or ``skipped`` (reason) — plus the counts; the API shows
the first 50 lines and the total.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.http import QueryDict
from django.utils.translation import gettext as _

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.models import Organisation, Practice
from numo9.workspace.search import directory_scope

from .actions import Change, Context, Skip, get_action, org_permitted

MAX_SELECTION = 5000
PREVIEW_LINES = 50


def reason_text(reason: str) -> str:
    texts = {
        "no_access": _("You don't have access to this organisation."),
        "no_permission": _("Your role in this organisation can't make this change."),
        "not_served": _("The practice no longer serves this organisation."),
        "fye_has_posted": _(
            "It has posted transactions: change its fiscal year end in its own settings."
        ),
        "no_recipients": _("It has no owner or admin to send the message to."),
        "cancelled": _("The bulk action was cancelled before this organisation."),
        "error": _("Something went wrong with this organisation. Nothing was changed."),
    }
    return str(texts.get(reason, reason))


def _query_dict(query: dict[str, Any]) -> QueryDict:
    data = QueryDict(mutable=True)
    for key, value in query.items():
        for item in value if isinstance(value, list) else [value]:
            data.appendlist(str(key), str(item))
    data["page"] = "1"
    return data


def selected_organisations(
    user: Any, practice: Practice, selection: Any
) -> tuple[list[Organisation], set[int]]:
    """The selected organisations (in order) and the ids among them the user may work on."""
    from numo9.workspace.api import parse_directory_params
    from numo9.workspace.search import DirectoryQuery

    if not isinstance(selection, dict):
        raise api_error(errors.BULK_EMPTY_SELECTION)
    visible = set(directory_scope(user, practice).values_list("organisation_id", flat=True))
    if "query" in selection:
        params, _columns, _facets = parse_directory_params(_query_dict(selection["query"] or {}))
        rows = DirectoryQuery(user, practice, params).results()
        orgs = [row.organisation for row in rows[: MAX_SELECTION + 1]]
    else:
        ids = selection.get("ids")
        if not isinstance(ids, list):
            raise api_error(errors.BULK_EMPTY_SELECTION)
        wanted = list(dict.fromkeys(str(value) for value in ids))
        if len(wanted) > MAX_SELECTION:
            raise api_error(errors.BULK_TOO_MANY, limit=MAX_SELECTION)
        import uuid

        valid = []
        for value in wanted:
            try:
                valid.append(uuid.UUID(value))
            except ValueError:
                continue
        by_id = {org.public_id: org for org in Organisation.objects.filter(public_id__in=valid)}
        orgs = [by_id[key] for key in valid if key in by_id]
    if not orgs:
        raise api_error(errors.BULK_EMPTY_SELECTION)
    if len(orgs) > MAX_SELECTION:
        raise api_error(errors.BULK_TOO_MANY, limit=MAX_SELECTION)
    return orgs, {org.pk for org in orgs if org.pk in visible}


@dataclass
class PreviewLine:
    organisation: Organisation
    status: str  # change | no_change | skipped
    reason: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "organisation": {"id": self.organisation.public_id, "name": self.organisation.name},
            "status": self.status,
            "reason": self.reason,
            "message": reason_text(self.reason) if self.reason else "",
            "before": self.before,
            "after": self.after,
        }


def evaluate(action: Any, ctx: Context, allowed: bool, write: bool = False) -> PreviewLine:
    if not allowed:
        return PreviewLine(ctx.organisation, "skipped", "no_access")
    if not org_permitted(action, ctx.user, ctx.organisation):
        return PreviewLine(ctx.organisation, "skipped", "no_permission")
    result: Change | Skip = action.apply(ctx) if write else action.diff(ctx)
    if isinstance(result, Skip):
        return PreviewLine(ctx.organisation, "skipped", result.reason)
    status = "change" if result.changed or action.key in ("message", "export") else "no_change"
    return PreviewLine(ctx.organisation, status, "", result.before, result.after)


def preview(
    user: Any, practice: Practice, action_key: str, params: dict[str, Any], selection: Any
) -> dict[str, Any]:
    action = get_action(action_key)
    orgs, allowed = selected_organisations(user, practice, selection)
    lines = [
        evaluate(action, Context(org, practice, user, params), org.pk in allowed) for org in orgs
    ]
    counts = {"change": 0, "no_change": 0, "skipped": 0}
    for line in lines:
        counts[line.status] += 1
    return {
        "total": len(lines),
        "counts": counts,
        "lines": [line.as_dict() for line in lines[:PREVIEW_LINES]],
    }
