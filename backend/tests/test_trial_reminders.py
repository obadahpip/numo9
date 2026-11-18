"""U-05-T07 — Reminder job 7/3/1/0 days (idempotent per organisation + day).

Acceptance: exactly one email per milestone. Running the hourly job through a whole 30-day trial
(every hour, on a Toronto organisation, across the DST change) sends four reminders per owner —
7, 3 and 1 days left and the day it ended — each once, in the owner's language; a job that missed
runs sends only the current milestone; a converted trial gets nothing more.
"""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.entitlements.models import StatusReason, Subscription, SubscriptionStatus, TrialReminder
from numo9.entitlements.trials import due_milestone, run_trial_reminders, start_trial
from numo9.notifications.models import EmailMessage
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
UTC = dt.UTC
START = dt.datetime(2026, 10, 15, 18, 0, tzinfo=UTC)  # 14:00 EDT; ends 13 Nov 23:59:59 EST


def _trial(**owner: str) -> Subscription:
    org = Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")
    OrganisationMember.objects.create(
        organisation=org,
        user=user("sam@refined.ca", "Sam Roy", **owner),
        role=OrganisationRole.OWNER,
    )
    return start_trial(org, now=START)


def _expire(subscription: Subscription) -> None:
    with org_context(subscription.organisation):
        subscription.status = SubscriptionStatus.READ_ONLY
        subscription.status_reason = StatusReason.TRIAL_ENDED
        subscription.save()


def test_one_email_per_milestone_over_the_whole_trial() -> None:
    subscription = _trial()
    assert subscription.current_period_end == dt.datetime(2026, 11, 14, 4, 59, 59, tzinfo=UTC)
    now = START
    while now < dt.datetime(2026, 11, 16, tzinfo=UTC):
        if now > subscription.current_period_end and subscription.status == "trialing":
            _expire(subscription)  # the expiry job's part (U-05-T08)
        run_trial_reminders(now)
        now += dt.timedelta(hours=1)
    kinds = list(
        EmailMessage.platform_messages.filter(kind__startswith="trial.reminder")
        .order_by("pk")
        .values_list("kind", flat=True)
    )
    assert kinds == [
        "trial.reminder.day7",
        "trial.reminder.day3",
        "trial.reminder.day1",
        "trial.reminder.day0",
    ]
    with org_context(subscription.organisation):
        sent = {r.milestone: r.sent_at for r in TrialReminder.objects.all()}
    # 7 days left starts at local midnight on 6 Nov (05:00 UTC, EST)
    assert (
        dt.datetime(2026, 11, 6, 5, 0, tzinfo=UTC)
        <= sent[7]
        < dt.datetime(2026, 11, 6, 6, 0, tzinfo=UTC)
    )
    assert sent[0] > subscription.current_period_end


def test_late_job_sends_only_the_current_milestone_and_twice_nothing() -> None:
    _trial(locale="fr-ca")
    two_days_left = dt.datetime(2026, 11, 11, 17, 0, tzinfo=UTC)
    assert run_trial_reminders(two_days_left)["3"] == 1
    assert run_trial_reminders(two_days_left) == {"7": 0, "3": 0, "1": 0, "0": 0}
    [message] = EmailMessage.platform_messages.filter(kind__startswith="trial.reminder")
    assert message.kind == "trial.reminder.day3" and message.language == "fr-ca"
    assert "2026-11-13" in message.text_body  # the local last day


def test_converted_trial_gets_nothing() -> None:
    subscription = _trial()
    with org_context(subscription.organisation):
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.save()
    assert due_milestone(subscription, dt.datetime(2026, 11, 12, tzinfo=UTC)) is None
    assert run_trial_reminders(dt.datetime(2026, 11, 13, 12, tzinfo=UTC)) == {
        "7": 0, "3": 0, "1": 0, "0": 0,
    }  # fmt: skip
