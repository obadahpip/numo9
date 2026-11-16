"""The posting service (C-02-T08): the only code that writes journal entries' lines.

``post_journal(spec, user=…, module=…)`` posts a journal in **one transaction**:

1. **validate** — ``validate_journal`` (C-02-T06): every rule, every problem listed;
2. **period** — ``assert_can_post`` (C-02-T07): lock dates (the module's and the GL's) and
   closed periods, for the entry's date and the person;
3. **insert** — the entry as a draft, then its lines (``bulk_create``; the append-only trigger
   allows lines only while the entry is a draft, C-02-T04);
4. **sequence** — the organisation's next journal number (``allocate_journal_number``,
   C-02-T05): taken last, so the row lock on the sequence is held for as short a time as possible;
5. **status Posted** — number, ``posted_by``, ``posted_at``;
6. **audit** — one event ``ledger.journalentry.posted`` (A-04) with the number, date, type,
   source and every line (account, debit, credit, book, contact).

Any failure rolls the whole transaction back: no entry, no line, no number used (the next
posting gets it), no audit event.

Every module posts through this service — sales invoices, bills, payments, payroll, manual
journals (C-04), opening balances (C-05); nothing else writes ``JournalLine`` (import-linter
contract, C-02-T14).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from numo9.audit import service as audit
from numo9.contacts.models import Contact
from numo9.orgsettings.locks import acting_user
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import acting_practice, current_org, org_context
from numo9.tenancy.models import Organisation

from .models import JournalEntry, JournalLine, JournalStatus
from .periods import assert_can_post
from .sequence import allocate_journal_number, format_journal_number
from .validation import JournalSpec, ValidatedJournal, validate_journal

#: ``user`` not given: the person of the audit context (a request's user; None for a system job).
ACTING: Any = object()


def _organisation(organisation: Organisation | None) -> Organisation:
    active = current_org()
    organisation = organisation or active
    if organisation is None:
        raise ValueError("Post a journal inside org_context() or pass organisation=.")
    if active is not None and active.pk != organisation.pk:
        raise ValueError("Journals are posted in the active organisation only.")
    return organisation


def _contact_id(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, Contact):
        return int(value.pk)
    return int(value)


def _lines(entry: JournalEntry, checked: ValidatedJournal) -> list[JournalLine]:
    return [
        JournalLine(
            organisation_id=entry.organisation_id,
            entry=entry,
            line_no=line.line_no,
            account=line.account,
            debit=line.debit,
            credit=line.credit,
            book=line.book,
            contact_id=_contact_id(line.spec.contact),
            tracking=dict(line.spec.tracking or {}),
            description=" ".join((line.spec.description or "").split())[:500],
            tax_code=line.spec.tax_code or "",
        )
        for line in checked.lines
    ]


def _audit_lines(lines: list[JournalLine]) -> list[dict[str, Any]]:
    return [
        {
            "line": line.line_no,
            "account": {"id": str(line.account.public_id), "label": str(line.account)},
            "debit": f"{line.debit:.2f}",
            "credit": f"{line.credit:.2f}",
            "book": line.book,
            "contact": str(line.contact_id) if line.contact_id else None,
        }
        for line in lines
    ]


def _number_and_post(
    entry: JournalEntry, lines: list[JournalLine], user: Any, previous_status: str
) -> JournalEntry:
    """Steps 4–6 for an entry whose lines are written: number, Posted, audit event."""
    number = allocate_journal_number(entry.organisation)
    posted_at = timezone.now()
    posted_by = user if getattr(user, "is_authenticated", False) else None
    JournalEntry._base_manager.filter(pk=entry.pk).update(
        status=JournalStatus.POSTED,
        number=number,
        posted_at=posted_at,
        posted_by=posted_by,
        updated_at=posted_at,
    )
    entry.status, entry.number = JournalStatus.POSTED, number
    entry.posted_at, entry.posted_by = posted_at, posted_by
    audit.record(
        "ledger.journalentry.posted",
        obj=entry,
        changes={"status": [previous_status, JournalStatus.POSTED], "number": [None, number]},
        meta={
            "number": format_journal_number(entry.organisation, number),
            "date": entry.date.isoformat(),
            "type": entry.type,
            "source": {"type": entry.source_type, "id": entry.source_id}
            if entry.source_type
            else None,
            "reversal_of": entry.reversal_of.number if entry.reversal_of is not None else None,
            "lines": _audit_lines(lines),
        },
        actor=posted_by,
    )
    return entry


def post_journal(
    spec: JournalSpec,
    *,
    organisation: Organisation | None = None,
    user: Any = ACTING,
    module: str = LockModule.GL,
    reversal_of: JournalEntry | None = None,
) -> JournalEntry:
    """Validate, check the period, insert, number and post ``spec`` — all or nothing.

    ``module`` is the lock module of the posting's source (``ar`` for a sales invoice, ``ap`` for
    a bill…); ``user`` defaults to the audit context's person (advisers pass an advisers-only
    lock; a system job is stopped like everyone).
    """
    organisation = _organisation(organisation)
    person = acting_user() if user is ACTING else user
    with org_context(organisation, acting_practice()), transaction.atomic():
        checked = validate_journal(spec, organisation)
        assert_can_post(organisation, spec.date, person, module)
        entry = JournalEntry(
            organisation=organisation,
            date=spec.date,
            type=spec.type,
            narration=spec.narration,
            source_type=spec.source_type,
            source_id=str(spec.source_id or ""),
            book_scope=checked.book_scope,
            reversal_of=reversal_of,
            status=JournalStatus.DRAFT,
            created_by=person if getattr(person, "is_authenticated", False) else None,
        )
        # The draft is an intermediate row of this transaction: the posting event (below) is its
        # audit record, so the draft is inserted without a "created" event of its own.
        JournalEntry.objects.bulk_create([entry])
        lines = _lines(entry, checked)
        JournalLine.objects.bulk_create(lines)
        return _number_and_post(entry, lines, person, JournalStatus.DRAFT)
