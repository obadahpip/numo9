"""Shared helpers for the chart-of-accounts tests (C-01)."""

from __future__ import annotations

from typing import Any

from numo9.ledger.models import SUBTYPE_TYPE, Account
from numo9.tenancy.models import Organisation


def account(
    organisation: Organisation,
    code: str,
    name: str = "",
    subtype: str = "operating_expense",
    **fields: Any,
) -> Account:
    """Create and save an account (runs every save rule)."""
    item = Account(
        organisation=organisation,
        code=code,
        name_i18n={"en-ca": name or f"Account {code}"},
        type=SUBTYPE_TYPE[subtype],
        subtype=subtype,
        **fields,
    )
    item.save()
    return item


def post_for_test(
    spec: Any, *, organisation: Organisation | None = None, reversal_of: Any = None
) -> Any:
    """Validate and post a journal the way the engine will (C-02-T08): lines written while the
    entry is a draft, then number, status Posted and posting time in the same transaction.

    Test fixture only — production code posts with ``numo9.ledger.services.post_journal``.
    """
    from django.db import transaction
    from django.utils import timezone

    from numo9.ledger.models import JournalEntry, JournalLine, JournalStatus
    from numo9.ledger.sequence import allocate_journal_number
    from numo9.ledger.validation import validate_journal
    from numo9.tenancy.context import current_org

    org = organisation or current_org()
    assert org is not None
    checked = validate_journal(spec, org)
    with transaction.atomic():
        entry = JournalEntry(
            organisation=org,
            date=spec.date,
            type=spec.type,
            narration=spec.narration,
            book_scope=checked.book_scope,
            reversal_of=reversal_of,
        )
        entry.save()
        JournalLine.objects.bulk_create(
            [
                JournalLine(
                    organisation=org,
                    entry=entry,
                    line_no=line.line_no,
                    account=line.account,
                    debit=line.debit,
                    credit=line.credit,
                    book=line.book,
                )
                for line in checked.lines
            ]
        )
        number = allocate_journal_number(org)
        JournalEntry.objects.filter(pk=entry.pk).update(
            status=JournalStatus.POSTED, number=number, posted_at=timezone.now()
        )
        if reversal_of is not None:
            JournalEntry.objects.filter(pk=reversal_of.pk).update(status=JournalStatus.REVERSED)
    entry.refresh_from_db()
    return entry
