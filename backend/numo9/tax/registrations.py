"""Registration service of the tax settings page (G-06-T04): the statutory registrations
(``orgsettings.TaxRegistration``) bound to the filing-cycle engine (G-03a).

- ``create_registration(organisation, type=, number=, effective_from=, frequency=, …)`` — saves
  the registration; a registration that **files returns** (GST/HST RT, QST) with an effective
  date gets its **first filing cycle and its periods** at once (``frequency``; annual when not
  given — the frequency the CRA assigns a new registrant, changed on the timeline).
- ``update_registration(registration, **fields)`` — number, dates, status, approval reference.
  Moving the **effective date** moves the first cycle with it and regenerates the periods;
  setting or moving the **end date** cuts the periods there. Both are refused when a filed
  period would change (``tax.registration.filed_periods``).
- ``remove_registration(registration)`` — soft-deletes it; refused while it has filed periods
  (stop it instead: the history must stay).
- ``summary(registration, today)`` — what the page shows on the card: the frequency in force,
  the number of periods, the next return due and how many are overdue.

Every change is audited (the registration is an audited model; cycle changes go through
``filing_service.apply_change``), so it appears in the tax history with its author.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.orgsettings.models import TaxRegistration

from . import filing_service
from .filing import ONE_DAY
from .models import LOCKED_PERIOD_STATUSES, FilingCycle, FilingPeriod, TaxError

#: The frequency of a new registration when none is chosen (CRA: annual for a new registrant).
DEFAULT_FREQUENCY = "annual"
EDITABLE = ("number", "effective_from", "effective_to", "status", "cra_approval_ref")


def _acting(user: Any) -> Any:
    from numo9.ledger.renumber import acting_as

    return acting_as(user)


def create_registration(
    organisation: Any,
    *,
    type: str,  # noqa: A002 - the model's field name
    number: str,
    effective_from: dt.date | None = None,
    effective_to: dt.date | None = None,
    status: str = "active",
    cra_approval_ref: str = "",
    frequency: str | None = None,
    user: Any = None,
    today: dt.date | None = None,
) -> TaxRegistration:
    """Save a registration; a filing one with a start date gets its cycle and periods."""
    from numo9.tenancy.context import org_context

    with org_context(organisation), transaction.atomic(), _acting(user):
        registration = TaxRegistration(
            organisation=organisation,
            type=type,
            number=number,
            effective_from=effective_from,
            effective_to=effective_to,
            status=status,
            cra_approval_ref=cra_approval_ref,
        )
        registration.save()
        if registration.files_returns and registration.start_date is not None:
            filing_service.apply_change(
                registration,
                {
                    "action": "switch",
                    "frequency": frequency or DEFAULT_FREQUENCY,
                    "effective_from": registration.start_date,
                },
                user=user,
                today=today,
            )
        return registration


def _filed(registration: TaxRegistration) -> Any:
    return FilingPeriod.objects.filter(registration=registration, status__in=LOCKED_PERIOD_STATUSES)


def _refuse_filed(message: str) -> TaxError:
    return TaxError(message, code="tax.registration.filed_periods")


def update_registration(
    registration: TaxRegistration,
    *,
    user: Any = None,
    today: dt.date | None = None,
    frequency: str | None = None,
    **fields: Any,
) -> TaxRegistration:
    """Change a registration and keep its periods in step (module docstring)."""
    from numo9.tenancy.context import org_context

    unknown = set(fields) - set(EDITABLE)
    if unknown:
        raise TypeError(f"Not editable: {', '.join(sorted(unknown))}")
    with org_context(registration.organisation), transaction.atomic(), _acting(user):
        old_start, old_stop = registration.start_date, registration.stop_date
        for name, value in fields.items():
            setattr(registration, name, value)
        new_start, new_stop = registration.start_date, registration.stop_date
        filed = _filed(registration)
        if new_start != old_start and filed.exists():
            raise _refuse_filed(
                _("Returns are already filed: the effective date can't change any more.")
            )
        if new_stop != old_stop and new_stop is not None:
            last = filed.order_by("-end").first()
            if last is not None and last.end > new_stop:
                raise _refuse_filed(
                    _("The period ending %(end)s is filed: the registration can't end before it.")
                    % {"end": last.end.isoformat()}
                )
        registration.save()
        if not registration.files_returns:
            return registration
        cycles = FilingCycle.objects.filter(registration=registration).order_by("effective_from")
        if new_start is None:
            return registration
        if not cycles.exists():
            filing_service.apply_change(
                registration,
                {
                    "action": "switch",
                    "frequency": frequency or DEFAULT_FREQUENCY,
                    "effective_from": new_start,
                },
                user=user,
                today=today,
            )
        elif new_start != old_start:
            first = cycles[0]
            later = cycles.filter(effective_from__lte=new_start).exclude(pk=first.pk)
            first = later.last() or first  # the cycle in force on the new start
            cycles.filter(effective_from__lt=first.effective_from).delete()
            first.effective_from = new_start
            first.save(update_fields=["effective_from"])
            FilingPeriod.objects.filter(registration=registration).delete()
            filing_service.regenerate(registration, today=today)
        elif new_stop != old_stop:
            FilingPeriod.objects.filter(registration=registration).exclude(
                status__in=LOCKED_PERIOD_STATUSES
            ).filter(kind="custom", start__gt=new_stop or dt.date.max).delete()
            last = _filed(registration).order_by("-end").first()
            start = last.end + ONE_DAY if last is not None else new_start
            filing_service.regenerate(registration, start, today=today)
        return registration


def remove_registration(registration: TaxRegistration, *, user: Any = None) -> None:
    """Soft-delete a registration; refused once it has filed periods."""
    from numo9.tenancy.context import org_context

    with org_context(registration.organisation), transaction.atomic(), _acting(user):
        if _filed(registration).exists():
            raise _refuse_filed(
                _("Returns are filed under this registration: end it instead of removing it.")
            )
        FilingPeriod.objects.filter(registration=registration).delete()
        FilingCycle.objects.filter(registration=registration).delete()
        registration.soft_delete()


def summary(registration: TaxRegistration, today: dt.date | None = None) -> dict[str, Any] | None:
    """The filing summary of the registration's card (None when it files no returns)."""
    from numo9.tenancy.context import org_context

    if not registration.files_returns:
        return None
    today = today or timezone.localdate()
    with org_context(registration.organisation):
        return _summary(registration, today)


def _summary(registration: TaxRegistration, today: dt.date) -> dict[str, Any]:
    cycles = list(FilingCycle.objects.filter(registration=registration).order_by("effective_from"))
    current = None
    for cycle in cycles:
        if cycle.effective_from <= today or current is None:
            current = cycle
    periods = FilingPeriod.objects.filter(registration=registration)
    unfiled = periods.exclude(status__in=LOCKED_PERIOD_STATUSES).order_by("start")
    next_due = unfiled.filter(end__lt=today).first() or unfiled.first()
    return {
        "frequency": current.frequency if current else "",
        "periods": periods.count(),
        "next_due": (
            {
                "start": next_due.start.isoformat(),
                "end": next_due.end.isoformat(),
                "due_date": next_due.due_date.isoformat(),
                "attention": filing_service.attention(next_due, today),
            }
            if next_due
            else None
        ),
        "overdue": sum(
            1
            for p in unfiled.filter(end__lt=today)
            if filing_service.attention(p, today) == "overdue"
        ),
    }
