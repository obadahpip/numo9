"""Conversion services (C-05)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction

from numo9.tenancy.context import org_context

from .models import ConversionSession


def current_session(organisation: Any) -> ConversionSession | None:
    with org_context(organisation):
        found: ConversionSession | None = ConversionSession.objects.filter(
            deleted_at__isnull=True
        ).first()
        return found


def start_conversion(
    organisation: Any, conversion_date: dt.date, *, user: Any
) -> ConversionSession:
    """The organisation's conversion session at ``conversion_date`` — refused
    (``conversion.session.exists``) when it has one already (C-05-T01)."""
    with org_context(organisation), transaction.atomic():
        session = ConversionSession(
            organisation=organisation,
            conversion_date=conversion_date,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        session.full_clean()
        session.save()
        return session
