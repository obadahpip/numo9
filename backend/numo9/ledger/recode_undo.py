"""Find & recode — undo (C-07-T07): put every line of a batch back the way it was.

``undo(batch, user, reason=…)`` reverses the batch's re-posts and posts each entry again with
the lines' coding ``before`` (append-only: nothing is deleted or edited), **latest entry first**,
in one transaction:

- only a **Completed** (or Failed, for the entries it recoded) batch is undone, once;
- a batch whose lines were recoded again by a later batch is undone after it — the later batch
  first (``ledger.recode.undo_later_batch``, naming it);
- every re-post must still be live and its period open: an entry dated on or before a lock date
  that applies to the person, inside a closed year or — when the batch changed tax codes — a
  filed tax period, or a re-post reversed or replaced since (its document voided or revised),
  refuses the whole undo (``ledger.recode.undo_refused``) with the list of entries and why
  (``RecodeUndoRefused.blocked``, the exclusion engine's reasons, C-07-T03);
- the documents that pointed at the re-post point at the restored entry;
- the batch becomes **Undone** (``undone_by`` / ``undone_at`` / ``undo_reason``), audited.

``undo_blockers(batch, user)`` lists what would refuse the undo — the UI disables Undo with that
reason (C-07-T13).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.audit import service as audit
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import org_context

from .models import (
    Account,
    JournalEntry,
    JournalLine,
    RecodeBatch,
    RecodeLineChange,
    RecodeStatus,
)
from .recode_exclusions import MODULE_OF_TYPE, reasons
from .recode_execute import _documents, repoint_documents
from .sequence import format_journal_number
from .validation import JournalSpec, LineSpec

UNDOABLE = (RecodeStatus.COMPLETED, RecodeStatus.FAILED)


class RecodeUndoRefused(ValidationError):
    """The batch can't be undone; ``blocked`` lists the entries in the way and why."""

    def __init__(
        self, message: str, *, code: str, params: dict[str, Any] | None = None, blocked: Any = ()
    ) -> None:
        super().__init__(message, code=code, params=params or {})
        self.blocked = list(blocked)


def _changes(batch: RecodeBatch) -> list[RecodeLineChange]:
    return list(
        RecodeLineChange.objects.filter(batch=batch, undo_repost_entry__isnull=True)
        .select_related("repost_entry", "entry")
        .order_by("-repost_entry_id", "line_no")
    )


def _live(change: RecodeLineChange) -> int | None:
    """The entry now carrying the change's line: its re-post, or — when a later batch recoded
    the re-post and was undone — the entry that undo restored (followed down the chain)."""
    current = change.repost_entry_id
    for _step in range(1000):
        if current is None:
            return None
        later = (
            RecodeLineChange.objects.filter(
                entry_id=current, line_no=change.line_no, batch__status=RecodeStatus.UNDONE
            )
            .exclude(undo_repost_entry__isnull=True)
            .order_by("-pk")
            .values_list("undo_repost_entry_id", flat=True)
            .first()
        )
        if later is None:
            return current
        current = later
    return current


def _targets(changes: list[RecodeLineChange]) -> dict[int, list[RecodeLineChange]]:
    """The live entries to reverse and post again, each with its batch lines."""
    out: dict[int, list[RecodeLineChange]] = defaultdict(list)
    for change in changes:
        live = _live(change)
        if live is not None:
            out[live].append(change)
    return dict(out)


def _later_batch(batch: RecodeBatch, reposts: set[int]) -> RecodeBatch | None:
    """A batch that recoded one of this batch's re-posts again and is still in force."""
    later = (
        RecodeLineChange.objects.filter(entry_id__in=reposts)
        .exclude(batch=batch)
        .exclude(batch__status=RecodeStatus.UNDONE)
        .select_related("batch")
        .order_by("-batch_id")
        .first()
    )
    return later.batch if later is not None else None


def undo_blockers(batch: RecodeBatch, user: Any = None) -> list[dict[str, Any]]:
    """Every entry that stops the undo, with its reason (``[]`` → the batch can be undone)."""
    organisation = batch.organisation
    with org_context(organisation):
        changes = _changes(batch)
        reposts = set(_targets(changes))
        later = _later_batch(batch, reposts)
        out: list[dict[str, Any]] = []
        if later is not None:
            out.append(
                {
                    "entry": None,
                    "number": None,
                    "code": "later_batch",
                    "message": _(
                        "Lines of this recode were recoded again by “%(batch)s”: undo it first."
                    )
                    % {"batch": str(later)},
                    "detail": {"batch": str(later.public_id)},
                }
            )
        lines = list(
            JournalLine.objects.filter(entry_id__in=reposts).select_related("entry", "account")
        )
        tax_changed = any(c.before.get("tax_code") != c.after.get("tax_code") for c in changes)
        found = reasons(organisation, lines, {"tax_code": ""} if tax_changed else {}, user)
        seen: set[int] = set()
        for line in lines:
            reason = found.get((line.entry_id, line.line_no))
            if reason is None or line.entry_id in seen:
                continue
            if reason.code == "system_journal":
                continue
            seen.add(line.entry_id)
            out.append(
                {
                    "entry": str(line.entry.public_id),
                    "number": format_journal_number(organisation, line.entry.number),
                    "date": line.entry.date.isoformat(),
                    **reason.as_dict(),
                }
            )
        return out


def _account(organisation: Any, public_id: Any, cache: dict[str, Account]) -> Account:
    key = str(public_id)
    if key not in cache:
        cache[key] = Account._base_manager.get(organisation=organisation, public_id=key)
    return cache[key]


def _contact(organisation: Any, public_id: Any, cache: dict[str, int | None]) -> int | None:
    if not public_id:
        return None
    from numo9.contacts.models import Contact

    key = str(public_id)
    if key not in cache:
        cache[key] = int(
            Contact._base_manager.filter(organisation=organisation, public_id=key)
            .values_list("pk", flat=True)
            .get()
        )
    return cache[key]


def _restore(
    batch: RecodeBatch, repost: JournalEntry, rows: list[RecodeLineChange], person: Any
) -> None:
    """Reverse ``repost`` and post it again with ``rows`` back to their coding ``before``."""
    from .services import RECODE_CALLER, post_journal, reverse

    organisation = batch.organisation
    locked = JournalEntry.objects.select_for_update().get(pk=repost.pk)
    module = MODULE_OF_TYPE.get(locked.type, LockModule.GL)
    number = format_journal_number(organisation, locked.number)
    label = batch.name or str(batch.public_id)[:8]
    reversal = reverse(
        locked,
        date=locked.date,
        narration=_("Undo of recode %(batch)s: reversal of %(number)s")
        % {"batch": label, "number": number},
        user=person,
        module=module,
    )
    before = {row.line_no: row.before for row in rows}
    accounts: dict[str, Account] = {}
    contacts: dict[str, int | None] = {}
    specs = []
    for line in locked.lines.order_by("line_no").select_related("account"):
        coding = before.get(line.line_no)
        if coding is None:
            specs.append(
                LineSpec(
                    account=line.account,
                    debit=line.debit,
                    credit=line.credit,
                    book=line.book,
                    contact=line.contact_id,
                    tracking=dict(line.tracking or {}),
                    description=line.description,
                    tax_code=line.tax_code,
                )
            )
            continue
        specs.append(
            LineSpec(
                account=_account(organisation, coding["account"], accounts),
                debit=line.debit,
                credit=line.credit,
                book=line.book,
                contact=_contact(organisation, coding.get("contact"), contacts),
                tracking=dict(coding.get("tracking") or {}),
                description=line.description,
                tax_code=coding.get("tax_code") or "",
            )
        )
    restored = post_journal(
        JournalSpec(
            date=locked.date,
            type=locked.type,
            journal_type=locked.journal_type,
            narration=locked.narration,
            source_type=locked.source_type,
            source_id=locked.source_id,
            auto_reverse_on=locked.auto_reverse_on,
            lines=tuple(specs),
        ),
        organisation=organisation,
        user=person,
        module=module,
        caller=RECODE_CALLER,
        attachments=_documents(locked),
    )
    repoint_documents(locked, restored)
    RecodeLineChange.objects.filter(pk__in=[row.pk for row in rows]).update(
        undo_reversal_entry=reversal, undo_repost_entry=restored
    )


def undo(batch: RecodeBatch, user: Any, *, reason: str = "") -> RecodeBatch:
    """Undo the whole batch (module docstring) — all or nothing."""
    organisation = batch.organisation
    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(organisation), transaction.atomic():
        locked: RecodeBatch = RecodeBatch.objects.select_for_update().get(pk=batch.pk)
        if locked.status not in UNDOABLE or not locked.lines.exists():
            raise RecodeUndoRefused(
                _("Only a recode that ran can be undone, once."),
                code="ledger.recode.undo_not_allowed",
                params={"status": locked.status},
            )
        blocked = undo_blockers(locked, person)
        if blocked:
            if any(b["code"] == "later_batch" for b in blocked):
                first = next(b for b in blocked if b["code"] == "later_batch")
                raise RecodeUndoRefused(
                    first["message"],
                    code="ledger.recode.undo_later_batch",
                    params=first["detail"],
                    blocked=blocked,
                )
            raise RecodeUndoRefused(
                _(
                    "This recode can't be undone: %(count)d entries are in locked, closed or "
                    "filed periods, or changed since — %(entries)s."
                ),
                code="ledger.recode.undo_refused",
                params={
                    "count": len(blocked),
                    "entries": ", ".join(f"{b['number']} ({b['code']})" for b in blocked),
                },
                blocked=blocked,
            )
        by_repost = _targets(_changes(locked))
        for repost_id in sorted(by_repost, reverse=True):  # latest entry first
            _restore(locked, JournalEntry.objects.get(pk=repost_id), by_repost[repost_id], person)
        now = timezone.now()
        RecodeBatch.objects.filter(pk=locked.pk).update(
            status=RecodeStatus.UNDONE,
            undone_by=person,
            undone_at=now,
            undo_reason=reason[:2000],
            updated_at=now,
        )
        locked.refresh_from_db()
        audit.record(
            "ledger.recodebatch.undone",
            obj=locked,
            changes={"status": [batch.status, RecodeStatus.UNDONE]},
            meta={
                "lines": sum(len(v) for v in by_repost.values()),
                "entries": len(by_repost),
                "reason": reason[:500],
            },
            actor=person,
        )
        return locked
