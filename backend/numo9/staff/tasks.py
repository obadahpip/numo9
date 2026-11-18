"""Celery tasks of the staff app (discovered by Celery): the daily dormant-staff alerts
(V-05-T06) and the activity aggregation (V-05-T07)."""

from __future__ import annotations

from .activity import aggregate_activity_job
from .dormant import dormant_alerts_job

__all__ = ["aggregate_activity_job", "dormant_alerts_job"]
