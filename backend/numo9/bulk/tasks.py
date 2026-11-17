"""Celery tasks of the bulk app (discovered by Celery): the executor (V-03-T05)."""

from __future__ import annotations

from .service import run_bulk_job

__all__ = ["run_bulk_job"]
