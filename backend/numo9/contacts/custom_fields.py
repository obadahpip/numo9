"""Custom fields (B-01-T09, gap-43): fields an organisation adds to its records, typed and checked.

An organisation defines up to 30 fields per record type (Phase 0: contacts) — text, number, date
or select — in Settings → Custom fields. A record keeps its values in one JSONB column
(``Contact.custom_fields``: ``{"industry": "construction", "employees": "12"}``) checked against
the definitions on every save by ``clean_custom_values()``:

- an unknown key is refused (``contacts.custom_field.unknown``);
- a value of the wrong type is refused (``contacts.custom_field.type_mismatch``): text must be text
  (≤ 500 characters), a number a number (``True`` is not one), a date a real ``YYYY-MM-DD`` date, a
  select one of its options;
- values are stored in one canonical form: text tidied, numbers as exact decimal strings
  (``"12.50"`` — no binary rounding, this is accounting software), dates as ISO strings, selects
  as the option's value; an empty value removes the key;
- a required field must be filled when the record is created, and can't be emptied later
  (``contacts.custom_field.required``); adding a required field later doesn't block saving older
  records;
- only values that change are checked: a value kept as it was stays valid even when its option
  was removed or its field deleted since (history is never rewritten by a settings change); a
  deleted field can't receive a new value.

Each error names the field (its English label) and is keyed ``custom_fields.<key>`` so the form
shows it next to the field.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MAX_FIELDS_PER_RECORD_TYPE = 30
MAX_OPTIONS = 100
TEXT_MAX = 500
NUMBER_MAX_DIGITS = 18
KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def clean_value(field_type: str, options: list[dict[str, Any]], value: Any) -> Any:
    """The canonical stored form of one value, or a ``ValueError`` when the type doesn't match."""
    from .models import CustomFieldType

    if field_type == CustomFieldType.TEXT:
        if not isinstance(value, str):
            raise ValueError("text")
        text = " ".join(value.split())
        if len(text) > TEXT_MAX:
            raise ValueError("too_long")
        return text
    if field_type == CustomFieldType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, int | float | Decimal | str):
            raise ValueError("number")
        try:
            number = Decimal(str(value).strip().replace(",", ""))
        except InvalidOperation as exc:
            raise ValueError("number") from exc
        if not number.is_finite():
            raise ValueError("number")
        digits = len(number.as_tuple().digits)
        if digits > NUMBER_MAX_DIGITS:
            raise ValueError("number")
        return format(number, "f")
    if field_type == CustomFieldType.DATE:
        if isinstance(value, date):
            return value.isoformat()
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
            raise ValueError("date")
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError as exc:
            raise ValueError("date") from exc
    if field_type == CustomFieldType.SELECT:
        if not isinstance(value, str) or value not in {o["value"] for o in options}:
            raise ValueError("select")
        return value
    raise ValueError("type")


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def clean_custom_values(
    values: Mapping[str, Any] | None,
    definitions: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    *,
    creating: bool,
) -> dict[str, Any]:
    """Check ``values`` against ``definitions`` (key → ``CustomFieldDefinition``, deleted ones
    included); return the values in canonical form or raise one ``ValidationError`` keyed
    ``custom_fields.<key>``."""
    if values is None:
        values = {}
    if not isinstance(values, Mapping):
        raise ValidationError(
            {
                "custom_fields": ValidationError(
                    _("Custom fields must be a set of field names and values."),
                    code="contacts.custom_field.not_an_object",
                )
            }
        )
    previous = dict(previous or {})
    errors: dict[str, list[ValidationError]] = {}
    cleaned: dict[str, Any] = {}
    for key, value in values.items():
        definition = definitions.get(key)
        unchanged = key in previous and previous[key] == value
        if unchanged:
            cleaned[key] = value  # kept as it was: never re-checked against a newer definition
            continue
        if definition is None:
            errors.setdefault(f"custom_fields.{key}", []).append(
                ValidationError(
                    _("There is no custom field %(key)s in this organisation."),
                    code="contacts.custom_field.unknown",
                    params={"key": key},
                )
            )
            continue
        if _is_empty(value):
            continue
        if definition.deleted_at is not None:
            errors.setdefault(f"custom_fields.{key}", []).append(
                ValidationError(
                    _("%(field)s has been removed from the custom fields."),
                    code="contacts.custom_field.removed",
                    params={"field": definition.label},
                )
            )
            continue
        try:
            cleaned[key] = clean_value(definition.field_type, definition.options or [], value)
        except ValueError as exc:
            errors.setdefault(f"custom_fields.{key}", []).append(
                _mismatch(definition, str(exc), value)
            )
    for key, definition in definitions.items():
        if not definition.required or definition.deleted_at is not None or key in cleaned:
            continue
        if creating or key in previous:
            errors.setdefault(f"custom_fields.{key}", []).append(
                ValidationError(
                    _("%(field)s is required."),
                    code="contacts.custom_field.required",
                    params={"field": definition.label},
                )
            )
    if errors:
        raise ValidationError(errors)
    return cleaned


def _mismatch(definition: Any, problem: str, value: Any) -> ValidationError:
    expected = {
        "text": _("text"),
        "number": _("a number"),
        "date": _("a date (YYYY-MM-DD)"),
        "select": _("one of its choices"),
    }.get(definition.field_type, definition.field_type)
    if problem == "too_long":
        return ValidationError(
            _("%(field)s is limited to %(max)d characters."),
            code="contacts.custom_field.too_long",
            params={"field": definition.label, "max": TEXT_MAX},
        )
    return ValidationError(
        _("%(field)s needs %(expected)s: %(value)s doesn't fit."),
        code="contacts.custom_field.type_mismatch",
        params={"field": definition.label, "expected": expected, "value": repr(value)[:60]},
    )
