"""A-05-T06 — Hook the lock service into the posting engine (C-02) and generic document save.

Acceptance: posting before the lock is refused — a journal entry dated on or before the GL lock
can't become posted (409 ``lock.violation`` naming the lock), after it it can. Also: drafts in a
locked period can be kept and edited; reversing a posted entry of a locked period (status only)
is allowed; a generic document (A-05 mixin) can't be saved or deleted in a locked period, nor
moved out of one; advisers pass the advisers-only level through the request's user; a system
change is stopped.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from numo9.accounts.models import User
from numo9.audit.context import audit_context
from numo9.ledger.models import Account, JournalEntry, JournalLine, JournalStatus
from numo9.orgsettings.locks import LockedPeriod
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, Practice, PracticeAssignment, PracticeMember
from tests.ledger_helpers import account
from tests.testapp.models import LockedDocument

pytestmark = pytest.mark.django_db

LOCK = dt.date(2026, 3, 31)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(organisation):
        for module, level in (("gl", "everyone"), ("ar", "advisers_only")):
            LockDate(organisation=organisation, module=module, level=level, date=LOCK).save()
    return organisation


def _draft(org: Organisation, day: dt.date) -> JournalEntry:
    with org_context(org):
        entry = JournalEntry(organisation=org, date=day, narration="Accrual")
        entry.save()
        cash = Account.objects.filter(code="1000").first() or account(org, "1000")
        sales = Account.objects.filter(code="4000").first() or account(org, "4000")
        JournalLine.objects.create(
            organisation=org, entry=entry, line_no=1, account=cash, debit=Decimal("10")
        )
        JournalLine.objects.create(
            organisation=org, entry=entry, line_no=2, account=sales, credit=Decimal("10")
        )
        return entry


def _post(entry: JournalEntry, number: int) -> None:
    entry.status, entry.number, entry.posted_at = JournalStatus.POSTED, number, timezone.now()
    entry.save()


def test_posting_before_the_gl_lock_is_refused(org: Organisation) -> None:
    locked = _draft(org, LOCK)
    with org_context(org):
        locked.narration = "Accrual, revised"  # a draft in a locked period can be edited
        locked.save()
        with pytest.raises(LockedPeriod) as raised:
            _post(locked, 1)
        assert raised.value.violation.module == "gl"
        assert "2026-03-31" in str(raised.value.detail)
        assert JournalEntry.objects.get(pk=locked.pk).status == "draft"

        open_entry = _draft(org, dt.date(2026, 4, 1))
        _post(open_entry, 1)
        assert JournalEntry.objects.get(pk=open_entry.pk).status == "posted"


def test_reversing_an_entry_of_a_locked_period_is_allowed(org: Organisation) -> None:
    entry = _draft(org, dt.date(2026, 3, 15))
    with org_context(org):
        LockDate.objects.filter(module="gl").update(date=dt.date(2026, 2, 28))
        _post(entry, 1)
        LockDate.objects.filter(module="gl").update(date=LOCK)  # period closed after posting
        entry.status = JournalStatus.REVERSED
        entry.save()
        assert JournalEntry.objects.get(pk=entry.pk).status == "reversed"


def test_generic_document_save_and_delete(org: Organisation) -> None:
    with org_context(org):
        draft = LockedDocument(organisation=org, date=LOCK)
        draft.save()  # drafts don't count
        draft.status = "approved"
        with pytest.raises(LockedPeriod):
            draft.save()
        current = LockedDocument(organisation=org, date=dt.date(2026, 4, 2), status="approved")
        current.save()
        current.date = LOCK  # moving into a locked period
        with pytest.raises(LockedPeriod):
            current.save()

        # A document already in the (now) locked period: can't move out of it, can't be deleted.
        LockDate.objects.update(date=None)
        old = LockedDocument(organisation=org, date=dt.date(2026, 3, 10), status="approved")
        old.save()
        LockDate.objects.filter(module="ar").update(date=LOCK)
        old.date = dt.date(2026, 4, 10)
        with pytest.raises(LockedPeriod) as raised:
            old.save()
        assert raised.value.violation.module == "ar"
        with pytest.raises(LockedPeriod):
            LockedDocument.objects.get(pk=old.pk).delete()


def test_advisers_pass_the_advisers_only_level_system_does_not(org: Organisation) -> None:
    practice = Practice.objects.create(name="North Star CPA")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    adviser = User.objects.create_user("acc@northstar.ca", password="x" * 12, name="Acc")
    assignment.assigned_staff.add(
        PracticeMember.objects.create(practice=practice, user=adviser, role="accountant")
    )
    with org_context(org):
        LockDate.objects.filter(module="gl").update(date=None)
        system = LockedDocument(organisation=org, date=LOCK, status="approved")
        with pytest.raises(LockedPeriod):
            system.save()  # no user: stopped like everyone
        with audit_context(kind="user", user=adviser, label="Acc"):
            ok = LockedDocument(organisation=org, date=LOCK, status="approved")
            ok.save()
        assert LockedDocument.objects.filter(pk=ok.pk).exists()
