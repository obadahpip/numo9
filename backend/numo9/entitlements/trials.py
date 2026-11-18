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
from collections.abc import Callable
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job
from numo9.orgsettings.validators import luhn_valid
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    DEFAULT_TIME_ZONE,
    Organisation,
    OrganisationMember,
    OrganisationRole,
)

from .models import (
    StatusReason,
    Subscription,
    SubscriptionStatus,
    TrialConfig,
    TrialRegistry,
    TrialReminder,
)

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


def start_trial(
    organisation: Organisation, *, now: dt.datetime | None = None, email: str | None = None
) -> Subscription:
    """Start the organisation's free trial: a ``trialing`` subscription of the configured trial
    package (``TrialConfig``) that ends at local 23:59:59 on day 30 (the configured length).

    An organisation that already has a current subscription keeps it (returned unchanged).
    The trial is recorded in the registry with the organisation's BN and its owner's email
    (``email`` when the owner isn't a member yet); a BN or email that already had a trial raises
    ``TrialAlreadyUsed`` (U-05-T06) and nothing is created.
    """
    now = now or timezone.now()
    with org_context(organisation), transaction.atomic():
        current: Subscription | None = (
            Subscription.objects.filter(organisation=organisation, deleted_at__isnull=True)
            .exclude(status=SubscriptionStatus.CANCELLED)
            .first()
        )
        if current is not None:
            return current
        register_trial(
            organisation,
            bn=organisation_bn(organisation),
            email=normalise_email(email) if email is not None else owner_email(organisation),
        )
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


# ---- one trial per BN and per email (U-05-T06) --------------------------------------------------


class TrialAlreadyUsed(ValidationError):
    """A free trial was already started with this Business Number or owner email."""

    def __init__(self, existing: Organisation, field: str) -> None:
        message = (
            _(
                "A free trial was already used with this Business Number. Choose a package to "
                "start using Numo9 with this organisation."
            )
            if field == "bn"
            else _(
                "A free trial was already used with this email address. Choose a package to "
                "start using Numo9 with this organisation."
            )
        )
        super().__init__(
            message,
            code=TRIAL_ALREADY_USED_CODE,
        )
        self.existing = existing
        self.field = field


TRIAL_ALREADY_USED_CODE = "trial_already_used"


def mask_name(name: str) -> str:
    """``Maple Leaf Supply Ltd.`` → ``Ma*** Le*** Su*** Lt***``: enough for the Platform Owner
    to recognise the organisation, never its full name."""
    return " ".join(f"{word[:2]}***" for word in name.split() if word) or "***"


def organisation_bn(organisation: Organisation) -> str:
    from numo9.orgsettings.models import TaxRegistration

    numbers = TaxRegistration.objects.unscoped(reason="trial registry: the BN of a new trial")
    for registration in numbers.filter(organisation=organisation).order_by("pk"):
        bn = normalise_bn(registration.business_number)
        if bn:
            return bn
    return ""


def owner_email(organisation: Organisation) -> str:
    owner = (
        OrganisationMember.objects.filter(organisation=organisation, role=OrganisationRole.OWNER)
        .select_related("user")
        .order_by("pk")
        .first()
    )
    return normalise_email(owner.user.email if owner is not None else "")


def check_trial_available(
    *, bn: str = "", email: str = "", exclude: Organisation | None = None
) -> None:
    """Raise ``TrialAlreadyUsed`` when the (normalised) BN or email already started a trial."""
    rows = TrialRegistry.objects.select_related("organisation")
    if exclude is not None:
        rows = rows.exclude(organisation=exclude)
    if bn:
        found = rows.filter(normalised_bn=bn).first()
        if found is not None:
            raise TrialAlreadyUsed(found.organisation, "bn")
    if email:
        found = rows.filter(normalised_email=email).first()
        if found is not None:
            raise TrialAlreadyUsed(found.organisation, "email")


def register_trial(organisation: Organisation, *, bn: str = "", email: str = "") -> TrialRegistry:
    """Record the trial in the registry; a concurrent trial with the same BN or email loses the
    race at the database (unique indexes) and is refused the same way."""
    check_trial_available(bn=bn, email=email)
    try:
        with transaction.atomic():
            row: TrialRegistry = TrialRegistry.objects.create(
                organisation=organisation, normalised_bn=bn, normalised_email=email
            )
    except IntegrityError:
        check_trial_available(bn=bn, email=email, exclude=organisation)
        raise
    return row


def claim_bn(organisation: Organisation, number: str) -> None:
    """A BN entered **after** the trial started (U-05 edge case): check it then. Refused when
    another organisation's trial used it; otherwise stored on the organisation's trial."""
    bn = normalise_bn(number)
    row = TrialRegistry.objects.filter(organisation=organisation).first()
    if not bn or row is None or row.normalised_bn == bn:
        return
    check_trial_available(bn=bn, exclude=organisation)
    if not row.normalised_bn:
        row.normalised_bn = bn
        try:
            with transaction.atomic():
                row.save(update_fields=["normalised_bn"])
        except IntegrityError:
            check_trial_available(bn=bn, exclude=organisation)
            raise


def bn_entered(sender: Any, instance: Any, **kwargs: Any) -> None:
    """``pre_save`` of a tax registration: a BN of an organisation on a trial is checked against
    the registry (``claim_bn``); a BN that already had another organisation's trial is refused
    (``TrialAlreadyUsed``, a ``ValidationError``: the settings API answers 400)."""
    if kwargs.get("raw"):
        return
    number = instance.business_number  # the BN of a BN or program (RT, RP…) registration
    if number:
        claim_bn(instance.organisation, number)


# ---- reminders (U-05-T07) ----------------------------------------------------------------------

REMINDER_JOB = "numo9.entitlements.trial_reminders"


def due_milestone(subscription: Subscription, now: dt.datetime) -> int | None:
    """The reminder due now: 7, 3 or 1 days left (the latest one reached — a job that missed a
    run sends only the current one), or 0 for a trial that ended. Days count on the
    organisation's calendar."""
    if subscription.status == SubscriptionStatus.TRIALING:
        left = trial_days_left(subscription, now=now)
        if left is None:
            return None
        for milestone in (1, 3, 7):
            if 0 <= left <= milestone:
                return milestone
        return None
    if (
        subscription.status == SubscriptionStatus.READ_ONLY
        and subscription.status_reason == StatusReason.TRIAL_ENDED
    ):
        return 0
    return None


def _owners(subscription: Subscription) -> list[Any]:
    return [
        member.user
        for member in OrganisationMember.objects.filter(
            organisation_id=subscription.organisation_id, role=OrganisationRole.OWNER
        ).select_related("user")
    ]


def _send_reminder(subscription: Subscription, milestone: int) -> int:
    from django.conf import settings

    from numo9.notifications.catalogue import render_system
    from numo9.notifications.mail import queue_email

    organisation = subscription.organisation
    zone = zoneinfo.ZoneInfo(organisation.time_zone or DEFAULT_TIME_ZONE)
    ends = subscription.current_period_end
    context = {
        "organisation": organisation.name,
        "days_left": milestone,
        "ends_on": ends.astimezone(zone).date().isoformat() if ends else "",
        "link": f"{settings.FRONTEND_URL}/o/{organisation.public_id}/settings/subscription",
    }
    owners = _owners(subscription)
    for owner in owners:
        email = render_system(
            "trial_reminder",
            context,
            language=getattr(owner, "locale", None),
            organisation=organisation,
        )
        queue_email(
            owner.email,
            email.subject,
            email.text,
            html=email.html,
            recipient=owner,
            organisation=organisation,
            kind=f"trial.reminder.day{milestone}",
            language=email.language,
        )
    return len(owners)


def send_reminder(
    subscription: Subscription, milestone: int, *, now: dt.datetime | None = None
) -> bool:
    """Send a milestone's reminder once; False when it was already sent."""
    try:
        with transaction.atomic(), org_context(subscription.organisation):
            row = TrialReminder.objects.create(
                organisation_id=subscription.organisation_id,
                subscription=subscription,
                milestone=milestone,
                sent_at=now or timezone.now(),
            )
            row.recipients = _send_reminder(subscription, milestone)
            row.save(update_fields=["recipients"])
    except IntegrityError:
        return False
    return True


def run_trial_reminders(now: dt.datetime | None = None) -> dict[str, int]:
    """Send every due trial reminder (beat, hourly: organisations' days start at different UTC
    hours). Idempotent: one email per milestone per trial."""
    now = now or timezone.now()
    sent = {str(m): 0 for m in TrialReminder.MILESTONES}
    rows = Subscription._base_manager.filter(
        deleted_at__isnull=True,
        status__in=(SubscriptionStatus.TRIALING, SubscriptionStatus.READ_ONLY),
        current_period_end__isnull=False,
    ).select_related("organisation")
    for subscription in rows:
        milestone = due_milestone(subscription, now)
        if milestone is not None and send_reminder(subscription, milestone, now=now):
            sent[str(milestone)] += 1
    return sent


@platform_job(name=REMINDER_JOB, queue=DEFAULT)
def trial_reminders_job() -> dict[str, int]:
    return run_trial_reminders()


# ---- expiry (U-05-T08) -------------------------------------------------------------------------

EXPIRY_JOB = "numo9.entitlements.expire_trials"


def expire_trial(subscription_id: int, now: dt.datetime) -> bool:
    """End one trial whose time is up: **read-only** (reason ``trial_ended``), data kept, export
    allowed. The row is locked and re-read first, so a conversion that commits at the last minute
    wins: an active (converted) subscription is skipped. Tells the owners at once (milestone 0).
    """
    with transaction.atomic():
        locked = (
            Subscription._base_manager.select_for_update()
            .select_related("organisation")
            .filter(pk=subscription_id)
            .first()
        )
        if (
            locked is None
            or locked.status != SubscriptionStatus.TRIALING
            or locked.current_period_end is None
            or locked.current_period_end > now
        ):
            return False
        with org_context(locked.organisation):
            locked.status = SubscriptionStatus.READ_ONLY
            locked.status_reason = StatusReason.TRIAL_ENDED
            locked.save()
    send_reminder(locked, 0, now=now)
    return True


def run_trial_expiry(now: dt.datetime | None = None) -> int:
    """End every trial whose end has passed (beat every 5 minutes); returns how many."""
    now = now or timezone.now()
    due = Subscription._base_manager.filter(
        deleted_at__isnull=True,
        status=SubscriptionStatus.TRIALING,
        current_period_end__lte=now,
    ).values_list("pk", flat=True)
    return sum(1 for pk in list(due) if expire_trial(pk, now))


@platform_job(name=EXPIRY_JOB, queue=DEFAULT)
def expire_trials_job() -> int:
    return run_trial_expiry()


# ---- conversion (U-05-T09) ---------------------------------------------------------------------

#: ``check(subscription)`` — run when a trial converts: the founding-1,000 offer (U-08) registers
#: its eligibility check here (trial organisations count toward the founding counter only from
#: their first successful payment).
ConversionCheck = Callable[[Subscription], None]
_conversion_checks: list[ConversionCheck] = []


def register_conversion_check(check: ConversionCheck) -> ConversionCheck:
    if check not in _conversion_checks:
        _conversion_checks.append(check)
    return check


def is_trial(subscription: Subscription) -> bool:
    """A trial, running or ended unpaid — what the first successful payment converts."""
    return subscription.status == SubscriptionStatus.TRIALING or (
        subscription.status == SubscriptionStatus.READ_ONLY
        and subscription.status_reason == StatusReason.TRIAL_ENDED
    )


def trial_converted(subscription: Subscription, at: dt.datetime) -> None:
    """The first successful payment turned the trial into a paid subscription (the billing state
    table already made it ``active``). Only the subscription's status changes — no business record
    is touched, so the books are exactly as they were. Records the conversion once (registry),
    audits it and runs the conversion checks (founding offer, U-08)."""
    from numo9.audit.service import record

    updated = TrialRegistry.objects.filter(
        organisation_id=subscription.organisation_id, converted_at__isnull=True
    ).update(converted_at=at)
    if not updated:
        return  # converted before (a re-delivered event) or never registered
    with org_context(subscription.organisation):
        record(
            "entitlements.trial.converted",
            obj=subscription,
            organisation=subscription.organisation,
            meta={"package": subscription.package.code if subscription.package else ""},
        )
    for check in list(_conversion_checks):
        check(subscription)
