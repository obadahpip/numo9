"""C-03-T08 — cash guard outcome by role: someone who isn't an adviser is blocked; an adviser is
warned and posts with a mandatory reason, stored in ``JournalOverride(reason, user, at)`` and
audited.

Acceptance: the owner (not an adviser) gets ``ledger.journal.negative_cash`` naming
"Petty Cash would be −417.22 on 15 Jun 2026" and nothing is posted; the adviser without a reason
(or with fewer than 10 characters) gets ``ledger.journal.override_reason_required``; with a reason
the journal posts and the override is kept and audited; posting a draft goes through the same
rule; system jobs (no person) and reversals aren't stopped.
"""

from __future__ import annotations

import pytest

from numo9.audit.models import AuditEvent
from numo9.ledger.models import JournalEntry, JournalOverride, JournalStatus
from numo9.ledger.policy import NegativeCash
from numo9.ledger.services import post_entry, post_journal, reverse, save_draft
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay, people

pytestmark = pytest.mark.django_db
MESSAGE = "Petty Cash would be −417.22 on 15 Jun 2026"


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def test_non_adviser_is_blocked(org: Organisation) -> None:
    who = people(org)
    with org_context(org):
        accounts = chart(org)
        with pytest.raises(NegativeCash) as raised:
            post_journal(pay(accounts["office"], accounts["petty"], "417.22"), user=who["owner"])
        assert raised.value.error_list[0].code == "ledger.journal.negative_cash"
        assert raised.value.messages[0].startswith(MESSAGE)
        assert raised.value.adviser is False
        assert not JournalEntry.objects.exists()


@pytest.mark.parametrize("reason", ["", "   ", "too short"])
def test_adviser_needs_a_reason(org: Organisation, reason: str) -> None:
    who = people(org)
    with org_context(org):
        accounts = chart(org)
        with pytest.raises(NegativeCash) as raised:
            post_journal(
                pay(accounts["office"], accounts["petty"], "417.22"),
                user=who["adviser"],
                override_reason=reason,
            )
    assert raised.value.error_list[0].code == "ledger.journal.override_reason_required"
    assert raised.value.adviser is True
    assert [p.message() for p in raised.value.projections] == [MESSAGE]


def test_adviser_posts_with_a_reason_kept_and_audited(org: Organisation) -> None:
    who = people(org)
    with org_context(org):
        accounts = chart(org)
        entry = post_journal(
            pay(accounts["office"], accounts["petty"], "417.22"),
            user=who["adviser"],
            override_reason="Owner paid from personal funds; float topped up Monday.",
        )
        assert entry.status == JournalStatus.POSTED
        override = JournalOverride.objects.get()
        assert (override.entry_id, override.user) == (entry.pk, who["adviser"])
        assert override.reason.startswith("Owner paid")
        assert override.shortfalls[0]["message"] == MESSAGE
        event = AuditEvent.objects.get(action="ledger.journalentry.override")
        assert event.meta["reason"] == override.reason
        assert event.meta["shortfalls"] == [MESSAGE]


def test_posting_a_draft_goes_through_the_rule(org: Organisation) -> None:
    who = people(org)
    with org_context(org):
        accounts = chart(org)
        draft = save_draft(pay(accounts["office"], accounts["petty"], "417.22"))
        with pytest.raises(NegativeCash):
            post_entry(draft, user=who["owner"])
        posted = post_entry(
            draft, user=who["adviser"], override_reason="Timing — deposit clears tomorrow."
        )
        assert posted.status == JournalStatus.POSTED
        assert JournalOverride.objects.filter(entry=posted).exists()


def test_system_jobs_and_reversals_are_not_stopped(org: Organisation) -> None:
    who = people(org)
    with org_context(org):
        accounts = chart(org)
        money_in = post_journal(
            pay(accounts["petty"], accounts["sales"], "100.00"), user=who["owner"]
        )
        assert post_journal(pay(accounts["office"], accounts["petty"], "417.22")).number
        assert reverse(money_in, user=who["owner"]).status == JournalStatus.POSTED
