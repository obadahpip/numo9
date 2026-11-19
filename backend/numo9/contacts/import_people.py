"""People import in long format: one row per person, as many per contact as needed (B-03-T09,
gap-15 — Xero takes five and deletes people on blank columns).

``contact_ref`` names the contact by external ID or number (never by name). The person is found
within that contact by email, else by first + last name; otherwise added. Blank cells leave a
field alone, ``__CLEAR__`` empties it; ``primary`` makes the person the contact's primary one.
Same dry-run / apply / audit behaviour as the contacts import (``import_engine``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils.translation import gettext as _

from numo9.audit.batch import audit_batch
from numo9.imports.mapping import check_mapping
from numo9.imports.parser import Sheet
from numo9.imports.report import CLEAR_TOKEN, Action, ImportReport, RowResult
from numo9.ledger.renumber import acting_as
from numo9.tenancy.context import current_org

from .import_engine import _DryRun, _messages, _RowFailed, _savepoint, cells_of
from .import_match import match_contact
from .import_normalise import EMAIL, FALSE, TRUE, _plain
from .importing import PERSON
from .models import ContactPerson

ENTITY_KEY = PERSON.key
TEXT_FIELDS = ("first_name", "last_name", "email", "phone", "job_title")
FLAGS = ("is_primary", "include_in_emails")


def _find(contact: Any, cells: dict[str, str]) -> ContactPerson | None:
    people: QuerySet[ContactPerson] = ContactPerson.objects.filter(
        contact=contact, deleted_at__isnull=True
    )
    email = cells.get("email", "").strip().lower()
    if email and email != CLEAR_TOKEN.lower():
        hit = people.filter(email__iexact=email).first()
        if hit is not None:
            return hit
    first, last = cells.get("first_name", "").strip(), cells.get("last_name", "").strip()
    if first or last:
        return people.filter(first_name__iexact=first, last_name__iexact=last).first()
    return None


def _row(cells: dict[str, str], result: RowResult) -> None:
    ref = cells.get("contact_ref", "").strip()
    found = match_contact({"external_id": ref}) if ref else None
    if found is None or found.contact is None:
        found = match_contact({"number": ref}) if ref else None
    if found is None or found.contact is None:
        result.fail(
            "contact_ref",
            "contacts.import.contact_unknown",
            _("No contact has the external ID or number '%(ref)s'.") % {"ref": ref},
        )
        raise _RowFailed
    contact = found.contact
    person = _find(contact, cells)
    new = person is None
    if person is None:
        person = ContactPerson(organisation=contact.organisation, contact=contact)
    changes: dict[str, list[Any]] = {}
    for field in TEXT_FIELDS:
        raw = cells.get(field, "").strip()
        if not raw:
            continue
        value = "" if raw == CLEAR_TOKEN else (raw.lower() if field == "email" else raw)
        if field == "email" and value and not EMAIL.match(value):
            result.fail(
                field,
                "contacts.import.email",
                _("'%(value)s' isn't an email address.") % {"value": raw},
            )
            raise _RowFailed
        if getattr(person, field) != value:
            changes[field] = [getattr(person, field), value]
    for field in FLAGS:
        raw = _plain(cells.get(field, ""))
        if not raw:
            continue
        if raw not in TRUE and raw not in FALSE:
            result.fail(field, "contacts.import.yes_no", _("Use Yes or No."))
            raise _RowFailed
        flag = raw in TRUE
        if getattr(person, field) != flag:
            changes[field] = [getattr(person, field), flag]
    name = " ".join(filter(None, [cells.get("first_name"), cells.get("last_name")]))
    result.label = f"{contact} · {name or cells.get('email', '')}"
    if not new and not changes:
        result.action = Action.UNCHANGED
        return
    for field, (_before, after) in changes.items():
        setattr(person, field, after)
    try:
        person.save()
    except ValidationError as error:
        for key, code, message in _messages(error):
            result.fail(key, code, message)
        raise _RowFailed from None
    result.action = Action.CREATE if new else Action.UPDATE
    result.changes = changes


def import_people(
    sheet: Sheet,
    columns: Mapping[str, str],
    *,
    apply: bool = False,
    actor: Any = None,
    filename: str = "",
    **_options: Any,
) -> ImportReport:
    organisation = current_org()
    if organisation is None:
        raise ValueError("Import people only with an active organisation.")
    check_mapping(ENTITY_KEY, columns)
    report = ImportReport(ENTITY_KEY, applied=apply)
    label = _("People import: %(file)s") % {"file": filename or sheet.name}
    try:
        with (
            acting_as(actor),
            transaction.atomic(),
            audit_batch(label, organisation=organisation, meta={"file": filename}),
        ):
            for number, cells in cells_of(sheet, columns):
                result = RowResult(number, cells.get("contact_ref", ""))
                report.rows.append(result)
                with _savepoint():
                    _row(cells, result)
            if not apply:
                raise _DryRun
    except _DryRun:
        pass
    return report
