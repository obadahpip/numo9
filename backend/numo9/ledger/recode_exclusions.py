"""Find & recode — the exclusion engine (C-07-T03): which found lines can't be recoded, and why.

Recoding reverses an entry and re-posts it with the new coding on the entry's own date
(append-only, C-07-T05), so a line is **excluded**, with a reason code, when:

- ``locked`` — the entry's date is on or before a lock date that applies to the person (A-05):
  the GL lock, or the lock of the entry's module (sales → AR, purchases → AP, payments → bank,
  payroll);
- ``closed_period`` — the date is inside a closed fiscal year (C-06);
- ``filed_period`` — the date is inside a filed or paid GST/HST or QST period and the line carries
  a tax code or the recode changes tax codes: a filed return can't move (the tax app's check);
- ``voided_document`` — the posting, or the reversal, of a voided document (the documents' apps:
  invoice, credit note, bill);
- ``superseded_revision`` — a reversed posting of a document that has posted again since (a
  revised document: only its current revision is recoded), or the reversal of one;
- ``reversed`` — any other reversed entry, or reversal;
- ``system_journal`` — a system journal (Closing, Payroll, Depreciation — C-03-T01): its own
  module owns its coding.

The first reason found, in that order, is the line's. ``split(organisation, lines, changes,
user)`` → ``(included, excluded)`` with ``excluded`` a list of ``Excluded(line, reason)``;
``Reason`` carries the code, a message and the detail (the lock, the period, the document).

Other apps add their checks with ``register_exclusion(check)`` — ``check(organisation, lines,
changes, user) -> {(entry_id, line_no): Reason}`` — under a code of the table; the engine keeps
the table's order whoever registered first.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from django.utils.translation import gettext as _

from numo9.orgsettings.locks import check_lock
from numo9.orgsettings.models import LockModule

from .models import SYSTEM_CATEGORIES, JournalEntry, JournalStatus, JournalType
from .periods import closed_period

ORDER = (
    "locked",
    "closed_period",
    "filed_period",
    "voided_document",
    "superseded_revision",
    "reversed",
    "system_journal",
)
MODULE_OF_TYPE = {
    JournalType.SALES: LockModule.AR,
    JournalType.PURCHASE: LockModule.AP,
    JournalType.PAYMENT: LockModule.BANK,
    JournalType.PAYROLL: LockModule.PAYROLL,
}


@dataclass(frozen=True)
class Reason:
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            **({"detail": self.detail} if self.detail else {}),
        }


@dataclass(frozen=True)
class Excluded:
    line: Any
    reason: Reason


Key = tuple[int, int]
Check = Callable[[Any, Sequence[Any], dict[str, Any], Any], dict[Key, Reason]]
_checks: list[Check] = []


def register_exclusion(check: Check) -> Check:
    if check not in _checks:
        _checks.append(check)
    return check


def unregister_exclusion(check: Check) -> None:
    if check in _checks:
        _checks.remove(check)


def key(line: Any) -> Key:
    return (line.entry_id, line.line_no)


def _locks(
    organisation: Any, lines: Sequence[Any], changes: dict[str, Any], user: Any
) -> dict[Key, Reason]:
    out: dict[Key, Reason] = {}
    seen: dict[tuple[Any, str], Any] = {}
    for line in lines:
        entry = line.entry
        module = MODULE_OF_TYPE.get(entry.type, LockModule.GL)
        probe = (entry.date, module)
        if probe not in seen:
            seen[probe] = check_lock(organisation, module, entry.date, user)
        violation = seen[probe]
        if violation is not None:
            out[key(line)] = Reason("locked", violation.message(), violation.as_dict())
    return out


def _closed(
    organisation: Any, lines: Sequence[Any], changes: dict[str, Any], user: Any
) -> dict[Key, Reason]:
    out: dict[Key, Reason] = {}
    seen: dict[Any, Any] = {}
    for line in lines:
        day = line.entry.date
        if day not in seen:
            seen[day] = closed_period(organisation, day)
        period = seen[day]
        if period is not None:
            out[key(line)] = Reason("closed_period", period.message(), period.as_dict())
    return out


def _source(entry: Any) -> tuple[str, str] | None:
    return (entry.source_type, entry.source_id) if entry.source_type and entry.source_id else None


def _reversals(
    organisation: Any, lines: Sequence[Any], changes: dict[str, Any], user: Any
) -> dict[Key, Reason]:
    """Reversed postings and reversals: superseded when the document posted again since."""
    entries = {line.entry_id: line.entry for line in lines}
    originals = {
        e.pk: e
        for e in JournalEntry.objects.filter(
            pk__in=[e.reversal_of_id for e in entries.values() if e.reversal_of_id]
        )
    }
    out: dict[Key, Reason] = {}
    for line in lines:
        entry = line.entry
        original = originals.get(entry.reversal_of_id) if entry.reversal_of_id else None
        if original is None and entry.status != JournalStatus.REVERSED:
            continue
        posting = original or entry
        source = _source(posting)
        later = source is not None and (
            JournalEntry.objects.filter(
                organisation=organisation,
                source_type=source[0],
                source_id=source[1],
                status=JournalStatus.POSTED,
                reversal_of__isnull=True,
                pk__gt=posting.pk,
            ).exists()
        )
        if later:
            out[key(line)] = Reason(
                "superseded_revision",
                _("The document was revised since: only its current revision can be recoded."),
                {"source_type": source[0], "source_id": source[1]} if source else {},
            )
        elif original is not None:
            out[key(line)] = Reason(
                "reversed",
                _("This entry reverses journal %(number)s: recode the original instead.")
                % {"number": original.number},
                {"reverses": original.number},
            )
        else:
            out[key(line)] = Reason(
                "reversed", _("This entry was reversed: there is nothing to recode."), {}
            )
    return out


def _system(
    organisation: Any, lines: Sequence[Any], changes: dict[str, Any], user: Any
) -> dict[Key, Reason]:
    return {
        key(line): Reason(
            "system_journal",
            _("A %(type)s journal is coded by its own module: it can't be recoded here.")
            % {"type": line.entry.get_journal_type_display()},
            {"journal_type": line.entry.journal_type},
        )
        for line in lines
        if line.entry.journal_type in SYSTEM_CATEGORIES
    }


BUILT_IN: tuple[Check, ...] = (_locks, _closed, _reversals, _system)


def reasons(
    organisation: Any, lines: Sequence[Any], changes: dict[str, Any] | None = None, user: Any = None
) -> dict[Key, Reason]:
    """Every exclusion found, the first reason (``ORDER``) kept per line."""
    changes = changes or {}
    found: dict[Key, Reason] = {}
    for check in (*BUILT_IN, *_checks):
        for k, reason in check(organisation, lines, changes, user).items():
            current = found.get(k)
            if current is None or ORDER.index(reason.code) < ORDER.index(current.code):
                found[k] = reason
    return found


def split(
    organisation: Any, lines: Iterable[Any], changes: dict[str, Any] | None = None, user: Any = None
) -> tuple[list[Any], list[Excluded]]:
    rows = list(lines)
    found = reasons(organisation, rows, changes, user)
    included = [line for line in rows if key(line) not in found]
    excluded = [Excluded(line, found[key(line)]) for line in rows if key(line) in found]
    return included, excluded


def voided_documents(source_type: str, model: Any, label: Any, void_status: str = "void") -> Check:
    """A check excluding the entries of ``model`` documents (source ``source_type``, public id)
    that are void — their posting and its reversal."""

    def check(
        organisation: Any, lines: Sequence[Any], changes: dict[str, Any], user: Any
    ) -> dict[Key, Reason]:
        ids = {
            line.entry.source_id
            for line in lines
            if line.entry.source_type == source_type and line.entry.source_id
        }
        if not ids:
            return {}
        void = {
            str(public_id): number
            for public_id, number in model._base_manager.filter(
                organisation=organisation, public_id__in=ids, status=void_status
            ).values_list("public_id", "number")
        }
        return {
            key(line): Reason(
                "voided_document",
                _("%(document)s %(number)s is void: its entries can't be recoded.")
                % {"document": str(label), "number": void[line.entry.source_id]},
                {"source_type": source_type, "number": void[line.entry.source_id]},
            )
            for line in lines
            if line.entry.source_type == source_type and line.entry.source_id in void
        }

    check.__name__ = f"voided_{source_type.replace('.', '_')}"
    return check
