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

**States** (C-02-T09) — explicit transitions only, anything else raises ``IllegalTransition``
(``ledger.journal.illegal_transition``):

    Draft ──submit()──▶ Awaiting approval ──post_entry()──▶ Posted ──reverse()──▶ Reversed
      │                  │  ▲                                  ▲
      │                  └──┘ return_to_draft()                │
      └──────────────────── post_entry() ──────────────────────┘

``save_draft(spec)`` keeps a journal as a draft (validated, not checked against lock dates: a
draft in a locked period may be kept); ``submit`` sends it for approval (who may approve is
C-04); ``post_entry`` posts a draft or an approved entry through steps 1–6 with its stored lines;
``reverse`` (C-02-T10) is the only way out of Posted. Reversed is final.

Every module posts through this service — sales invoices, bills, payments, payroll, manual
journals (C-04), opening balances (C-05); nothing else writes ``JournalLine`` (import-linter
contract, C-02-T14).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.audit import service as audit
from numo9.contacts.models import Contact
from numo9.orgsettings.locks import acting_user
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import acting_practice, current_org, org_context
from numo9.tenancy.models import Organisation

from .models import JournalEntry, JournalLine, JournalStatus, LedgerError
from .periods import assert_can_post
from .sequence import allocate_journal_number, format_journal_number
from .validation import JournalSpec, LineSpec, ValidatedJournal, validate_journal

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


# ---- states (C-02-T09) ---------------------------------------------------------------------

#: The allowed transitions; Posted → Reversed only through ``reverse()`` (C-02-T10).
TRANSITIONS: dict[str, frozenset[str]] = {
    JournalStatus.DRAFT: frozenset({JournalStatus.AWAITING_APPROVAL, JournalStatus.POSTED}),
    JournalStatus.AWAITING_APPROVAL: frozenset({JournalStatus.DRAFT, JournalStatus.POSTED}),
    JournalStatus.POSTED: frozenset({JournalStatus.REVERSED}),
    JournalStatus.REVERSED: frozenset(),
}


class IllegalTransition(LedgerError):
    """A status change the state machine doesn't allow."""


def _status_label(status: str) -> str:
    return str(JournalStatus(status).label).lower()


def assert_transition(entry: JournalEntry, to: str) -> None:
    """Raise ``IllegalTransition`` unless ``entry.status → to`` is allowed."""
    if to not in TRANSITIONS.get(entry.status, frozenset()):
        raise IllegalTransition(
            _("%(journal)s is %(from)s: it can't become %(to)s."),
            code="ledger.journal.illegal_transition",
            params={
                "journal": str(entry),
                "from": _status_label(entry.status),
                "to": _status_label(to),
            },
        )


def _locked(entry: JournalEntry) -> JournalEntry:
    """The entry reloaded under a row lock (two people acting on it wait for each other)."""
    locked: JournalEntry = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    return locked


def _spec_of(entry: JournalEntry) -> JournalSpec:
    lines = entry.lines.order_by("line_no").select_related("account")
    return JournalSpec(
        date=entry.date,
        type=entry.type,
        narration=entry.narration,
        source_type=entry.source_type,
        source_id=entry.source_id,
        lines=tuple(
            LineSpec(
                account=line.account,
                debit=line.debit,
                credit=line.credit,
                book=line.book,
                contact=line.contact_id,
                tracking=line.tracking,
                description=line.description,
                tax_code=line.tax_code,
            )
            for line in lines
        ),
    )


def save_draft(
    spec: JournalSpec,
    *,
    entry: JournalEntry | None = None,
    organisation: Organisation | None = None,
    user: Any = ACTING,
) -> JournalEntry:
    """Create a draft from ``spec``, or replace a draft's header and lines (validated)."""
    organisation = _organisation(organisation)
    person = acting_user() if user is ACTING else user
    with org_context(organisation, acting_practice()), transaction.atomic():
        checked = validate_journal(spec, organisation)
        if entry is None:
            entry = JournalEntry(
                organisation=organisation,
                created_by=person if getattr(person, "is_authenticated", False) else None,
            )
        else:
            entry = _locked(entry)
            if entry.status != JournalStatus.DRAFT:
                raise IllegalTransition(
                    _("%(journal)s is %(status)s: only drafts can be edited."),
                    code="ledger.journal.not_draft",
                    params={"journal": str(entry), "status": _status_label(entry.status)},
                )
        entry.date, entry.type, entry.narration = spec.date, spec.type, spec.narration
        entry.source_type, entry.source_id = spec.source_type, str(spec.source_id or "")
        entry.book_scope = checked.book_scope
        entry.save()
        JournalLine.objects.filter(entry=entry).delete()
        JournalLine.objects.bulk_create(_lines(entry, checked))
        return entry


def _move(entry: JournalEntry, to: str) -> JournalEntry:
    with org_context(entry.organisation, acting_practice()), transaction.atomic():
        entry = _locked(entry)
        assert_transition(entry, to)
        entry.status = to
        entry.save()
        return entry


def submit(entry: JournalEntry) -> JournalEntry:
    """Draft → Awaiting approval."""
    return _move(entry, JournalStatus.AWAITING_APPROVAL)


def return_to_draft(entry: JournalEntry) -> JournalEntry:
    """Awaiting approval → Draft (sent back for changes)."""
    return _move(entry, JournalStatus.DRAFT)


def post_entry(
    entry: JournalEntry, *, user: Any = ACTING, module: str = LockModule.GL
) -> JournalEntry:
    """Draft or Awaiting approval → Posted: steps 1–6 of ``post_journal`` on its stored lines."""
    person = acting_user() if user is ACTING else user
    organisation = entry.organisation
    with org_context(organisation, acting_practice()), transaction.atomic():
        entry = _locked(entry)
        assert_transition(entry, JournalStatus.POSTED)
        spec = _spec_of(entry)
        checked = validate_journal(spec, organisation)
        assert_can_post(organisation, entry.date, person, module)
        if entry.book_scope != checked.book_scope:
            JournalEntry._base_manager.filter(pk=entry.pk).update(book_scope=checked.book_scope)
            entry.book_scope = checked.book_scope
        lines = list(entry.lines.order_by("line_no").select_related("account"))
        return _number_and_post(entry, lines, person, entry.status)
