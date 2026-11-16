"""Column mapping: auto-suggest (fuzzy header match EN/FR), validation, saved mappings (B-03-T03).

**Auto-suggest** — ``suggest(entity, headers)`` proposes one field per column of a file:

1. headers and field names are normalised: accents removed, case folded, punctuation and spaces
   collapsed (``"N° de client"`` → ``"n de client"``, ``"E-mail"`` → ``"e mail"``);
2. a header equal to the field's label or one of its English names is **exact**; equal to one of
   its French names, **exact (FR)** (``"Courriel"`` → Email, ``"Code postal"`` → postal code);
3. otherwise a **similar** match: the best similarity between the header and any name ≥ 0.8
   (character ratio of the space-free forms, or the share of the name's words found in the
   header). Names of three letters or fewer (``BN``, ``NE``, ``Tél``) only match exactly, so
   ``NB`` (New Brunswick) is never taken for a Business Number;
4. fields and columns are paired best score first: a field is suggested for one column at most,
   and a column gets one field at most; the rest get **none** ("Don't import").

**Validation** — ``check_mapping(entity, columns)``: every field known, none mapped twice, every
required field mapped; all problems reported at once (``ValidationError`` on ``columns``).

**Saved mappings** — ``save_mapping`` stores an ``ImportMapping``; ``find_saved`` returns the
organisation's mapping saved from a file with the same headers (order and case don't matter);
``resolve(entity, headers)`` gives the columns for a new file: from the saved mapping when there
is one (confidence **saved**), else from auto-suggest.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.tenancy.context import TenantContextMissing, current_org

from .fields import ImportEntity, UnknownEntity, get_entity
from .models import ImportMapping

SIMILAR_THRESHOLD = 0.8
#: Names this short (space-free) only match exactly.
SHORT_NAME = 3


class Confidence(StrEnum):
    SAVED = "saved"
    EXACT = "exact"
    EXACT_FR = "exact_fr"
    SIMILAR = "similar"
    NONE = "none"


@dataclass(frozen=True)
class Suggestion:
    header: str
    field: str  # "" = don't import
    confidence: Confidence
    score: float


_NON_ALNUM = re.compile(r"[^0-9a-z]+")
#: Ligatures Unicode doesn't decompose (ß is handled by casefold).
_LIGATURES = str.maketrans({"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae"})


def normalise(text: str) -> str:
    """Header comparison form: no accents, case folded, punctuation and spaces collapsed."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_LIGATURES))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _NON_ALNUM.sub(" ", plain.casefold()).strip()


def header_key(headers: Iterable[str]) -> str:
    """Fingerprint of a file's headers, independent of order, case and accents."""
    names = sorted({normalise(header) for header in headers if normalise(header)})
    return hashlib.sha256("\x1f".join(names).encode()).hexdigest()


# ---- auto-suggest ------------------------------------------------------------------------------


def _names(entity: ImportEntity) -> list[tuple[str, Confidence, str]]:
    """(field key, confidence on an exact match, normalised name) for every name of every field."""
    names: list[tuple[str, Confidence, str]] = []
    for item in entity.fields:
        for name in (str(item.label), item.key.replace("_", " "), *item.names_en):
            names.append((item.key, Confidence.EXACT, normalise(name)))
        for name in item.names_fr:
            names.append((item.key, Confidence.EXACT_FR, normalise(name)))
    return names


def similarity(header: str, name: str) -> float:
    """Similarity of two normalised strings in [0, 1] (module docstring, step 3)."""
    compact_header, compact_name = header.replace(" ", ""), name.replace(" ", "")
    if not compact_header or not compact_name:
        return 0.0
    if compact_header == compact_name:
        return 1.0
    if min(len(compact_header), len(compact_name)) <= SHORT_NAME:
        return 0.0
    ratio = SequenceMatcher(None, compact_header, compact_name).ratio()
    name_words, header_words = set(name.split()), set(header.split())
    shared = len(name_words & header_words) / len(name_words) if len(name_words) > 1 else 0.0
    # Containment counts only when the header adds little (e.g. "Billing city" ⊇ "city" is not
    # enough; "Customer email address" ⊇ "email address" is).
    if shared and len(header_words) > len(name_words) + 1:
        shared = 0.0
    return max(ratio, shared)


def suggest(entity_key: str, headers: Sequence[str]) -> list[Suggestion]:
    """One suggestion per header, in header order (module docstring)."""
    entity = get_entity(entity_key)
    names = _names(entity)
    candidates: list[tuple[float, int, int, str, Confidence]] = []
    for index, header in enumerate(headers):
        plain = normalise(header)
        best: dict[str, tuple[float, Confidence]] = {}
        for key, exact_confidence, name in names:
            if plain == name:
                score, confidence = 1.0, exact_confidence
            else:
                score, confidence = similarity(plain, name), Confidence.SIMILAR
                if score < SIMILAR_THRESHOLD:
                    continue
                score = min(score, 0.99)  # an exact match always wins
            current = best.get(key)
            # English exact before French exact for the same field (e.g. "Province").
            rank = (score, confidence == Confidence.EXACT)
            if current is None or rank > (current[0], current[1] == Confidence.EXACT):
                best[key] = (score, confidence)
        for key, (score, confidence) in best.items():
            order = entity.field_keys.index(key)
            candidates.append((score, -order, -index, key, confidence))
    chosen: dict[int, tuple[str, Confidence, float]] = {}
    used: set[str] = set()
    for score, _order, negative_index, key, confidence in sorted(candidates, reverse=True):
        index = -negative_index
        if index in chosen or key in used:
            continue
        chosen[index] = (key, confidence, score)
        used.add(key)
    result: list[Suggestion] = []
    for index, header in enumerate(headers):
        if index in chosen:
            key, confidence, score = chosen[index]
            result.append(Suggestion(header, key, confidence, round(score, 3)))
        else:
            result.append(Suggestion(header, "", Confidence.NONE, 0.0))
    return result


# ---- validation --------------------------------------------------------------------------------


def join_names(names: Sequence[str]) -> str:
    """["A"] → "A"; ["A", "B"] → "A and B"; ["A", "B", "C"] → "A, B and C"."""
    if len(names) < 2:
        return "".join(names)
    return _("%(items)s and %(last)s") % {"items": ", ".join(names[:-1]), "last": names[-1]}


def check_mapping(entity_key: str, columns: Any) -> None:
    """Raise a ``ValidationError`` (all problems) unless ``columns`` is a usable mapping."""
    try:
        entity = get_entity(entity_key)
    except UnknownEntity:
        raise ValidationError(
            {
                "entity": ValidationError(
                    _("Nothing can be imported as %(entity)s.") % {"entity": entity_key},
                    code="imports.mapping.entity_unknown",
                )
            }
        ) from None
    if not isinstance(columns, Mapping) or not all(
        isinstance(header, str) and isinstance(target, str) for header, target in columns.items()
    ):
        raise ValidationError(
            {
                "columns": ValidationError(
                    _("A mapping pairs each column header with a field."),
                    code="imports.mapping.invalid",
                )
            }
        )
    problems: list[ValidationError] = []
    by_field: dict[str, list[str]] = {}
    for header, target in columns.items():
        if not target:
            continue
        if target not in entity.field_keys:
            problems.append(
                ValidationError(
                    _("Column %(column)s is mapped to %(field)s, which isn't a field here.")
                    % {"column": header, "field": target},
                    code="imports.mapping.field_unknown",
                )
            )
            continue
        by_field.setdefault(target, []).append(header)
    for target, headers in by_field.items():
        if len(headers) > 1:
            problems.append(
                ValidationError(
                    _("%(columns)s map to the same field, %(field)s — choose one.")
                    % {"columns": join_names(headers), "field": entity.field(target).label},
                    code="imports.mapping.field_twice",
                )
            )
    missing = [entity.field(key).label for key in entity.required_keys if key not in by_field]
    if missing:
        problems.append(
            ValidationError(
                _("Map a column to %(fields)s: it is required.")
                % {"fields": ", ".join(str(label) for label in missing)},
                code="imports.mapping.required_missing",
            )
        )
    if problems:
        raise ValidationError({"columns": problems})


# ---- saved mappings ----------------------------------------------------------------------------


def find_saved(entity_key: str, headers: Iterable[str]) -> ImportMapping | None:
    """The active organisation's mapping saved from a file with the same headers, if any."""
    mapping: ImportMapping | None = (
        ImportMapping.objects.filter(
            entity=entity_key, header_key=header_key(headers), deleted_at__isnull=True
        )
        .order_by(F("last_used_at").desc(nulls_last=True), "-updated_at")
        .first()
    )
    return mapping


def resolve(
    entity_key: str, headers: Sequence[str], saved: ImportMapping | None = None
) -> list[Suggestion]:
    """The columns for a new file: the saved mapping's (given or found), else auto-suggest.

    Headers are matched to the saved mapping's in their normalised form, so a file whose headers
    differ only in case or accents still uses it. Headers the saved mapping doesn't know are
    auto-suggested among the fields it leaves free.
    """
    saved = saved or find_saved(entity_key, headers)
    if saved is None:
        return suggest(entity_key, headers)
    known = {normalise(header): target for header, target in saved.columns.items()}
    suggestions = suggest(entity_key, headers)
    taken = {known[normalise(h)] for h in headers if known.get(normalise(h))}
    result: list[Suggestion] = []
    for suggestion in suggestions:
        plain = normalise(suggestion.header)
        if plain in known:
            result.append(Suggestion(suggestion.header, known[plain], Confidence.SAVED, 1.0))
        elif suggestion.field and suggestion.field not in taken:
            result.append(suggestion)
        else:
            result.append(Suggestion(suggestion.header, "", Confidence.NONE, 0.0))
    return result


def as_columns(suggestions: Iterable[Suggestion]) -> dict[str, str]:
    return {suggestion.header: suggestion.field for suggestion in suggestions}


def save_mapping(
    entity_key: str,
    name: str,
    columns: Mapping[str, str],
    *,
    user: Any = None,
    mapping: ImportMapping | None = None,
) -> ImportMapping:
    """Create a named mapping, or update ``mapping`` (same organisation) with new columns/name."""
    if mapping is None:
        organisation = current_org()
        if organisation is None:
            raise TenantContextMissing("save_mapping needs an active organisation")
        mapping = ImportMapping(
            organisation=organisation, entity=entity_key, created_by=user if user else None
        )
    mapping.name = name
    mapping.columns = dict(columns)
    mapping.save()
    return mapping


def record_use(mapping: ImportMapping) -> None:
    """Count one more use (an applied import) without an audit line or a race."""
    now = timezone.now()
    ImportMapping.objects.filter(pk=mapping.pk).update(
        use_count=F("use_count") + 1, last_used_at=now
    )
    mapping.refresh_from_db(fields=["use_count", "last_used_at"])
