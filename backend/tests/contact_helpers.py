"""Shared helpers for the contact tests (B-01)."""

from __future__ import annotations

from typing import Any

from numo9.contacts.models import Contact
from numo9.tenancy.models import Organisation


def contact(
    organisation: Organisation,
    display_name: str,
    roles: list[str] | None = None,
    **fields: Any,
) -> Contact:
    """Create and save a contact (runs every save rule); a customer unless roles are given."""
    item = Contact(
        organisation=organisation,
        display_name=display_name,
        roles=["customer"] if roles is None else roles,
        **fields,
    )
    item.save()
    return item
