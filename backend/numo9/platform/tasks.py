"""Background jobs of the platform console (discovered by Celery): the nightly metrics snapshot
(U-06-T05)."""

from __future__ import annotations

from .metrics import snapshot_metrics_job

__all__ = ["snapshot_metrics_job"]
