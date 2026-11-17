"""C-02-T09 — Journal state machine. Acceptance: an illegal transition raises.

Draft → Awaiting approval → Posted → Reversed with explicit transitions: every pair of states is
tried (allowed ones succeed, the others raise ``ledger.journal.illegal_transition`` naming both
states); a draft is saved validated and edited (lines replaced) but an entry awaiting approval or
posted can't be edited; drafts may sit in a locked period but can't be posted there; posting a
draft or an approved entry numbers it with its stored lines and one audit event; posting twice is
refused.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest

from numo9.audit.models import AuditEvent
from numo9.ledger.models import Account, JournalEntry, JournalLine, JournalStatus
from numo9.ledger.services import (
    TRANSITIONS,
    IllegalTransition,
    assert_transition,
    post_entry,
    return_to_draft,
    save_draft,
    submit,
)
from numo9.ledger.validation import JournalInvalid, JournalSpec, LineSpec
from numo9.orgsettings.locks import LockedPeriod
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

DATE = dt.date(2026, 4, 15)
S = JournalStatus


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def acc(org: Organisation) -> dict[str, Account]:
    return {
        "rent": account(org, "6100", "Rent", subtype="operating_expense"),
        "bank": account(org, "1000", "Chequing", subtype="bank"),
        "util": account(org, "6200", "Utilities", subtype="operating_expense"),
    }


def accrual(acc: dict[str, Account], amount: str = "2500.00", day: dt.date = DATE) -> JournalSpec:
    return JournalSpec(
        date=day,
        narration="April rent",
        lines=(
            LineSpec(acc["rent"], debit=Decimal(amount)),
            LineSpec(acc["bank"], credit=Decimal(amount)),
        ),
    )


def test_transition_table_is_exactly_the_plan() -> None:
    assert {
        S.DRAFT: {S.AWAITING_APPROVAL, S.POSTED},
        S.AWAITING_APPROVAL: {S.DRAFT, S.POSTED},
        S.POSTED: {S.REVERSED},
        S.REVERSED: set(),
    } == TRANSITIONS


@pytest.mark.parametrize("start", S.values)
@pytest.mark.parametrize("to", S.values)
def test_every_pair_of_states(start: str, to: str) -> None:
    entry = JournalEntry(status=start, number=7 if start in (S.POSTED, S.REVERSED) else None)
    if to in TRANSITIONS[start]:
        assert_transition(entry, to)
        return
    with pytest.raises(IllegalTransition) as refused:
        assert_transition(entry, to)
    assert refused.value.code == "ledger.journal.illegal_transition"
    assert str(S(start).label).lower() in refused.value.messages[0]
    assert str(S(to).label).lower() in refused.value.messages[0]


def test_draft_submit_return_post(acc: dict[str, Account]) -> None:
    entry = save_draft(accrual(acc), user=None)
    assert entry.status == S.DRAFT and entry.number is None
    assert JournalLine.objects.filter(entry=entry).count() == 2
    entry = submit(entry)
    assert entry.status == S.AWAITING_APPROVAL
    with pytest.raises(IllegalTransition):
        submit(entry)
    entry = return_to_draft(entry)
    assert entry.status == S.DRAFT
    with pytest.raises(IllegalTransition):
        return_to_draft(entry)
    entry = post_entry(submit(entry), user=None)
    stored = JournalEntry.objects.get(pk=entry.pk)
    assert stored.status == S.POSTED and stored.number == 1 and stored.posted_at is not None
    posted = AuditEvent.objects.get(action="ledger.journalentry.posted")
    assert posted.changes["status"] == ["awaiting_approval", "posted"]
    with pytest.raises(IllegalTransition) as twice:
        post_entry(entry)
    assert "is posted: it can't become posted" in twice.value.messages[0]
    with pytest.raises(IllegalTransition):
        submit(entry)
    with pytest.raises(IllegalTransition):
        return_to_draft(entry)


def test_a_draft_posts_directly(acc: dict[str, Account]) -> None:
    entry = post_entry(save_draft(accrual(acc)), user=None)
    assert entry.status == S.POSTED and entry.number == 1


def test_drafts_are_edited_lines_replaced(acc: dict[str, Account]) -> None:
    entry = save_draft(accrual(acc))
    edited = JournalSpec(
        date=DATE,
        narration="April rent and hydro",
        lines=(
            LineSpec(acc["rent"], debit=Decimal("2500.00")),
            LineSpec(acc["util"], debit=Decimal("180.00")),
            LineSpec(acc["bank"], credit=Decimal("2680.00")),
        ),
    )
    entry = save_draft(edited, entry=entry)
    assert entry.narration == "April rent and hydro"
    assert list(entry.lines.order_by("line_no").values_list("account__code", flat=True)) == [
        "6100",
        "6200",
        "1000",
    ]
    with pytest.raises(JournalInvalid):
        save_draft(accrual(acc, "-1"), entry=entry)
    assert entry.lines.count() == 3  # the refused edit changed nothing


@pytest.mark.parametrize("move", ["submit", "post"])
def test_only_drafts_are_edited(acc: dict[str, Account], move: str) -> None:
    entry = save_draft(accrual(acc))
    entry = submit(entry) if move == "submit" else post_entry(entry, user=None)
    with pytest.raises(IllegalTransition) as refused:
        save_draft(accrual(acc, "10.00"), entry=entry)
    assert refused.value.code == "ledger.journal.not_draft"


def test_drafts_may_sit_in_a_locked_period(org: Organisation, acc: dict[str, Account]) -> None:
    LockDate(organisation=org, module="gl", level="everyone", date=DATE).save()
    entry = submit(save_draft(accrual(acc)))
    with pytest.raises(LockedPeriod):
        post_entry(entry, user=None)
    entry.refresh_from_db()
    assert entry.status == S.AWAITING_APPROVAL and entry.number is None
    entry = save_draft(accrual(acc, day=DATE + dt.timedelta(days=1)), entry=return_to_draft(entry))
    assert post_entry(entry, user=None).number == 1
