"""Duplicate detection (B-01-T10): "Possible duplicate: Maple Supply Ltd. (BN matches)".

    find_duplicates(name="Maple Suply")                  # → Maple Supply Ltd., name 79 % similar
    find_duplicates(name="…", email="ap@maplesupply.ca", bn="123456782", exclude=contact)

A contact is a possible duplicate when **any** of these holds:

- **name** — trigram similarity (PostgreSQL ``pg_trgm``) of the two *name keys* is at least 0.6.
  A name key (``Contact.name_key``, kept up to date on save) is the display name in lower case
  without accents (``Érable`` = ``erable``), punctuation, a leading "The" or trailing company forms
  (Ltd., Limited, Inc., Corp., Co., LLC, Ltée, Limitée, Enr., S.E.N.C.…): "Maple Supply Ltd." and
  "Maple Suply" compare as ``maple supply`` / ``maple suply`` (0.79). Names shorter than 3
  characters are not compared;
- **email** — a person of the contact has the same email address (any case);
- **BN** — the same Business Number (``123 456 782`` = ``123456782 RT 0001``);
- **tax ID** — the same tax ID, ignoring case, spaces, hyphens, dots and slashes.

It is a warning, never a block: the same name in another province is still listed (with its
province, so people can tell), and saving stays possible. Merged contacts are never listed;
archived ones are, marked archived. Results: exact matches first (more reasons first), then by
name similarity, at most ``limit``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from django.contrib.postgres.search import TrigramSimilarity
from django.db import connection
from django.db.models import BooleanField, F, Func, QuerySet, Value
from django.db.models.functions import Replace, Upper

from .validators import normalise_bn

NAME_SIMILARITY = 0.6
MIN_NAME_LENGTH = 3
DEFAULT_LIMIT = 10

#: Company forms dropped from the end of a name key (English and French, after accents go).
COMPANY_FORMS: frozenset[str] = frozenset(
    {
        "ltd",
        "limited",
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "co",
        "company",
        "llc",
        "llp",
        "lp",
        "plc",
        "ltee",
        "limitee",
        "enr",
        "senc",
        "sencrl",
        "srl",
        "cie",
    }
)


class Reason:
    NAME = "name"
    EMAIL = "email"
    BN = "bn"
    TAX_ID = "tax_id"


#: Order of the reasons in a match (exact identifiers first).
REASON_ORDER = (Reason.BN, Reason.TAX_ID, Reason.EMAIL, Reason.NAME)


def name_key(name: str) -> str:
    """The comparable form of a name: ``Érable Distribution Ltée`` → ``erable distribution``."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"(?<=\b[a-z])\.(?=[a-z]\b)", "", text)  # s.e.n.c. → senc, s.r.l. → srl
    words = re.sub(r"[^a-z0-9]+", " ", text).split()
    full = list(words)
    if words and words[0] == "the":
        words = words[1:]
    while words and words[-1] in COMPANY_FORMS:
        words = words[:-1]
    return " ".join(words or full)


def tax_id_key(value: str) -> str:
    """``us 12-345/678`` → ``US12345678`` (case, spaces, hyphens, dots and slashes ignored)."""
    return re.sub(r"[\s\-./]", "", (value or "").upper())


@dataclass
class DuplicateMatch:
    contact: Any  # numo9.contacts.models.Contact
    reasons: list[str] = field(default_factory=list)
    similarity: float | None = None  # name similarity 0–1 when the name was compared

    @property
    def is_exact(self) -> bool:
        return any(r != Reason.NAME for r in self.reasons)


class TrigramMatch(Func):
    """``a % b`` — pg_trgm's similarity operator (uses the name-key GIN index)."""

    arg_joiner = " %% "
    template = "(%(expressions)s)"
    output_field = BooleanField()


def find_duplicates(
    *,
    name: str = "",
    email: str = "",
    bn: str = "",
    tax_id: str = "",
    exclude: Any = None,
    limit: int = DEFAULT_LIMIT,
) -> list[DuplicateMatch]:
    """Possible duplicates in the active organisation (see the module docstring)."""
    from .models import Contact, ContactPerson

    base: QuerySet[Contact] = Contact.objects.filter(deleted_at__isnull=True)
    if exclude is not None and getattr(exclude, "pk", None) is not None:
        base = base.exclude(pk=exclude.pk)
    matches: dict[int, DuplicateMatch] = {}

    def add(contact: Contact, reason: str, similarity: float | None = None) -> None:
        match = matches.setdefault(contact.pk, DuplicateMatch(contact))
        if reason not in match.reasons:
            match.reasons.append(reason)
        if similarity is not None:
            match.similarity = max(match.similarity or 0.0, similarity)

    key = name_key(name)
    if len(key) >= MIN_NAME_LENGTH and connection.vendor == "postgresql":
        similar = (
            base.filter(TrigramMatch(F("name_key"), Value(key)))
            .annotate(similarity=TrigramSimilarity("name_key", key))
            .filter(similarity__gte=NAME_SIMILARITY)
            .order_by("-similarity", "display_name")[: limit * 2]
        )
        for found in similar:
            add(found, Reason.NAME, float(found.similarity))

    address = (email or "").strip().lower()
    if address:
        people = ContactPerson.objects.filter(email=address, deleted_at__isnull=True)
        for by_email in base.filter(pk__in=people.values("contact_id"))[:limit]:
            add(by_email, Reason.EMAIL)

    number = normalise_bn(bn)
    if re.fullmatch(r"[0-9]{9}", number):
        for by_bn in base.filter(bn=number)[:limit]:
            add(by_bn, Reason.BN)

    tax_key = tax_id_key(tax_id)
    if tax_key:
        compact: Func = Upper(F("tax_id"))
        for character in " -./":
            compact = Replace(compact, Value(character), Value(""))
        for by_tax_id in base.annotate(tax_key=compact).filter(tax_key=tax_key)[:limit]:
            add(by_tax_id, Reason.TAX_ID)

    for match in matches.values():
        match.reasons.sort(key=REASON_ORDER.index)
    ordered = sorted(
        matches.values(),
        key=lambda m: (
            -sum(r != Reason.NAME for r in m.reasons),
            -(m.similarity or 0.0),
            m.contact.display_name,
        ),
    )
    return ordered[:limit]
