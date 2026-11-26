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
    contact: Any = None,
) -> Any:
    """Create or replace the account's opening balance in the session (C-05-T02); validated —
    one side only, positive, the session still a draft. ``contact``: for an account that
    requires one (C-05-T09)."""
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
        line.contact = contact
        line.full_clean(exclude=["organisation", "session", "account", "contact"])
        line.save()
        return line


def remove_line(session: ConversionSession, account: Any) -> bool:
    """Remove the account's opening balance from a draft session (soft delete); returns whether
    there was one."""
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext as _

    from .models import ConversionLine

    with org_context(session.organisation), transaction.atomic():
        if session.is_finalised:
            raise ValidationError(
                _("The conversion is finalised: correct it with a correcting opening journal."),
                code="conversion.session.finalised",
            )
        line = ConversionLine.objects.filter(
            session=session, account=account, deleted_at__isnull=True
        ).first()
        if line is None:
            return False
        line.soft_delete()
        return True


def update_session(session: ConversionSession, **changes: Any) -> ConversionSession:
    """Change a session's conversion date (draft only), its "lock balances" choice and the
    wizard's saved progress (``step``, ``completed_steps``: known steps only, in order)."""
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext as _

    from .models import ConversionStep

    with org_context(session.organisation), transaction.atomic():
        locked = ConversionSession._base_manager.select_for_update().get(pk=session.pk)
        if "conversion_date" in changes and changes["conversion_date"] != locked.conversion_date:
            if locked.is_finalised:
                raise ValidationError(
                    _("The conversion is finalised: its date doesn't change."),
                    code="conversion.session.finalised",
                )
            locked.conversion_date = changes["conversion_date"]
        if "lock_balances" in changes and not locked.is_finalised:
            locked.lock_balances = bool(changes["lock_balances"])
        if "step" in changes:
            if changes["step"] not in ConversionStep.values:
                raise ValidationError(
                    {"step": ValidationError(_("Unknown step."), code="conversion.step")}
                )
            locked.step = changes["step"]
        if "completed_steps" in changes:
            done = set(changes["completed_steps"] or [])
            if not done <= set(ConversionStep.values):
                raise ValidationError(
                    {"completed_steps": ValidationError(_("Unknown step."), code="conversion.step")}
                )
            locked.completed_steps = [s for s in ConversionStep.values if s in done]
        locked.save()
        return locked
