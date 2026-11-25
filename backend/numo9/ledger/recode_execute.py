"""Find & recode — running a batch (C-07-T05): reverse and re-post each affected entry.

``create_batch(organisation, criteria, changes, user, selection=…)`` keeps a **draft**
``RecodeBatch`` — the search, the new coding and the lines chosen in the preview (``selection``:
``[{"entry", "line_no", "fingerprint"}]``; ``None`` = every line the search finds). The
preview's checks run first: a batch that would change debits or credits, or that changes tax
codes without ``confirm_tax`` (C-07-T04 ``needs_confirmation``), is refused.

``execute(batch, user)`` runs it — **now** for up to ``ASYNC_THRESHOLD`` (200) lines, otherwise
as the background job ``numo9.ledger.recode`` (A-08: idempotent per batch, progress in the job
tray). Either way ``run_batch`` does the work:

1. the search runs again and the exclusion engine (C-03) splits the lines; only chosen,
   included lines that the new coding changes are recoded;
2. for each **entry** (document) — in one transaction, the entry row locked: ``reverse()`` the
   entry on its own date, then ``post_journal()`` it again on that date with every line copied
   and the chosen lines carrying the new coding (same type, journal type, source, narration,
   attachments and automatic reversal; ``caller="recode"`` — no approval gate, no cash guard);
   the documents that pointed at the entry (an invoice's ``journal_entry``…) point at the
   re-post; one ``RecodeLineChange`` per recoded line (before / after / amounts / both entries);
2b. **optimistic re-validation** (C-07-T06) — each chosen line carries the ``fingerprint`` the
   preview showed; a line that changed since (recoded or reversed by someone else, its document
   voided…) is a **conflict**: its entry is not recoded and is listed in ``batch.problems``
   (``ledger.recode.conflict``), whether the run no longer finds the line or finds it changed
   once the entry row is locked;
3. an entry whose posting is refused (a rule of the new account, a lock set meanwhile…) keeps
   its coding and is listed in ``batch.problems``; the others go on;
4. ``progress`` counts the lines done (the job tray too); the batch ends **Completed** with
   ``line_count`` = lines recoded, or **Failed** with ``error`` when something unexpected stops
   it (the entries recoded until then stay recoded and can be undone).

Recoding never changes an amount: each re-post carries the original's debits and credits.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import APIException

from numo9.audit import service as audit
from numo9.jobs.queues import REPORTS
from numo9.jobs.runtime import current_job, org_job, report_progress, start_job
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import org_context

from .models import (
    Account,
    JournalEntry,
    JournalLine,
    JournalStatus,
    RecodeBatch,
    RecodeLineChange,
    RecodeStatus,
)
from .recode_exclusions import MODULE_OF_TYPE
from .recode_preview import Changes, PreviewLine, clean_changes, fingerprint, preview
from .sequence import format_journal_number
from .validation import JournalSpec, LineSpec

ASYNC_THRESHOLD = 200
JOB = "numo9.ledger.recode"


class RecodeRefused(ValidationError):
    """The batch can't run (not a draft, nothing to recode, tax change not confirmed…)."""


def _refused(message: str, code: str, **params: Any) -> RecodeRefused:
    return RecodeRefused(message, code=code, params=params)


def _key_of(row: dict[str, Any]) -> tuple[str, int]:
    return (str(row.get("entry", "")), int(row.get("line_no", 0)))


def clean_selection(selection: Any) -> list[dict[str, Any]] | None:
    if selection is None:
        return None
    if not isinstance(selection, list) or not all(
        isinstance(row, dict) and "entry" in row and "line_no" in row for row in selection
    ):
        raise ValidationError(
            {
                "selection": ValidationError(
                    _("Choose the lines as the preview lists them (entry and line)."),
                    code="ledger.recode.selection_invalid",
                )
            }
        )
    out = []
    for row in selection:
        try:
            out.append(
                {
                    "entry": str(row["entry"]),
                    "line_no": int(row["line_no"]),
                    "fingerprint": str(row.get("fingerprint") or ""),
                }
            )
        except (TypeError, ValueError):
            raise ValidationError(
                {
                    "selection": ValidationError(
                        _("Choose the lines as the preview lists them (entry and line)."),
                        code="ledger.recode.selection_invalid",
                    )
                }
            ) from None
    return out


# ---- the plan: what the batch recodes now ------------------------------------------------------


def _plan(batch: RecodeBatch, user: Any) -> tuple[Changes, list[PreviewLine], list[Any]]:
    """The preview of the batch as the books are now, narrowed to the chosen lines."""
    organisation = batch.organisation
    changes = clean_changes(organisation, batch.changes)
    keys = {_key_of(row) for row in batch.selection} if batch.selection is not None else None
    built = preview(organisation, batch.criteria, batch.changes, user, keys=keys)
    return changes, built.lines, built.excluded


def create_batch(
    organisation: Any,
    criteria: Any,
    changes: Any,
    user: Any,
    *,
    selection: Any = None,
    name: str = "",
    confirm_tax: bool = False,
) -> RecodeBatch:
    """A draft batch, checked like the preview (raises when nothing would be recoded)."""
    with org_context(organisation):
        chosen = clean_selection(selection)
        keys = {_key_of(row) for row in chosen} if chosen is not None else None
        built = preview(organisation, criteria, changes, user, keys=keys)
        rows = built.lines
        if not rows:
            raise _refused(
                _("Nothing to recode: no chosen line would change."), "ledger.recode.nothing"
            )
        if built.needs_confirmation and not confirm_tax:
            raise _refused(
                _(
                    "Changing the tax code changes the tax these lines carry by %(delta)s: "
                    "confirm the tax change to go on."
                ),
                "ledger.recode.confirm_tax",
                delta=f"{built.tax_delta:.2f}",
            )
        batch: RecodeBatch = RecodeBatch.objects.create(
            organisation=organisation,
            name=name[:200],
            criteria=criteria,
            changes=changes,
            selection=chosen,
            line_count=len(rows),
            excluded_count=len(built.excluded),
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        return batch


# ---- running ------------------------------------------------------------------------------------


def _documents(entry: JournalEntry) -> list[Any]:
    """The documents attached to the entry: the re-post carries them too (A-06)."""
    from django.contrib.contenttypes.models import ContentType

    from numo9.files.models import Attachment

    rows = Attachment.objects.filter(
        content_type=ContentType.objects.get_for_model(JournalEntry),
        object_public_id=entry.public_id,
        deleted_at__isnull=True,
        document__deleted_at__isnull=True,
    ).select_related("document")
    return list({row.document_id: row.document for row in rows}.values())


def repoint_documents(original: JournalEntry, repost: JournalEntry) -> None:
    """Documents whose posting is ``original`` (an invoice's, a bill's, a bank transaction's
    ``journal_entry``) now point at ``repost``: voiding the document later reverses the live
    entry, not the one the recode reversed. Every document posts with its ``source_type``, so an
    entry without one (a manual journal) has none to repoint."""
    if not original.source_type:
        return
    for relation in JournalEntry._meta.related_objects:
        if relation.one_to_one and relation.field.name == "journal_entry":
            model = relation.related_model
            model._base_manager.filter(journal_entry=original).update(journal_entry=repost)


def _contact_pk(organisation: Any, public_id: Any) -> int | None:
    if not public_id:
        return None
    from numo9.contacts.models import Contact

    return int(
        Contact._base_manager.filter(organisation=organisation, public_id=public_id)
        .values_list("pk", flat=True)
        .get()
    )


def _line_spec(line: JournalLine, after: dict[str, Any] | None, changes: Changes) -> LineSpec:
    if after is None:
        return LineSpec(
            account=line.account,
            debit=line.debit,
            credit=line.credit,
            book=line.book,
            contact=line.contact_id,
            tracking=dict(line.tracking or {}),
            description=line.description,
            tax_code=line.tax_code,
        )
    account: Account = changes.account if "account" in changes.values else line.account  # type: ignore[assignment]
    if "contact" in changes.values:
        contact = changes.contact.pk if changes.contact is not None else None
    else:
        contact = line.contact_id
    return LineSpec(
        account=account,
        debit=line.debit,
        credit=line.credit,
        book=line.book,
        contact=contact,
        tracking=dict(after.get("tracking") or {}),
        description=line.description,
        tax_code=after.get("tax_code") or "",
    )


def recode_entry(
    batch: RecodeBatch,
    entry: JournalEntry,
    rows: list[PreviewLine],
    changes: Changes,
    person: Any,
    fingerprints: dict[tuple[str, int], str] | None = None,
) -> list[RecodeLineChange]:
    """Reverse ``entry`` and post it again with ``rows`` recoded — one transaction."""
    from .services import RECODE_CALLER, post_journal, reverse

    organisation = batch.organisation
    with transaction.atomic():
        locked = JournalEntry.objects.select_for_update().get(pk=entry.pk)
        lines = list(locked.lines.order_by("line_no").select_related("account", "entry"))
        if fingerprints is not None:  # C-07-T06: the lines as the preview showed them
            for line in lines:
                expected = fingerprints.get((str(locked.public_id), line.line_no))
                if expected and expected != fingerprint(line):
                    raise RecodeConflict(locked, [line.line_no])
        if locked.status != JournalStatus.POSTED:
            raise RecodeConflict(locked, [r.line.line_no for r in rows])
        module = MODULE_OF_TYPE.get(locked.type, LockModule.GL)
        number = format_journal_number(organisation, locked.number)
        label = batch.name or str(batch.public_id)[:8]
        reversal = reverse(
            locked,
            date=locked.date,
            narration=_("Recode %(batch)s: reversal of %(number)s")
            % {"batch": label, "number": number},
            user=person,
            module=module,
        )
        recoded = {r.line.line_no: r for r in rows}
        spec = JournalSpec(
            date=locked.date,
            type=locked.type,
            journal_type=locked.journal_type,
            narration=locked.narration,
            source_type=locked.source_type,
            source_id=locked.source_id,
            auto_reverse_on=locked.auto_reverse_on,
            lines=tuple(
                _line_spec(
                    line,
                    recoded[line.line_no].after if line.line_no in recoded else None,
                    changes,
                )
                for line in lines
            ),
        )
        repost = post_journal(
            spec,
            organisation=organisation,
            user=person,
            module=module,
            caller=RECODE_CALLER,
            attachments=_documents(locked),
        )
        repoint_documents(locked, repost)
        made = RecodeLineChange.objects.bulk_create(
            [
                RecodeLineChange(
                    organisation=organisation,
                    batch=batch,
                    entry=locked,
                    line_no=row.line.line_no,
                    line_id=row.line.id,
                    before=row.before,
                    after=row.after,
                    debit=row.line.debit,
                    credit=row.line.credit,
                    fingerprint=fingerprint(row.line),
                    reversal_entry=reversal,
                    repost_entry=repost,
                )
                for row in sorted(rows, key=lambda r: r.line.line_no)
            ]
        )
        return made


class RecodeConflict(Exception):
    """The entry changed since the preview (C-07-T06): its lines are not recoded."""

    def __init__(self, entry: JournalEntry, lines: list[int]) -> None:
        super().__init__(entry.pk)
        self.entry = entry
        self.lines = lines


def _problem(entry: JournalEntry, lines: Iterable[int], code: str, message: str) -> dict[str, Any]:
    return {
        "entry": str(entry.public_id),
        "number": format_journal_number(entry.organisation, entry.number),
        "lines": sorted(lines),
        "code": code,
        "message": message[:500],
    }


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    if not code and isinstance(error, APIException):
        detail = getattr(error, "detail", None)
        code = detail.get("code") if isinstance(detail, dict) else error.default_code
    if not code and isinstance(error, ValidationError):
        codes = [e.code for e in error.error_list if getattr(e, "code", None)]
        code = codes[0] if codes else None
    return str(code or "ledger.recode.refused")


def _message(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return " ".join(error.messages)
    return str(getattr(error, "detail", None) or error)


def run_batch(batch: RecodeBatch, user: Any) -> RecodeBatch:
    """Recode every entry of the batch (module docstring, steps 1–4)."""
    organisation = batch.organisation
    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(organisation):
        batch.refresh_from_db()
        if batch.status not in (RecodeStatus.DRAFT, RecodeStatus.RUNNING):
            return batch
        changes, rows, excluded = _plan(batch, person)
        by_entry: dict[int, list[PreviewLine]] = defaultdict(list)
        for row in rows:
            by_entry[row.line.entry_id].append(row)
        planned = sum(len(v) for v in by_entry.values())
        fingerprints = (
            {_key_of(row): row["fingerprint"] for row in batch.selection if row.get("fingerprint")}
            if batch.selection is not None
            else None
        )
        missing = _missing(batch, rows)
        RecodeBatch.objects.filter(pk=batch.pk).update(
            status=RecodeStatus.RUNNING,
            line_count=max(planned, 0),
            excluded_count=len(excluded),
            progress=0,
            problems=missing,
            executed_by=person,
            executed_at=timezone.now(),
            updated_at=timezone.now(),
        )
        problems = list(missing)
        done = recoded = 0
        try:
            for entry_rows in by_entry.values():
                entry = entry_rows[0].line.entry
                try:
                    made = recode_entry(batch, entry, entry_rows, changes, person, fingerprints)
                    recoded += len(made)
                except RecodeConflict as conflict:
                    problems.append(
                        _problem(
                            conflict.entry,
                            conflict.lines,
                            "ledger.recode.conflict",
                            _(
                                "This entry changed after the preview: its lines were not "
                                "recoded. Preview again to include them."
                            ),
                        )
                    )
                except (ValidationError, APIException) as error:
                    problems.append(
                        _problem(
                            entry,
                            [r.line.line_no for r in entry_rows],
                            _error_code(error),
                            _message(error),
                        )
                    )
                done += len(entry_rows)
                RecodeBatch.objects.filter(pk=batch.pk).update(
                    progress=done, problems=problems, updated_at=timezone.now()
                )
                if current_job() is not None:
                    report_progress(done, planned)
        except Exception as error:
            RecodeBatch.objects.filter(pk=batch.pk).update(
                status=RecodeStatus.FAILED,
                line_count=max(recoded, 0),
                progress=recoded,
                problems=problems,
                error=str(error)[:2000],
                updated_at=timezone.now(),
            )
            raise
        RecodeBatch.objects.filter(pk=batch.pk).update(
            status=RecodeStatus.COMPLETED,
            line_count=recoded,
            progress=recoded,
            problems=problems,
            updated_at=timezone.now(),
        )
        batch.refresh_from_db()
        audit.record(
            "ledger.recodebatch.executed",
            obj=batch,
            meta={
                "lines": recoded,
                "entries": batch.lines.values("entry").distinct().count(),
                "excluded": batch.excluded_count,
                "problems": len(problems),
                "changes": batch.changes,
            },
            actor=person,
        )
        return batch


def _missing(batch: RecodeBatch, rows: list[PreviewLine]) -> list[dict[str, Any]]:
    """Chosen lines the run no longer finds (recoded, reversed or excluded since): conflicts."""
    if batch.selection is None:
        return []
    found = {(str(r.line.entry.public_id), r.line.line_no) for r in rows}
    gone: dict[str, list[int]] = defaultdict(list)
    for row in batch.selection:
        k = _key_of(row)
        if k not in found:
            gone[k[0]].append(k[1])
    if not gone:
        return []
    entries = {
        str(e.public_id): e
        for e in JournalEntry._base_manager.filter(
            organisation=batch.organisation, public_id__in=list(gone)
        )
    }
    return [
        _problem(
            entries[pid],
            nos,
            "ledger.recode.conflict",
            _(
                "This line can't be recoded any more (it changed, or is excluded now) — preview "
                "again."
            ),
        )
        for pid, nos in gone.items()
        if pid in entries
    ]


@org_job(name=JOB, queue=REPORTS, max_retries=0, atomic=False)
def recode_job(*, org_id: str, batch_id: str, user_id: int | None = None) -> dict[str, Any]:
    from numo9.accounts.models import User

    batch = RecodeBatch.objects.get(public_id=batch_id)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    done = run_batch(batch, user)
    return {"batch": str(done.public_id), "lines": done.line_count, "status": done.status}


def execute(batch: RecodeBatch, user: Any) -> RecodeBatch:
    """Run the draft batch now (≤ ``ASYNC_THRESHOLD`` lines) or start its background job."""
    if batch.status != RecodeStatus.DRAFT:
        raise _refused(
            _("This recode has run already."), "ledger.recode.not_draft", status=batch.status
        )
    if batch.line_count <= ASYNC_THRESHOLD:
        return run_batch(batch, user)
    with org_context(batch.organisation), transaction.atomic():
        run = start_job(
            recode_job,
            organisation=batch.organisation,
            key=f"recode:{batch.public_id}",
            created_by=user if getattr(user, "is_authenticated", False) else None,
            batch_id=str(batch.public_id),
            user_id=user.pk if getattr(user, "is_authenticated", False) else None,
        )
        RecodeBatch.objects.filter(pk=batch.pk).update(
            status=RecodeStatus.RUNNING, job_run=run, updated_at=timezone.now()
        )
    batch.refresh_from_db()
    return batch
