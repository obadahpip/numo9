"""Notification events and category defaults (A-07-T02).

An **event** is something that happened that people are told about — ``notify()`` is always
called with an event key, never with free text:

    register_event("jobs.finished", NotificationCategory.JOBS,
                   title_key="notifications.job.finished")

- ``category`` decides whose preferences apply (``NotificationPreference``) and the defaults
  below when someone has not chosen;
- ``title_key`` is the message of the catalogue (``texts``) — the same key is stored on the
  in-app notification and renders the email subject and text;
- ``channels`` the event goes to by default (``notify(channels=…)`` may narrow them);
- ``mandatory`` events ignore preferences (a new sign-in on the account, a payment that failed):
  people cannot turn off what they must know.

**Defaults per category** (a person who never opened the preferences page): every category in the
app; by email only what needs attention outside the app — security, approvals, billing and the
account itself. Security is *locked*: both channels, always (the preferences page shows it
greyed out).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import NotificationCategory, NotificationChannel

C = NotificationCategory
IN_APP = NotificationChannel.IN_APP.value
EMAIL = NotificationChannel.EMAIL.value


@dataclass(frozen=True)
class CategoryDefault:
    in_app: bool = True
    email: bool = False
    locked: bool = False  # preferences cannot change it


DEFAULTS: dict[str, CategoryDefault] = {
    C.SYSTEM: CategoryDefault(in_app=True, email=True),
    C.SECURITY: CategoryDefault(in_app=True, email=True, locked=True),
    C.JOBS: CategoryDefault(in_app=True, email=False),
    C.DOCUMENTS: CategoryDefault(in_app=True, email=False),
    C.APPROVALS: CategoryDefault(in_app=True, email=True),
    C.REMINDERS: CategoryDefault(in_app=True, email=False),
    C.BILLING: CategoryDefault(in_app=True, email=True),
}


class UnknownEvent(LookupError):
    """``notify()`` was called with an event key nobody registered."""


@dataclass(frozen=True)
class NotificationEvent:
    key: str
    category: str
    title_key: str
    channels: tuple[str, ...] = (IN_APP, EMAIL)
    mandatory: bool = False
    extra: dict[str, str] = field(default_factory=dict)


_events: dict[str, NotificationEvent] = {}


def register_event(
    key: str,
    category: str,
    *,
    title_key: str,
    channels: tuple[str, ...] = (IN_APP, EMAIL),
    mandatory: bool = False,
) -> NotificationEvent:
    if category not in NotificationCategory.values:
        raise ValueError(f"Unknown notification category {category!r}")
    event = NotificationEvent(key, category, title_key, tuple(channels), mandatory)
    _events[key] = event
    return event


def get_event(key: str) -> NotificationEvent:
    try:
        return _events[key]
    except KeyError:
        raise UnknownEvent(key) from None


def all_events() -> list[NotificationEvent]:
    return sorted(_events.values(), key=lambda e: e.key)


# ---- events of Phase 0 modules (messages in texts.py) ------------------------------------------

register_event("jobs.finished", C.JOBS, title_key="notifications.job.finished")
register_event("jobs.failed", C.JOBS, title_key="notifications.job.failed")
register_event("documents.quarantined", C.DOCUMENTS, title_key="notifications.document.quarantined")
# System messages (A-07-T11): sign-in alerts and payment problems can't be turned off.
register_event(
    "security.new_device", C.SECURITY, title_key="notifications.security.new_device", mandatory=True
)
register_event(
    "billing.payment_failed",
    C.BILLING,
    title_key="notifications.billing.payment_failed",
    mandatory=True,
)
register_event(
    "billing.read_only", C.BILLING, title_key="notifications.billing.read_only", mandatory=True
)
register_event("trial.ending", C.BILLING, title_key="notifications.trial.ending")
# Lock dates (A-05-T13, flow F6): the organisation's admins are told when a lock moves.
register_event("settings.lock_changed", C.SYSTEM, title_key="notifications.settings.lock_changed")

# ---- credit limits (B-01-T13) ------------------------------------------------------------------
register_event(
    "contacts.credit_override_requested",
    C.APPROVALS,
    title_key="notifications.contacts.credit_override_requested",
)
register_event(
    "contacts.credit_override_approved",
    C.APPROVALS,
    title_key="notifications.contacts.credit_override_approved",
)
register_event(
    "contacts.credit_override_rejected",
    C.APPROVALS,
    title_key="notifications.contacts.credit_override_rejected",
)
