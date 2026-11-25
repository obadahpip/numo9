"""Find & recode — the search (C-07-T02): conditions → an ORM filter over ``JournalLine``.

``criteria`` = ``{"match": "all" | "any", "conditions": [{"field", "op", "value"}]}`` →
``find_lines(organisation, criteria)``: the organisation's lines of **posted** entries matching
all (or any) of the conditions, in entry and line order. Every query is scoped to the
organisation's partition (``organisation_id`` first, ADR-0003 §5) and served by the journal-line
indexes (account / account + date / contact / entry).

| Field | Ops | Value |
|---|---|---|
| ``type`` | ``is``, ``in`` | entry type(s): ``manual``, ``sales``, ``purchase``… |
| ``status`` | ``is``, ``in`` | ``posted``, ``reversed`` (searched when asked) |
| ``account`` | ``is``, ``in``, ``not`` | account public id(s) |
| ``bank_account`` | ``is`` | a bank account's public id: entries touching it |
| ``date`` | ``on``, ``before``, ``after``, ``between`` | ``YYYY-MM-DD`` / ``{from, to}`` |
| ``amount`` | ``eq``, ``gt``, ``gte``, ``lt``, ``lte``, ``between`` | the line's amount |
| ``tax_code`` | ``is``, ``in``, ``empty`` | tax code key(s) |
| ``entered_by`` | ``is`` | the user's public id (who posted the entry) |
| ``contact`` | ``is``, ``in``, ``empty`` | contact public id(s) |
| ``number`` | ``is`` | the journal number |
| ``reference`` | ``contains`` | text in the entry's narration or the line's description |
| ``tracking`` | ``is`` | ``{"category": "option"}`` |
| ``book`` | ``is`` | ``both``, ``accounting``, ``tax`` (``both`` lines are in each book) |

A condition that isn't one of these is refused (``ValidationError``, code
``ledger.recode.condition_invalid``, ``params.condition`` its position).
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal, InvalidOperation
from functools import reduce
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import F, Q, QuerySet
from django.db.models.functions import Greatest
from django.utils.translation import gettext as _

from .models import Book, JournalLine, JournalStatus

SEARCHED_STATUSES = (JournalStatus.POSTED, JournalStatus.REVERSED)
OPS: dict[str, tuple[str, ...]] = {
    "type": ("is", "in"),
    "status": ("is", "in"),
    "account": ("is", "in", "not"),
    "bank_account": ("is",),
    "date": ("on", "before", "after", "between"),
    "amount": ("eq", "gt", "gte", "lt", "lte", "between"),
    "tax_code": ("is", "in", "empty"),
    "entered_by": ("is",),
    "contact": ("is", "in", "empty"),
    "number": ("is",),
    "reference": ("contains",),
    "tracking": ("is",),
    "book": ("is",),
}


class Invalid(Exception):
    """A condition that isn't one of the table's."""


def _refuse(position: int, message: str) -> ValidationError:
    return ValidationError(
        message, code="ledger.recode.condition_invalid", params={"condition": position}
    )


def _list(value: Any) -> list[Any]:
    values = value if isinstance(value, list) else [value]
    if not values or any(v in (None, "") for v in values):
        raise Invalid
    return values


def _uuids(value: Any) -> list[uuid.UUID]:
    try:
        return [uuid.UUID(str(v)) for v in _list(value)]
    except ValueError as error:
        raise Invalid from error


def _date(value: Any) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as error:
        raise Invalid from error


def _decimal(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise Invalid from error
    if not amount.is_finite():
        raise Invalid
    return amount


def _range(value: Any, parse: Any) -> tuple[Any, Any]:
    if not isinstance(value, dict) or "from" not in value or "to" not in value:
        raise Invalid
    return parse(value["from"]), parse(value["to"])


def _in(field: str, op: str, values: list[Any]) -> Q:
    q = Q(**{f"{field}__in": values})
    return ~q if op == "not" else q


def condition_q(condition: Any) -> Q:
    """The filter of one condition (``Invalid`` when it isn't one)."""
    if not isinstance(condition, dict):
        raise Invalid
    field, op, value = condition.get("field"), condition.get("op"), condition.get("value")
    if field not in OPS or op not in OPS[field]:
        raise Invalid
    if field == "type":
        return Q(entry__type__in=[str(v) for v in _list(value)])
    if field == "status":
        statuses = [str(v) for v in _list(value)]
        if set(statuses) - set(SEARCHED_STATUSES):
            raise Invalid
        return Q(entry__status__in=statuses)
    if field == "account":
        return _in("account__public_id", op, _uuids(value))
    if field == "bank_account":
        (bank,) = _uuids(value)[:1]
        return Q(entry__lines__account__public_id=bank, entry__lines__account__is_bank=True)
    if field == "date":
        if op == "between":
            start, end = _range(value, _date)
            return Q(date__gte=start, date__lte=end)
        lookup = {"on": "date", "before": "date__lt", "after": "date__gt"}[op]
        return Q(**{lookup: _date(value)})
    if field == "amount":
        if op == "between":
            low, high = _range(value, _decimal)
            return Q(line_amount__gte=low, line_amount__lte=high)
        lookup = "line_amount" if op == "eq" else f"line_amount__{op}"
        return Q(**{lookup: _decimal(value)})
    if field == "tax_code":
        return Q(tax_code="") if op == "empty" else Q(tax_code__in=[str(v) for v in _list(value)])
    if field == "entered_by":
        (user,) = _uuids(value)[:1]
        return Q(entry__posted_by__public_id=user)
    if field == "contact":
        if op == "empty":
            return Q(contact__isnull=True)
        return Q(contact__public_id__in=_uuids(value))
    if field == "number":
        try:
            return Q(entry__number=int(str(value)))
        except (TypeError, ValueError) as error:
            raise Invalid from error
    if field == "reference":
        text = str(value or "").strip()
        if not text:
            raise Invalid
        return Q(entry__narration__icontains=text) | Q(description__icontains=text)
    if field == "tracking":
        if not isinstance(value, dict) or len(value) != 1:
            raise Invalid
        ((category, option),) = value.items()
        return Q(tracking__contains={str(category): option})
    # book
    if value not in Book.values:
        raise Invalid
    return Q(book=value) if value == Book.BOTH else Q(book__in=[value, Book.BOTH])


def criteria_q(criteria: Any) -> Q:
    """The filter of the whole search (``ValidationError`` naming the first bad condition)."""
    if not isinstance(criteria, dict):
        raise _refuse(0, _("The search isn't a list of conditions."))
    match = criteria.get("match", "all")
    conditions = criteria.get("conditions") or []
    if match not in ("all", "any") or not isinstance(conditions, list) or not conditions:
        raise _refuse(0, _("Add at least one condition, matching all or any of them."))
    parts = []
    for position, condition in enumerate(conditions, start=1):
        try:
            parts.append(condition_q(condition))
        except Invalid:
            raise _refuse(
                position,
                _("Condition %(condition)s isn't a search we can run.") % {"condition": position},
            ) from None
    return reduce((lambda a, b: a & b) if match == "all" else (lambda a, b: a | b), parts)


def _asks_status(criteria: Any) -> bool:
    return any(
        isinstance(c, dict) and c.get("field") == "status" for c in criteria.get("conditions", [])
    )


def find_lines(organisation: Any, criteria: Any) -> QuerySet[JournalLine]:
    """The matching lines (module docstring)."""
    q = criteria_q(criteria)
    base = JournalLine.objects.filter(organisation=organisation)
    statuses = SEARCHED_STATUSES if _asks_status(criteria) else (JournalStatus.POSTED,)
    base = base.filter(entry__status__in=statuses).annotate(
        line_amount=Greatest(F("debit"), F("credit"))
    )
    found: QuerySet[JournalLine] = (
        base.filter(q)
        .select_related("entry", "account", "contact")
        .distinct()
        .order_by("entry__date", "entry_id", "line_no")
    )
    return found
