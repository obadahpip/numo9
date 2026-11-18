"""Celery tasks of the staff app (discovered by Celery): the daily dormant-staff alerts
(V-05-T06)."""

from __future__ import annotations

from .dormant import dormant_alerts_job

__all__ = ["dormant_alerts_job"]
