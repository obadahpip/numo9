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


def set_line(
    session: ConversionSession,
    account: Any,
    *,
    debit: Any = 0,
    credit: Any = 0,
    description: str = "",
) -> Any:
    """Create or replace the account's opening balance in the session (C-05-T02); validated —
    one side only, positive, the session still a draft."""
    from decimal import Decimal

    from .models import ConversionLine

    with org_context(session.organisation), transaction.atomic():
        line = ConversionLine.objects.filter(
            session=session, account=account, deleted_at__isnull=True
        ).first() or ConversionLine(
            organisation=session.organisation, session=session, account=account
        )
        line.debit = Decimal(str(debit or 0))
        line.credit = Decimal(str(credit or 0))
        line.description = description
        line.full_clean(exclude=["organisation", "session", "account"])
        line.save()
        return line
