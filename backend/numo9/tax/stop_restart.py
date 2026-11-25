"""Stop and restart filing (G-03b-T03, T07): a registration ends at a date and starts again later
without corrupting history.

``stop(registration, date, reason_code, …, user)`` — ``date`` is the **last day registered**:

- it may not be before the registration starts, before the end of the last filed or paid
  period (``tax.filing.stop_before_filed``) nor before the last restart
  (``tax.filing.stop_before_restart``), and the registration must not already be stopped;
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
    restarted = (
        RegistrationStatusEvent.objects.filter(
            registration=registration, action=RegistrationAction.RESTART
        )
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    if restarted is not None and date < restarted:
        raise TaxError(
            _("Filing restarted on %(day)s: the last day registered can't be before it.")
            % {"day": restarted.isoformat()},
            code="tax.filing.stop_before_restart",
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


# ---- impact preview and the API's change runner (G-03b-T08, T09) --------------------------------


def apply(
    registration: Any, change: dict[str, Any], *, user: Any, today: dt.date | None = None
) -> dict[str, Any]:
    """Run ``{"action": "stop", "date", "reason_code", "reason_text"}`` or ``{"action":
    "restart", "date", "frequency", "reason_text"}`` → the diff, the periods, and the impact:
    ``documents`` dated while not registered with the registration's tax codes (G-03b-T05),
    ``out_of_scope_default`` (new sales default to out of scope after a GST/HST stop, G-03b-T06).
    """
    from .post_stop import post_stop_documents
    from .settings import tax_settings

    action = change.get("action")
    if action == "stop":
        result = stop(
            registration,
            change["date"],
            change.get("reason_code") or "",
            change.get("reason_text") or "",
            user=user,
            today=today,
        )
    elif action == "restart":
        result = restart(
            registration,
            change["date"],
            change.get("frequency") or "",
            change.get("reason_text") or "",
            user=user,
            today=today,
        )
    else:
        raise TaxError(_("Unknown change."), code="tax.filing.action")
    registration.refresh_from_db()
    stopped = is_stopped(registration)
    return {
        **result,
        "documents": post_stop_documents(registration),
        "out_of_scope_default": bool(
            stopped
            and registration.type == "rt"
            and tax_settings(registration.organisation).out_of_scope_after_stop
        ),
        "stopped": stopped,
    }


class _Undo(Exception):
    """Rolls a preview's transaction back."""


def preview(
    registration: Any, change: dict[str, Any], *, user: Any, today: dt.date | None = None
) -> dict[str, Any]:
    """``apply``'s result with nothing written: the change runs in a transaction rolled back,
    so the preview is exactly what saving gives (a refused change raises the same error)."""
    from numo9.orgsettings.models import TaxRegistration

    result: dict[str, Any] = {}
    try:
        with transaction.atomic():
            result = apply(registration, change, user=user, today=today)
            raise _Undo
    except _Undo:
        pass
    # the in-memory row was refreshed inside the rolled-back transaction
    fresh = TaxRegistration.objects.get(pk=registration.pk)
    registration.effective_to, registration.status = fresh.effective_to, fresh.status
    return result


def event_row(event: RegistrationStatusEvent) -> dict[str, Any]:
    return {
        "id": str(event.public_id),
        "action": event.action,
        "date": event.date.isoformat(),
        "reason_code": event.reason_code,
        "reason_label": event.get_reason_code_display() if event.reason_code else "",
        "reason_text": event.reason_text,
        "frequency": event.frequency,
        "by": {"id": str(event.user.public_id), "name": event.user.name or event.user.email},
        "at": event.created_at.isoformat(),
    }


def status_of(registration: Any) -> dict[str, Any]:
    """The registration's stop/restart history (G-03b-T09 ``events``): the events, the gaps,
    whether it is stopped now and its last day registered."""
    from .filing_service import gaps

    events = RegistrationStatusEvent.objects.filter(registration=registration).select_related(
        "user"
    )
    return {
        "events": [event_row(e) for e in events.order_by("date", "created_at", "pk")],
        "gaps": [
            {"start": start.isoformat(), "end": end.isoformat() if end else None}
            for start, end in gaps(registration)
        ],
        "stopped": is_stopped(registration),
        "stop_date": registration.effective_to.isoformat() if registration.effective_to else None,
        "last_filed_end": (filed.isoformat() if (filed := last_filed_end(registration)) else None),
    }
