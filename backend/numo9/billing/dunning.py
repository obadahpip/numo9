"""Dunning (U-04-T09): a failed renewal → reminders on days 0, 3, 5, 7 → read-only at grace end.

When a renewal payment fails the subscription goes **past due** with ``grace_until`` = the failure
+ 7 days (U-04-T07/T08): full access during the grace period. Then:

=====  =====================================================================================
Day    Step
=====  =====================================================================================
0      reminder — sent at once by the ``invoice.payment_failed`` handler (``start_dunning``)
3, 5   reminders — Stripe retries the card or debit in between (Smart Retries)
7      the grace ends: the subscription becomes **read-only** (reason ``payment_failed``) at
       ``grace_until`` exactly, and the owners are told
=====  =====================================================================================

A reminder is the ``dunning`` system email (A-07-T11, owner's language: amount, failure date,
grace end, link to the billing page) to each owner, plus an in-app notification
(``billing.payment_failed`` / ``billing.read_only`` — mandatory, can't be turned off).

``run_dunning(now)`` — the platform job ``numo9.billing.run_dunning`` (beat every 15 minutes)
takes, for every past-due subscription, the latest step that is due and not taken yet: a job that
missed a run never sends a burst of old reminders. Each step is recorded once
(``DunningReminder``, unique per subscription, grace period and day): running the job twice, or
a re-delivered failure event, sends nothing twice. A payment that succeeds (``invoice.paid``)
makes the subscription active again and the dunning stops.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.documents.formatting import format_money
from numo9.entitlements.models import StatusReason, Subscription, SubscriptionStatus
from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember

from .models import DunningReminder, PlatformInvoice

DAYS: tuple[int, ...] = (0, 3, 5, 7)
GRACE_DAYS = 7
JOB = "numo9.billing.run_dunning"


def failed_on(subscription: Subscription) -> dt.datetime:
    assert subscription.grace_until is not None  # noqa: S101 - past due always has a grace end
    return subscription.grace_until - dt.timedelta(days=GRACE_DAYS)


def due_day(subscription: Subscription, now: dt.datetime) -> int | None:
    """The latest step due ``now`` (0, 3, 5 or 7), or None before the failure."""
    if subscription.grace_until is None:
        return None
    if now >= subscription.grace_until:
        return 7
    elapsed = now - failed_on(subscription)
    due = [day for day in DAYS[:-1] if elapsed >= dt.timedelta(days=day)]
    return due[-1] if due else None


def _owners(subscription: Subscription) -> list[Any]:
    return [
        m.user
        for m in OrganisationMember.objects.filter(
            organisation_id=subscription.organisation_id, role="owner"
        ).select_related("user")
    ]


def _amount(subscription: Subscription) -> str:
    with org_context(subscription.organisation):
        invoice = (
            PlatformInvoice.objects.filter(
                stripe_subscription_id=subscription.stripe_subscription_id
            )
            .exclude(status="paid")
            .order_by("-issued_at", "-pk")
            .first()
        )
    cents = invoice.amount_due_cents if invoice is not None else 0
    return format_money(Decimal(cents) / 100)


def _tell(subscription: Subscription, day: int) -> int:
    from django.conf import settings

    from numo9.notifications.catalogue import render_system
    from numo9.notifications.mail import queue_email
    from numo9.notifications.services import notify

    organisation = subscription.organisation
    link_path = f"/o/{organisation.public_id}/settings/subscription"
    context = {
        "organisation": organisation.name,
        "amount": _amount(subscription),
        "failed_on": timezone.localdate(failed_on(subscription)).isoformat(),
        "grace_until": timezone.localdate(subscription.grace_until).isoformat(),
        "day": day,
        "link": f"{settings.FRONTEND_URL}{link_path}",
    }
    owners = _owners(subscription)
    for owner in owners:
        email = render_system(
            "dunning", context, language=getattr(owner, "locale", None), organisation=organisation
        )
        queue_email(
            owner.email,
            email.subject,
            email.text,
            html=email.html,
            recipient=owner,
            kind=f"dunning.day{day}",
            language=email.language,
        )
    notify(
        "billing.read_only" if day == 7 else "billing.payment_failed",
        owners,
        channels=["in_app"],
        organisation=organisation,
        params={"organisation": organisation.name, "grace_until": context["grace_until"]},
        link=link_path,
    )
    return len(owners)


def take_step(subscription: Subscription, day: int) -> bool:
    """Take a dunning step once; False when it was already taken for this grace period."""
    assert subscription.grace_until is not None  # noqa: S101
    try:
        with transaction.atomic():
            with org_context(subscription.organisation):
                step = DunningReminder.objects.create(
                    organisation_id=subscription.organisation_id,
                    subscription=subscription,
                    grace_until=subscription.grace_until,
                    day=day,
                )
            if day == 7 and subscription.status == SubscriptionStatus.PAST_DUE:
                subscription.status = SubscriptionStatus.READ_ONLY
                subscription.status_reason = StatusReason.PAYMENT_FAILED
                subscription.save()
            step.recipients = _tell(subscription, day)
            step.save(update_fields=["recipients"])
    except IntegrityError:
        return False
    return True


def start_dunning(subscription: Subscription, invoice: Any = None) -> bool:
    """Day 0, from the failure event: tell the owners now (once per grace period)."""
    if subscription.status != SubscriptionStatus.PAST_DUE or subscription.grace_until is None:
        return False
    return take_step(subscription, 0)


def run_dunning(now: dt.datetime | None = None) -> dict[str, int]:
    """Take the due step of every past-due subscription (see the module docstring)."""
    now = now or timezone.now()
    counts = {"reminders": 0, "read_only": 0}
    rows = Subscription._base_manager.filter(
        status=SubscriptionStatus.PAST_DUE, deleted_at__isnull=True, grace_until__isnull=False
    ).select_related("organisation")
    for subscription in rows:
        with transaction.atomic():
            locked = (
                Subscription._base_manager.select_for_update()
                .select_related("organisation")
                .get(pk=subscription.pk)
            )
            if locked.status != SubscriptionStatus.PAST_DUE:
                continue
            day = due_day(locked, now)
            if day is None or not take_step(locked, day):
                continue
            counts["read_only" if day == 7 else "reminders"] += 1
    return counts


@platform_job(name=JOB, queue=DEFAULT)
def run_dunning_job() -> dict[str, int]:
    """Beat, every 15 minutes."""
    return run_dunning()
