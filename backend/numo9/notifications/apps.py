from typing import Any

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Notifications (A-07): in-app notification centre; email sending and domains follow."""

    name = "numo9.notifications"
    label = "notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:
        # Tenant sweep (A-01-T09): a notification needs a recipient.
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["notifications.Notification"] = _sweep_notification
        SWEEP_FACTORIES["notifications.SendingDomain"] = _sweep_domain


def _sweep_notification(organisation: Any) -> Any:
    import uuid

    from numo9.accounts.models import User

    from .models import Notification

    recipient = User.objects.create_user(f"sweep-{uuid.uuid4().hex}@example.invalid", name="Sweep")
    notification = Notification(
        organisation=organisation,
        recipient=recipient,
        category="system",
        title_key="notifications.test",
    )
    notification.save()
    return notification


def _sweep_domain(organisation: Any) -> Any:
    import uuid

    from .models import SendingDomain

    domain = SendingDomain(
        organisation=organisation, domain=f"sweep-{uuid.uuid4().hex[:12]}.ca", provider="local"
    )
    domain.save()
    return domain
