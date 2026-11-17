"""Background jobs of the entitlements app (discovered by Celery): the free trial's reminder and
expiry jobs (U-05-T07, T08)."""

from __future__ import annotations

from .trials import trial_reminders_job

__all__ = ["trial_reminders_job"]
