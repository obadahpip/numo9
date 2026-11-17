"""Free trial (U-05): normalisers, starting a trial, refusing a second one, reminders, expiry
and conversion. See ``docs/architecture/trial.md``.

**Normalisers** (U-05-T03) — what the trial registry stores and compares:

- ``normalise_bn("123 456 782 RT0001")`` → ``"123456782"``: the nine-digit Business Number
  whatever the spacing, dashes or program account suffix (RT/RP/RC/RZ… + 4 digits); anything that
  isn't nine digits (with a valid check digit) → ``""`` (no BN to compare);
- ``normalise_email("Dana+numo9@Refined.CA ")`` → ``"dana@refined.ca"``: trimmed, lower-case,
  plus-addressing stripped from the local part (``dana+trial2@`` is ``dana@``).

**Starting** (U-05-T04) — ``start_trial(org)``: a ``trialing`` subscription of the configured
package ending at **23:59:59 organisation-local time on the last day** (day 1 = the day it
starts), stored in UTC (``trial_end``).
"""

from __future__ import annotations

import datetime as dt
import re
import zoneinfo

from django.db import transaction
from django.utils import timezone

from numo9.orgsettings.validators import luhn_valid
from numo9.tenancy.context import org_context
from numo9.tenancy.models import DEFAULT_TIME_ZONE, Organisation

from .models import Subscription, SubscriptionStatus, TrialConfig

_BN = re.compile(r"^(\d{9})(?:(?:RT|RP|RC|RZ|RR|RM|RN|RD|RG)\d{4})?$")


def normalise_bn(value: str | None) -> str:
    """The nine-digit BN of ``value``, or ``""`` when it doesn't hold a valid one."""
    compact = re.sub(r"[\s\-.]", "", (value or "").upper())
    match = _BN.match(compact)
    if match is None or not luhn_valid(match[1]):
        return ""
    return match[1]


def normalise_email(value: str | None) -> str:
    """Trimmed, lower-case, without plus-addressing; ``""`` when it isn't an address."""
    text = (value or "").strip().lower()
    if text.count("@") != 1:
        return ""
    local, domain = text.split("@")
    local = local.split("+", 1)[0]
    if not local or not domain or "." not in domain:
        return ""
    return f"{local}@{domain}"


# ---- starting a trial (U-05-T04) ---------------------------------------------------------------


def trial_end(start: dt.datetime, days: int, time_zone: str) -> dt.datetime:
    """The end of a ``days``-day trial that starts at ``start``: 23:59:59 **organisation-local
    time** on the last day (the start day is day 1), returned in UTC. Computed on the local
    calendar, so a DST change in the month moves nothing: the trial still ends at local 23:59:59.
    """
    zone = zoneinfo.ZoneInfo(time_zone or DEFAULT_TIME_ZONE)
    first_day = start.astimezone(zone).date()
    last_day = first_day + dt.timedelta(days=days - 1)
    local_end = dt.datetime.combine(last_day, dt.time(23, 59, 59), tzinfo=zone)
    return local_end.astimezone(dt.UTC)


def start_trial(organisation: Organisation, *, now: dt.datetime | None = None) -> Subscription:
    """Start the organisation's free trial: a ``trialing`` subscription of the configured trial
    package (``TrialConfig``) that ends at local 23:59:59 on day 30 (the configured length).

    An organisation that already has a current subscription keeps it (returned unchanged).
    """
    now = now or timezone.now()
    with org_context(organisation), transaction.atomic():
        current = (
            Subscription.objects.filter(organisation=organisation, deleted_at__isnull=True)
            .exclude(status=SubscriptionStatus.CANCELLED)
            .first()
        )
        if current is not None:
            return current
        config = TrialConfig.current()
        subscription: Subscription = Subscription.objects.create(
            organisation=organisation,
            package=config.package,
            status=SubscriptionStatus.TRIALING,
            current_period_end=trial_end(now, config.days, organisation.time_zone),
            status_changed_at=now,
        )
    return subscription


def trial_days_left(subscription: Subscription, *, now: dt.datetime | None = None) -> int | None:
    """Whole days left on the organisation's calendar (0 on the last day, negative after it);
    ``None`` when the subscription isn't a trial with an end."""
    if (
        subscription.status != SubscriptionStatus.TRIALING
        or subscription.current_period_end is None
    ):
        return None
    zone = zoneinfo.ZoneInfo(subscription.organisation.time_zone or DEFAULT_TIME_ZONE)
    today = (now or timezone.now()).astimezone(zone).date()
    return (subscription.current_period_end.astimezone(zone).date() - today).days
