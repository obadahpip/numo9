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

# ---- system messages (A-07-T11): in-app side of the system email catalogue --------------------

register_text(
    "notifications.security.new_device",
    _("New sign-in on %(device)s"),
    _(
        "Your account was signed in on %(when)s from %(device)s (%(ip)s). Not you? Change your "
        "password and sign out the other sessions."
    ),
)
register_text(
    "notifications.billing.payment_failed",
    _("Payment for %(organisation)s didn't go through"),
    _("Update the payment method by %(grace_until)s to keep working without a break."),
)
register_text(
    "notifications.billing.read_only",
    _("%(organisation)s is read-only"),
    _(
        "The subscription payment is overdue. Everyone can still see and export; update the "
        "payment method to make changes again."
    ),
)
register_text(
    "notifications.billing.receipt",
    _("Receipt: %(amount)s paid for %(organisation)s"),
    _("Numo9 invoice %(number)s is paid. Thank you. The invoice is on the Subscription page."),
)
register_text(
    "notifications.trial.ending",
    _("Your trial ends on %(ends_on)s"),
    _("Choose a package to keep working without a break. Everything you entered stays."),
)

# ---- settings (A-05-T13, flow F6) -------------------------------------------------------------

register_text(
    "notifications.settings.lock_changed",
    _("%(module)s lock date changed"),
    _("%(person)s set the %(level)s lock to %(date)s."),
)

# ---- credit limits (B-01-T13) ------------------------------------------------------------------

register_text(
    "notifications.contacts.credit_override_requested",
    _("Credit limit override requested for %(contact)s"),
    _("%(person)s asks to go %(over)s over the credit limit of %(limit)s: %(reason)s"),
)
register_text(
    "notifications.contacts.credit_override_approved",
    _("Credit limit override approved for %(contact)s"),
    _("%(person)s approved going %(over)s over the credit limit. %(note)s"),
)
register_text(
    "notifications.contacts.credit_override_rejected",
    _("Credit limit override declined for %(contact)s"),
    _("%(person)s declined going %(over)s over the credit limit. %(note)s"),
)

# ---- practice messages (V-03-T06) --------------------------------------------------------------

register_text(
    "notifications.practice.message",
    _("%(practice)s: %(subject)s"),
    _("%(body)s"),
)

# ---- quotes (D-02-T15) -------------------------------------------------------------------------

register_text(
    "notifications.sales.quote.accepted",
    _("Quote %(number)s accepted"),
    _("%(customer)s accepted quote %(number)s (%(total)s)."),
)
register_text(
    "notifications.sales.quote.declined",
    _("Quote %(number)s declined"),
    _("%(customer)s declined quote %(number)s: %(reason)s"),
)

# ---- recurring invoices (D-04-T05) ------------------------------------------------------------

register_text(
    "notifications.sales.recurring.failed",
    _("Recurring invoice %(name)s needs attention"),
    _("The invoice of %(date)s was created but not finished: %(reason)s"),
)

# ---- filing periods (G-03a-T17) ---------------------------------------------------------------

register_text(
    "notifications.tax.filing.due_soon",
    _("%(registration)s return due %(due_date)s"),
    _("The return for %(period)s is due on %(due_date)s."),
)
register_text(
    "notifications.tax.filing.overdue",
    _("%(registration)s return overdue"),
    _("The return for %(period)s was due on %(due_date)s and isn't filed."),
)
