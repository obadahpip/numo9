"""Contact import matcher: which existing contact a row updates (B-03-T05).

By stable keys only, never by name — a renamed contact is updated in place, two contacts with the
same name stay two (gap-21, Xero matches on the name):

1. ``external_id`` — the contact's ID in the system the file comes from;
2. ``number`` — the Numo9 contact number; a merged contact's number leads to the contact it was
   merged into (B-01-T12 alias);
3. ``bn`` — the Business Number, **only when the person opts in** (``match_bn=True``) and exactly
   one active contact has it.

A key that is present but finds no contact means "create" (with that external ID or number); a
row whose keys point at two different contacts is refused, naming both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext as _

from .merge import resolve
from .models import Contact
from .validators import normalise_bn


@dataclass
class Match:
    contact: Contact | None
    by: str = ""  # "external_id" | "number" | "bn" | ""
    conflict: str = ""  # a message when the keys disagree


def _scope() -> Any:
    return Contact.objects.filter(deleted_at__isnull=True)


def match_contact(values: dict[str, Any], *, match_bn: bool = False) -> Match:
    found: list[tuple[str, Contact]] = []
    external = values.get("external_id")
    if isinstance(external, str) and external:
        hit = _scope().filter(external_id=external).first()
        if hit is not None:
            found.append(("external_id", resolve(hit)))
    number = values.get("number")
    if isinstance(number, str) and number:
        hit = _scope().filter(number__iexact=number).first()
        if hit is not None:
            found.append(("number", resolve(hit)))
    if match_bn and not found:
        bn = values.get("bn")
        if isinstance(bn, str) and bn:
            hits = list(_scope().filter(bn=normalise_bn(bn), merged_into__isnull=True)[:2])
            if len(hits) == 1:
                found.append(("bn", hits[0]))
    if not found:
        return Match(None)
    by, contact = found[0]
    for _other_by, other in found[1:]:
        if other.pk != contact.pk:
            return Match(
                None,
                conflict=_(
                    "The external ID points to %(a)s but the contact number to %(b)s. Fix one of "
                    "them in the file."
                )
                % {"a": contact, "b": other},
            )
    return Match(contact, by)
