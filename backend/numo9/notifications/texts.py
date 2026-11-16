"""The notification message catalogue (A-07-T01): message key → title and body.

A notification stores ``title_key`` and ``body_params``; the text is rendered at read time in the
reader's language (``render``), so a French-speaking member reads French even when the event
happened in an English session. Messages use named ``%(param)s`` placeholders; a missing
parameter renders as an empty string rather than failing. A key not in the catalogue renders as a
generic "Notification" (a message removed in a later release must not break old notifications).

Apps register their messages with ``register_text`` at import time of their ``notifications``
module (or in ``AppConfig.ready``). A-07-T11 seeds the system catalogue (verification, invite,
trial reminders, dunning, new device).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.utils import translation
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class NotificationText:
    title: Promise | str
    body: Promise | str = ""


_texts: dict[str, NotificationText] = {}


def register_text(key: str, title: Promise | str, body: Promise | str = "") -> NotificationText:
    text = NotificationText(title, body)
    _texts[key] = text
    return text


def is_registered(key: str) -> bool:
    return key in _texts


def _fill(template: Promise | str, params: dict[str, Any]) -> str:
    text = str(template)
    if not text:
        return ""
    return text % defaultdict(str, params)


def render(key: str, params: dict[str, Any] | None, language: str | None = None) -> tuple[str, str]:
    """(title, body) of a notification in ``language`` (the active language when None)."""
    text = _texts.get(key) or NotificationText(_("Notification"))
    with translation.override(language or translation.get_language()):
        return _fill(text.title, params or {}), _fill(text.body, params or {})


# ---- messages of Phase 0 modules -------------------------------------------------------------

register_text(
    "notifications.job.finished",
    _("%(job)s finished"),
    _("%(summary)s"),
)
register_text(
    "notifications.job.failed",
    _("%(job)s didn't finish"),
    _("%(error)s Open the job tray to try again."),
)
register_text(
    "notifications.document.quarantined",
    _("%(file)s was blocked"),
    _("The virus scan found a threat: the file can't be opened. Ask the sender for a clean copy."),
)
