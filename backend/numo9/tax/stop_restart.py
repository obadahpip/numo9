"""Stop and restart filing (G-03b-T03, T07): a registration ends at a date and starts again later
without corrupting history.

``stop(registration, date, reason_code, …, user)`` — ``date`` is the **last day registered**:

- it may not be before the registration starts nor before the end of the last filed or paid
  period (``tax.filing.stop_before_filed``), and the registration must not already be stopped;
- the open period crossing ``date`` is cut to end on it (a stub — the **final return**), the
  unfiled periods after it are deleted (custom ones too), and none is generated after it until a
  restart (the stop date is the generator's horizon, G-03b-T04);
- the registration's ``effective_to`` becomes ``date`` and its status **Closed**; a
  ``RegistrationStatusEvent`` (stop, reason, person) and the audit event
  ``tax.filing.stopped`` are recorded.

``restart(registration, date, frequency, …, user)`` — ``date`` (the first day registered again)
must be **after** the stop date: a ``FilingCycle`` of ``frequency`` starts on it, the
registration is **Active** and open-ended again, and its periods are generated from ``date``
(a stub up to the next regular boundary when ``date`` is mid-period); the days between stop and
restart stay a gap with no period ("Not registered", ``filing_service.gaps``). Event (restart,
frequency, person) and ``tax.filing.restarted``.

Both always name a person: without one they are refused (gap-44, never "System Generated").
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .filing import MONTHS, ONE_DAY
from .filing_service import diff, period_rows, regenerate
from .models import (
    LOCKED_PERIOD_STATUSES,
    FilingCycle,
    FilingPeriod,
    RegistrationAction,
    RegistrationStatusEvent,
    StopReason,
    TaxError,
)


def _person(user: Any) -> Any:
    if not getattr(user, "is_authenticated", False):
        raise TaxError(
            _("A person must make this change: it is recorded with their name."),
            code="tax.filing.no_actor",
        )
    return user


def is_stopped(registration: Any) -> bool:
    return registration.effective_to is not None and (
        RegistrationStatusEvent.objects.filter(registration=registration)
        .order_by("-date", "-created_at", "-pk")
        .values_list("action", flat=True)
        .first()
        == RegistrationAction.STOP
    )


def last_filed_end(registration: Any) -> dt.date | None:
    period = (
        FilingPeriod.objects.filter(registration=registration, status__in=LOCKED_PERIOD_STATUSES)
        .order_by("-end")
        .first()
    )
    return period.end if period is not None else None


def validate_stop(registration: Any, date: dt.date, reason_code: str) -> None:
    if not registration.files_returns:
        raise TaxError(
            _("Only GST/HST and QST registrations file returns."), code="tax.filing.type"
        )
    if reason_code not in StopReason.values:
        raise TaxError(_("Choose why filing stops."), code="tax.filing.stop_reason")
    if is_stopped(registration):
        raise TaxError(
            _("Filing is already stopped (last day %(day)s): restart it first.")
            % {"day": registration.effective_to.isoformat()},
            code="tax.filing.already_stopped",
        )
    start = registration.start_date
    if start is None or date < start:
        raise TaxError(
            _("The last day registered can't be before the registration starts."),
            code="tax.filing.stop_before_start",
        )
    filed = last_filed_end(registration)
    if filed is not None and date < filed:
        raise TaxError(
            _(
                "The period up to %(end)s is already filed: the last day registered can't be "
                "before it."
            )
            % {"end": filed.isoformat()},
            code="tax.filing.stop_before_filed",
        )


def validate_restart(registration: Any, date: dt.date, frequency: str) -> None:
    if frequency not in MONTHS:
        raise TaxError(_("Choose monthly, quarterly or annual."), code="tax.filing.frequency")
    if not is_stopped(registration):
        raise TaxError(_("Filing isn't stopped."), code="tax.filing.not_stopped")
    if date <= registration.effective_to:
        raise TaxError(
            _("Registered again from must be after the last day registered (%(day)s).")
            % {"day": registration.effective_to.isoformat()},
            code="tax.filing.restart_before_stop",
        )


def stop(
    registration: Any,
    date: dt.date,
    reason_code: str,
    reason_text: str = "",
    *,
    user: Any,
    today: dt.date | None = None,
) -> dict[str, Any]:
    """Stop filing after ``date`` (module docstring) → the diff and the periods."""
    from numo9.audit.service import record
    from numo9.orgsettings.models import RegistrationStatus, TaxRegistration
    from numo9.tenancy.context import org_context

    person = _person(user)
    with org_context(registration.organisation), transaction.atomic():
        registration = TaxRegistration.objects.select_for_update().get(pk=registration.pk)
        validate_stop(registration, date, reason_code)
        before = period_rows(registration)
        previous = registration.status
        registration.effective_to = date
        registration.status = RegistrationStatus.CLOSED
        registration.save()
        RegistrationStatusEvent(
            organisation=registration.organisation,
            registration=registration,
            action=RegistrationAction.STOP,
            date=date,
            reason_code=reason_code,
            reason_text=(reason_text or "").strip(),
            user=person,
        ).save()
        regenerate(registration, date + ONE_DAY, today=today)
        record(
            "tax.filing.stopped",
            obj=registration,
            actor=person,
            changes={"status": [previous, registration.status], "effective_to": [None, str(date)]},
            meta={"date": date.isoformat(), "reason": reason_code, "note": reason_text or ""},
        )
        after = period_rows(registration)
        return {**diff(before, after), "periods": after, "warnings": []}


def restart(
    registration: Any,
    date: dt.date,
    frequency: str,
    reason_text: str = "",
    *,
    user: Any,
    today: dt.date | None = None,
) -> dict[str, Any]:
    """Restart filing from ``date`` with ``frequency`` (module docstring)."""
    from numo9.audit.service import record
    from numo9.orgsettings.models import RegistrationStatus, TaxRegistration
    from numo9.tenancy.context import org_context

    person = _person(user)
    with org_context(registration.organisation), transaction.atomic():
        registration = TaxRegistration.objects.select_for_update().get(pk=registration.pk)
        validate_restart(registration, date, frequency)
        before = period_rows(registration)
        stopped = registration.effective_to
        registration.effective_to = None
        registration.status = RegistrationStatus.ACTIVE
        registration.save()
        FilingCycle.objects.update_or_create(
            registration=registration,
            effective_from=date,
            defaults={
                "organisation": registration.organisation,
                "frequency": frequency,
                "note": (reason_text or "").strip(),
                "created_by": person,
            },
        )
        RegistrationStatusEvent(
            organisation=registration.organisation,
            registration=registration,
            action=RegistrationAction.RESTART,
            date=date,
            frequency=frequency,
            reason_text=(reason_text or "").strip(),
            user=person,
        ).save()
        regenerate(registration, date, today=today or timezone.localdate())
        record(
            "tax.filing.restarted",
            obj=registration,
            actor=person,
            changes={"status": [RegistrationStatus.CLOSED, registration.status]},
            meta={
                "date": date.isoformat(),
                "frequency": frequency,
                "stopped": stopped.isoformat() if stopped else "",
                "note": reason_text or "",
            },
        )
        after = period_rows(registration)
        return {**diff(before, after), "periods": after, "warnings": []}
