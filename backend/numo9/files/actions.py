""" "Create from file" actions (A-06-T11): what a document can become.

Modules register the records they can make from a document — a bill (E-02), an expense claim
(E-04), a fixed asset (I-01) — and the inbox shows every registered action on a document: the
ones that work as buttons, the others greyed **with the reason** ("Bills arrive with Purchases in
Phase 1"), never hidden or silently disabled (Phase 0 UX principle: honest gating).

    register_file_action(FileAction(
        key="bill", label=_("Create a bill"), module="purchases", deliverable="E-02",
        feature="accounting.bills.write", url="/o/{org}/purchases/bills/new?document={document}",
        available=True,
    ))

``actions_for(document)`` answers for one document: an action is available when its module says
so (``available``), the document is clean (scanned, not quarantined) and its type is one the
action reads (``mimes``; empty = any type).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from .models import Document, DocumentStatus

READABLE = frozenset(
    {"application/pdf", "image/png", "image/jpeg", "image/tiff", "image/heic", "image/heif"}
)


@dataclass(frozen=True)
class FileAction:
    key: str
    label: Promise | str
    module: str
    deliverable: str
    #: True when the module is built; a callable decides per document (e.g. a feature check).
    available: bool | Callable[[Document], bool] = False
    #: Why it isn't available yet (shown next to the greyed action).
    unavailable_reason: Promise | str = ""
    #: Where the action goes, with ``{org}`` and ``{document}`` filled in.
    url: str = ""
    mimes: frozenset[str] = field(default_factory=frozenset)


_actions: dict[str, FileAction] = {}


def register_file_action(action: FileAction) -> FileAction:
    _actions[action.key] = action
    return action


def unregister_file_action(key: str) -> None:
    _actions.pop(key, None)


def registered() -> list[FileAction]:
    return list(_actions.values())


def actions_for(document: Document) -> list[dict[str, Any]]:
    out = []
    for action in _actions.values():
        reason = ""
        ready = action.available(document) if callable(action.available) else action.available
        if not ready:
            reason = str(action.unavailable_reason)
        elif document.status != DocumentStatus.CLEAN:
            ready, reason = False, str(_("Wait until the file has been checked for viruses."))
        elif action.mimes and document.mime not in action.mimes:
            ready, reason = False, str(_("This action reads PDF files and images only."))
        out.append(
            {
                "key": action.key,
                "label": str(action.label),
                "module": action.module,
                "available": ready,
                "reason": reason,
                "url": (
                    action.url.format(
                        org=document.organisation.public_id, document=document.public_id
                    )
                    if ready and action.url
                    else ""
                ),
            }
        )
    return out


# ---- Phase 0: the actions planned for Phases 1 and 2, greyed with their reason --------------

register_file_action(
    FileAction(
        key="bill",
        label=_("Create a bill"),
        module="purchases",
        deliverable="E-02",
        unavailable_reason=_("Bills arrive with Purchases in Phase 1."),
        mimes=READABLE,
    )
)
register_file_action(
    FileAction(
        key="expense",
        label=_("Create an expense claim"),
        module="purchases",
        deliverable="E-04",
        unavailable_reason=_("Expense claims arrive with Purchases in Phase 1."),
        mimes=READABLE,
    )
)
register_file_action(
    FileAction(
        key="asset",
        label=_("Create a fixed asset"),
        module="accounting",
        deliverable="I-01",
        unavailable_reason=_("The fixed asset register arrives in Phase 2."),
        mimes=READABLE,
    )
)
