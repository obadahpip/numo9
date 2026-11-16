"""Reading and marking a person's notifications (A-07-T01).

Everything is for **one person in the active organisation**: the scoped manager limits to the
organisation, ``recipient`` to the person; soft-deleted notifications never show.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from .models import Notification


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
