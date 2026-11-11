"""Numo9 backend. Loading the Celery app here makes ``@shared_task`` use it (A-08-T01)."""

from .celery import app as celery_app

__all__ = ("celery_app",)
