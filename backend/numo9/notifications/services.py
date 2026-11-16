"""Notification services (A-07-T01 reading and marking, A-07-T02 sending).

Reading and marking are for **one person in the active organisation**: the scoped manager limits
to the organisation, ``recipient`` to the person; soft-deleted notifications never show.

Sending — ``notify(event, recipients, channels=None, params=None, link="", organisation=None)``:

1. ``event`` is a registered event key (``events.register_event``; unknown → ``UnknownEvent``);
2. for each recipient (duplicates and people without an account skipped), the channels are the
   event's channels ∩ ``channels`` (when given) ∩ what the person allows for the event's category
   in this organisation (``preferences_for``) — a *mandatory* event or a *locked* category skips
   the preference step;
3. each channel delivers (``channels.get_channel(name).deliver``); a channel nobody registered
   (SMS before a provider exists) is skipped, never an error.

Returns a ``Sent`` list of ``(recipient, channel, result)`` so callers and tests see exactly what
went where. Runs in the organisation's tenant context (the active one, or ``organisation``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from numo9.tenancy.context import current_org, org_context
from numo9.tenancy.models import Organisation

from .channels import Delivery, get_channel
from .events import DEFAULTS, EMAIL, IN_APP, CategoryDefault, get_event
from .models import Notification, NotificationCategory, NotificationPreference


def my_notifications(user: Any) -> QuerySet[Notification]:
    return Notification.objects.filter(recipient=user, deleted_at__isnull=True)


def unread_count(user: Any) -> int:
    return my_notifications(user).filter(read_at__isnull=True).count()


def mark_read(notification: Notification) -> Notification:
    """Mark one notification read; reading it again keeps the first time."""
    if notification.read_at is None:
        notification.read_at = timezone.now()
        Notification.objects.filter(pk=notification.pk, read_at__isnull=True).update(
            read_at=notification.read_at
        )
    return notification


def mark_all_read(user: Any, category: str | None = None) -> int:
    """Mark every unread notification (of ``category``) read; returns how many changed."""
    unread = my_notifications(user).filter(read_at__isnull=True)
    if category:
        unread = unread.filter(category=category)
    return unread.update(read_at=timezone.now())


# ---- preferences (A-07-T02) ----------------------------------------------------------------


@dataclass(frozen=True)
class CategoryPreference:
    category: str
    in_app: bool
    email: bool
    locked: bool
    is_default: bool

    def allows(self, channel: str) -> bool:
        if channel == IN_APP:
            return self.in_app
        if channel == EMAIL:
            return self.email
        return True  # channels without a per-category switch (SMS/WhatsApp, A-07-T12) opt in


def preferences_for(user: Any) -> dict[str, CategoryPreference]:
    """Every category's effective choice for ``user`` in the active organisation."""
    rows = {
        row.category: row
        for row in NotificationPreference.objects.filter(user=user, deleted_at__isnull=True)
    }
    result: dict[str, CategoryPreference] = {}
    for category in NotificationCategory.values:
        default = DEFAULTS.get(category, CategoryDefault())
        row = rows.get(category)
        if default.locked or row is None:
            result[category] = CategoryPreference(
                category, default.in_app, default.email, default.locked, True
            )
        else:
            result[category] = CategoryPreference(category, row.in_app, row.email, False, False)
    return result


class LockedCategory(ValueError):
    """Security notifications cannot be turned off."""


def set_preference(
    user: Any, category: str, *, in_app: bool | None = None, email: bool | None = None
) -> CategoryPreference:
    """Change one category for ``user`` in the active organisation (a locked one: refused)."""
    if category not in NotificationCategory.values:
        raise ValueError(f"Unknown notification category {category!r}")
    if DEFAULTS.get(category, CategoryDefault()).locked:
        raise LockedCategory(category)
    organisation = current_org()
    current = preferences_for(user)[category]
    row, _ = NotificationPreference.objects.get_or_create(
        user=user,
        category=category,
        deleted_at__isnull=True,
        defaults={"organisation": organisation, "in_app": current.in_app, "email": current.email},
    )
    if in_app is not None:
        row.in_app = in_app
    if email is not None:
        row.email = email
    row.save()
    return preferences_for(user)[category]


# ---- sending (A-07-T02) --------------------------------------------------------------------


@dataclass
class Sent:
    deliveries: list[tuple[Any, str, Any]] = field(default_factory=list)

    def to(self, recipient: Any) -> list[str]:
        return [channel for who, channel, _ in self.deliveries if who.pk == recipient.pk]

    def __len__(self) -> int:
        return len(self.deliveries)


def channels_for(user: Any, event_key: str, requested: Iterable[str] | None = None) -> list[str]:
    """The channels ``event_key`` reaches ``user`` on, in the active organisation."""
    event = get_event(event_key)
    channels = [c for c in event.channels if requested is None or c in set(requested)]
    if event.mandatory:
        return channels
    preference = preferences_for(user)[event.category]
    return [c for c in channels if preference.allows(c)]


def _unique(recipients: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    people = []
    for person in recipients:
        if person is None or person.pk is None or person.pk in seen:
            continue
        seen.add(person.pk)
        people.append(person)
    return people


def notify(
    event: str,
    recipients: Iterable[Any],
    channels: Iterable[str] | None = None,
    *,
    params: dict[str, Any] | None = None,
    link: str = "",
    organisation: Organisation | None = None,
) -> Sent:
    """Tell ``recipients`` about ``event`` on the channels their preferences allow."""
    definition = get_event(event)
    organisation = organisation or current_org()
    if organisation is None:
        raise ValueError("notify() needs an organisation (active context or organisation=)")
    requested = list(channels) if channels is not None else None
    sent = Sent()
    with org_context(organisation):
        for person in _unique(recipients):
            for name in channels_for(person, event, requested):
                channel = get_channel(name)
                if channel is None:
                    continue
                delivery = Delivery(definition, person, organisation, dict(params or {}), link)
                sent.deliveries.append((person, name, channel.deliver(delivery)))
    return sent
