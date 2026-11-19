"""Contact import engine: dry run and apply of a mapped contacts sheet (B-03-T07, T08).

``import_contacts(sheet, columns, apply=…, match_bn=…)`` reads every row with the normaliser
(T04), finds its contact with the matcher (T05), works out the changes with the diff engine (T06)
and — on apply — writes them, **each row in its own transaction** (savepoint): a row that fails
leaves the others imported, and its reasons are reported. A dry run does the same work and rolls
it all back, so the review shows exactly what applying does (and writes 0 contacts). The whole
import is one audit batch ("Contacts import: <file>") attributed to the person.

Duplicates within the file (two rows with the same external ID or number) are refused on the
second row. A new contact needs a display name and at least one role (Customer by default).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from numo9.audit.batch import audit_batch
from numo9.imports.mapping import check_mapping
from numo9.imports.parser import Sheet
from numo9.imports.report import Action, ImportReport, RowResult
from numo9.ledger.renumber import acting_as
from numo9.tenancy.context import current_org

from .import_diff import apply as apply_changes
from .import_diff import diff
from .import_match import match_contact
from .import_normalise import normalise_row
from .importing import CONTACT
from .models import Contact

ENTITY_KEY = CONTACT.key


class _DryRun(Exception):
    pass


class _RowFailed(Exception):
    pass


def cells_of(sheet: Sheet, columns: Mapping[str, str]) -> Iterator[tuple[int, dict[str, str]]]:
    index = {header: position for position, header in enumerate(sheet.headers)}
    mapped = [(index[h], f) for h, f in columns.items() if f and h in index]
    for row in sheet.rows:
        yield row.number, {f: row.cells[p] if p < len(row.cells) else "" for p, f in mapped}


def _messages(error: ValidationError) -> list[tuple[str, str, str]]:
    found = []
    if hasattr(error, "error_dict"):
        for field, items in error.error_dict.items():
            for item in items:
                for message in item.messages:
                    found.append((field, item.code or "invalid", message))
    else:
        for message in error.messages:
            found.append(("", getattr(error, "code", None) or "invalid", message))
    return found


@contextmanager
def _savepoint() -> Iterator[None]:
    try:
        with transaction.atomic():
            yield
    except _RowFailed:
        pass


def _key(values: dict[str, Any]) -> str:
    return str(values.get("external_id") or values.get("number") or "")


def _row(values: dict[str, Any], result: RowResult, match_bn: bool) -> None:
    found = match_contact(values, match_bn=match_bn)
    if found.conflict:
        result.fail("", "contacts.import.conflict", found.conflict)
        raise _RowFailed
    contact = found.contact
    changes = diff(contact, values)
    if contact is None:
        if not values.get("display_name"):
            result.fail(
                "display_name", "contacts.import.required", _("A new contact needs a name.")
            )
            raise _RowFailed
        contact = Contact(organisation=current_org(), roles=["customer"])
        result.action = Action.CREATE
    elif changes:
        result.action = Action.UPDATE
    else:
        result.action = Action.UNCHANGED
        result.label = str(contact)
        return
    try:
        apply_changes(contact, changes)
    except ValidationError as error:
        for field, code, message in _messages(error):
            result.fail(field, code, message)
        raise _RowFailed from None
    result.changes = {f: [_plain(b), _plain(a)] for f, (b, a) in changes.items()}
    result.label = str(contact)
    result.key = result.key or contact.number


def _plain(value: Any) -> Any:
    return (
        str(value)
        if value is not None and not isinstance(value, str | bool | int | list)
        else value
    )


def import_contacts(
    sheet: Sheet,
    columns: Mapping[str, str],
    *,
    apply: bool = False,
    match_bn: bool = False,
    actor: Any = None,
    filename: str = "",
) -> ImportReport:
    """Dry-run (default) or apply a contacts sheet (module docstring)."""
    organisation = current_org()
    if organisation is None:
        raise ValueError("Import contacts only with an active organisation.")
    check_mapping(ENTITY_KEY, columns)
    report = ImportReport(ENTITY_KEY, applied=apply)
    seen: dict[str, int] = {}
    label = _("Contacts import: %(file)s") % {"file": filename or sheet.name}
    try:
        with (
            acting_as(actor),
            transaction.atomic(),
            audit_batch(label, organisation=organisation, meta={"file": filename}),
        ):
            for number, cells in cells_of(sheet, columns):
                normalised = normalise_row(cells)
                result = RowResult(number, _key(normalised.values))
                report.rows.append(result)
                for error in normalised.errors:
                    result.fail(error.field, error.code, error.message)
                for key in ("external_id", "number"):
                    value = normalised.values.get(key)
                    if isinstance(value, str) and value:
                        first = seen.setdefault(f"{key}:{value.casefold()}", number)
                        if first != number:
                            result.fail(
                                key,
                                "contacts.import.duplicate_row",
                                _("Row %(row)s already has this %(what)s.")
                                % {
                                    "row": first,
                                    "what": _("external ID")
                                    if key == "external_id"
                                    else _("contact number"),
                                },
                            )
                if result.action == Action.ERROR:
                    continue
                with _savepoint():
                    _row(normalised.values, result, match_bn)
            if not apply:
                raise _DryRun
    except _DryRun:
        pass
    return report
