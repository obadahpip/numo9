"""Celery tasks of the notifications app (discovered by ``app.autodiscover_tasks()``)."""

from .dnscheck import check_sending_domains
from .mail import send_email

__all__ = ["check_sending_domains", "send_email"]
