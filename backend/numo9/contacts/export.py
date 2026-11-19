"""Contacts and people export in the shape the import reads back (B-03-T10).

The headers are the import fields' labels (so the import maps them on its own), one row per
contact (``contacts.contact``) or per person (``contacts.person``, long format with the contact's
external ID or number). Exporting then importing the file changes nothing (round trip). CSV is
UTF-8 with a byte-order mark (Excel opens accents correctly); XLSX cells are text, so numbers
like ``0100`` keep their digits.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from django.utils.translation import gettext as _

from .importing import CONTACT, PERSON
from .models import Address, Contact, ContactPerson, ContactRole

ROLE_NAMES = dict(ContactRole.choices)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return _("Yes") if value else _("No")
    return str(value)


def contact_values(contact: Contact) -> dict[str, str]:
    people = list(ContactPerson.objects.filter(contact=contact, deleted_at__isnull=True))
    primary = next((p for p in people if p.is_primary), people[0] if people else None)
    values = {
        "external_id": contact.external_id,
        "number": contact.number,
        "display_name": contact.display_name,
        "legal_name": contact.legal_name,
        "roles": "; ".join(str(ROLE_NAMES[r]) for r in contact.roles),
        "email": primary.email if primary else "",
        "phone": primary.phone if primary else "",
        "bn": contact.bn,
        "tax_id": contact.tax_id,
        "currency": contact.currency,
        "credit_limit": "" if contact.credit_limit is None else f"{contact.credit_limit:.2f}",
        "credit_mode": contact.credit_mode,
        "language": contact.language,
        "statement_pref": contact.statement_pref,
        "t4a_flag": _text(contact.t4a_flag),
    }
    for kind in ("billing", "shipping"):
        address = Address.objects.filter(
            contact=contact, kind=kind, deleted_at__isnull=True
        ).first()
        for part in ("line1", "line2", "city", "province", "postal_code", "country"):
            values[f"{kind}_{part}"] = getattr(address, part) if address else ""
    return values


def _contacts() -> list[Contact]:
    return list(
        Contact.objects.filter(deleted_at__isnull=True, merged_into__isnull=True).order_by(
            "display_name", "number"
        )
    )


def export_table(entity: str = CONTACT.key) -> tuple[list[str], list[list[str]]]:
    """Headers (the import labels in the active language) and the rows of the active org."""
    if entity == PERSON.key:
        headers = [str(f.label) for f in PERSON.fields]
        rows = []
        for contact in _contacts():
            ref = contact.external_id or contact.number
            for person in ContactPerson.objects.filter(contact=contact, deleted_at__isnull=True):
                values = {
                    "contact_ref": ref,
                    "first_name": person.first_name,
                    "last_name": person.last_name,
                    "email": person.email,
                    "phone": person.phone,
                    "job_title": person.job_title,
                    "is_primary": _text(person.is_primary),
                    "include_in_emails": _text(person.include_in_emails),
                }
                rows.append([values[key] for key in PERSON.field_keys])
        return headers, rows
    headers = [str(f.label) for f in CONTACT.fields]
    return headers, [[contact_values(c)[k] for k in CONTACT.field_keys] for c in _contacts()]


def export_csv(entity: str = CONTACT.key) -> bytes:
    headers, rows = export_table(entity)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def export_xlsx(entity: str = CONTACT.key) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    headers, rows = export_table(entity)
    workbook = Workbook()
    sheet: Any = workbook.active
    sheet.title = str(_("People") if entity == PERSON.key else _("Contacts"))[:31]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    for line in sheet.iter_rows(min_row=2):
        for cell in line:
            cell.number_format = "@"
    sheet.freeze_panes = "A2"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def template_csv(entity: str = CONTACT.key) -> bytes:
    """An empty file with the import's headers (B-03-T13)."""
    headers = [str(f.label) for f in (PERSON if entity == PERSON.key else CONTACT).fields]
    buffer = io.StringIO(newline="")
    csv.writer(buffer).writerow(headers)
    return ("﻿" + buffer.getvalue()).encode("utf-8")
