"""Contact import diff engine: what a row changes, never destroying what the file leaves blank
(B-03-T06, gap-21).

``diff(contact, values)`` compares normalised values (T04) with a contact (``None`` = new) and
returns ``{field: [before, after]}`` for every field that would change:

- a field **absent** from ``values`` (a blank cell) is never touched;
- ``CLEAR`` (``__CLEAR__``) empties it (``""``, or no limit for the credit limit);
- ``email`` / ``phone`` are the primary person's; ``billing_*`` / ``shipping_*`` the addresses'.

``apply(contact, values)`` writes exactly those changes (the model's rules run on save).
"""

from __future__ import annotations

from typing import Any

from .import_normalise import CLEAR
from .models import Address, Contact, ContactPerson

CONTACT_FIELDS = (
    "external_id",
    "number",
    "display_name",
    "legal_name",
    "roles",
    "bn",
    "tax_id",
    "currency",
    "credit_limit",
    "credit_mode",
    "language",
    "statement_pref",
    "t4a_flag",
)
PERSON_FIELDS = ("email", "phone")
ADDRESS_PARTS = ("line1", "line2", "city", "province", "postal_code", "country")
KINDS = ("billing", "shipping")


def _empty(field: str) -> Any:
    return None if field == "credit_limit" else ""


def _primary(contact: Contact | None) -> ContactPerson | None:
    if contact is None or contact.pk is None:
        return None
    return (
        ContactPerson.objects.filter(contact=contact, deleted_at__isnull=True)
        .order_by("-is_primary", "created_at", "id")
        .first()
    )


def _address(contact: Contact | None, kind: str) -> Address | None:
    if contact is None or contact.pk is None:
        return None
    return Address.objects.filter(contact=contact, kind=kind, deleted_at__isnull=True).first()


def _current(contact: Contact | None) -> dict[str, Any]:
    now: dict[str, Any] = {}
    for field in CONTACT_FIELDS:
        now[field] = getattr(contact, field) if contact is not None else _empty(field)
    if contact is not None:
        now["roles"] = list(contact.roles)
    person = _primary(contact)
    for field in PERSON_FIELDS:
        now[field] = getattr(person, field) if person else ""
    for kind in KINDS:
        address = _address(contact, kind)
        for part in ADDRESS_PARTS:
            now[f"{kind}_{part}"] = getattr(address, part) if address else ""
    return now


def diff(contact: Contact | None, values: dict[str, Any]) -> dict[str, list[Any]]:
    """``{field: [before, after]}`` for each field the row changes (module docstring)."""
    now = _current(contact)
    changes: dict[str, list[Any]] = {}
    for field, value in values.items():
        if field not in now:
            continue
        after = _empty(field) if value is CLEAR else value
        before = now[field]
        same_number = (
            field == "number"
            and isinstance(after, str)
            and isinstance(before, str)
            and after.casefold() == before.casefold()
        )
        if same_number:
            continue
        if before != after:
            changes[field] = [before, after]
    return changes


def apply(contact: Contact, changes: dict[str, list[Any]]) -> None:
    """Write ``changes`` (from ``diff``) to the saved contact, its primary person and addresses."""
    for field in CONTACT_FIELDS:
        if field in changes:
            setattr(contact, field, changes[field][1])
    contact.save()
    person_changes = {f: changes[f][1] for f in PERSON_FIELDS if f in changes}
    if person_changes:
        person = _primary(contact) or ContactPerson(
            organisation=contact.organisation, contact=contact
        )
        for field, value in person_changes.items():
            setattr(person, field, value)
        person.save()
    for kind in KINDS:
        parts = {p: changes[f"{kind}_{p}"][1] for p in ADDRESS_PARTS if f"{kind}_{p}" in changes}
        if parts:
            address = _address(contact, kind) or Address(
                organisation=contact.organisation, contact=contact, kind=kind
            )
            for part, value in parts.items():
                setattr(address, part, value)
            address.save()
