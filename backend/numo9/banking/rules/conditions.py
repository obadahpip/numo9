"""Condition evaluator of the bank rules (F-04-T04).

A condition is ``field`` ``operator`` ``value`` (``value_to`` for *amount between*):

- text fields — ``payee``, ``description``, ``reference`` and ``any_text`` (any of the three) —
  take ``equals``, ``contains``, ``not_contains``, ``starts_with``, ``ends_with``, ``regex`` and
  ``is_blank``. Comparisons are **case-insensitive with accent folding** ("CAFÉ" equals "cafe")
  and ignore repeated spaces. On ``any_text`` a positive operator matches when one field does;
  ``not_contains`` when no field contains the value; ``is_blank`` when every field is blank.
- ``amount`` takes ``equals``, ``gt``, ``lt`` and ``between`` (both bounds included) and compares
  the line's amount **without its sign** (a spend of 45.00 is −45.00 on the statement).

**Regex safety.** Patterns run on the ``regex`` engine with a **50 ms timeout**; a pattern that
times out never matches (it is not an error at evaluation time). At save, ``validate_condition``
refuses a pattern that does not compile, is longer than 500 characters, or exceeds the timeout
on adversarial probe texts built from its own characters (catastrophic backtracking such as
``(a|aa)+$``): code ``banking.rule.regex_slow``.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any

import regex  # type: ignore[import-untyped]
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from ..models import AMOUNT_OPERATORS, TEXT_OPERATORS, ConditionField, ConditionOperator

#: The time a pattern may take on one text (F-04 business rule: 50 ms).
REGEX_TIMEOUT = 0.05
MAX_PATTERN = 500
TEXT_FIELDS = ("payee", "description", "reference")
_PROBE_LENGTH = 5000
Op = ConditionOperator


@dataclass(frozen=True)
class Condition:
    field: str
    operator: str
    value: str = ""
    value_to: str = ""


@dataclass(frozen=True)
class LineFacts:
    """What a rule reads from a statement line."""

    amount: Decimal
    payee: str = ""
    description: str = ""
    reference: str = ""
    bank_account_id: int | None = None
    id: int | None = None

    @classmethod
    def of(cls, line: Any) -> LineFacts:
        return cls(
            amount=Decimal(line.amount),
            payee=line.payee or "",
            description=line.description or "",
            reference=line.reference or "",
            bank_account_id=line.bank_account_id,
            id=line.pk,
        )


def fold(text: str) -> str:
    """Lower-case, accents removed, spaces collapsed: what text comparisons compare."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(plain.casefold().split())


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return unicodedata.normalize(
        "NFC", "".join(c for c in decomposed if not unicodedata.combining(c))
    )


@lru_cache(maxsize=512)
def compile_pattern(pattern: str) -> Any:
    """The pattern compiled case-insensitively, its accents folded like the text."""
    return regex.compile(_strip_accents(pattern), regex.IGNORECASE | regex.V0)


def regex_search(pattern: str, text: str) -> bool:
    """Does ``pattern`` occur in ``text``? False when it times out (50 ms)."""
    try:
        return (
            compile_pattern(pattern).search(_strip_accents(text), timeout=REGEX_TIMEOUT) is not None
        )
    except TimeoutError:
        return False


def _probes(pattern: str) -> list[str]:
    chars = [c for c in dict.fromkeys(pattern) if c.isalnum()][:8] or ["a"]
    texts = [c * _PROBE_LENGTH + "!" for c in [*chars, "a", "1", " "]]
    share = _PROBE_LENGTH // len(chars)
    texts.append("".join(c * share for c in chars) + "!")
    texts.append(" ".join(chars) * (_PROBE_LENGTH // (2 * len(chars))) + "!")
    return list(dict.fromkeys(texts))


def validate_pattern(pattern: str) -> None:
    """Refuse a pattern that does not compile, is too long, or backtracks past the timeout."""
    if not pattern:
        raise ValidationError(_("Enter a pattern."), code="banking.rule.value_required")
    if len(pattern) > MAX_PATTERN:
        raise ValidationError(
            _("A pattern has at most %(max)d characters."),
            code="banking.rule.regex_too_long",
            params={"max": MAX_PATTERN},
        )
    try:
        compiled = regex.compile(_strip_accents(pattern), regex.IGNORECASE | regex.V0)
    except regex.error as error:
        raise ValidationError(
            _("This pattern isn't valid: %(error)s."),
            code="banking.rule.regex_invalid",
            params={"error": str(error)},
        ) from error
    for text in _probes(pattern):
        try:
            compiled.search(text, timeout=REGEX_TIMEOUT)
        except TimeoutError as error:
            raise ValidationError(
                _(
                    "This pattern takes too long to run on some texts (catastrophic "
                    "backtracking). Simplify it, for example without nested repeats."
                ),
                code="banking.rule.regex_slow",
            ) from error


def _amount(value: str) -> Decimal | None:
    try:
        number = Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def validate_condition(condition: Condition) -> None:
    """The checks made when a rule is saved: operator allowed for the field, value present and
    of the right kind, the range in order, the pattern safe."""
    if condition.field not in ConditionField.values:
        raise ValidationError(_("Choose what the condition looks at."), code="banking.rule.field")
    if condition.operator not in ConditionOperator.values:
        raise ValidationError(_("Choose how to compare."), code="banking.rule.operator")
    if condition.field == ConditionField.AMOUNT:
        if condition.operator not in AMOUNT_OPERATORS:
            raise ValidationError(
                _("This comparison doesn't apply to an amount."),
                code="banking.rule.operator_field",
            )
        low = _amount(condition.value)
        if low is None or low < 0:
            raise ValidationError(
                _("Enter an amount (0 or more)."), code="banking.rule.amount_invalid"
            )
        if condition.operator == Op.BETWEEN:
            high = _amount(condition.value_to)
            if high is None or high < low:
                raise ValidationError(
                    _("Enter the upper amount, at least the lower one."),
                    code="banking.rule.range_invalid",
                )
        return
    if condition.operator not in TEXT_OPERATORS:
        raise ValidationError(
            _("This comparison applies to amounts only."), code="banking.rule.operator_field"
        )
    if condition.operator == Op.IS_BLANK:
        return
    if condition.operator == Op.REGEX:
        validate_pattern(condition.value)
        return
    if not fold(condition.value):
        raise ValidationError(_("Enter the text to look for."), code="banking.rule.value_required")


def _text_match(operator: str, text: str, value: str) -> bool:
    if operator == Op.IS_BLANK:
        return not fold(text)
    if operator == Op.REGEX:
        return regex_search(value, text)
    folded, wanted = fold(text), fold(value)
    if operator == Op.EQUALS:
        return folded == wanted
    if operator in (Op.CONTAINS, Op.NOT_CONTAINS):
        return wanted in folded
    if operator == Op.STARTS_WITH:
        return folded.startswith(wanted)
    if operator == Op.ENDS_WITH:
        return folded.endswith(wanted)
    return False


def evaluate(condition: Condition, line: LineFacts) -> bool:
    """Does ``line`` meet ``condition``? Invalid conditions never match."""
    op = condition.operator
    if condition.field == ConditionField.AMOUNT:
        amount = abs(Decimal(line.amount))
        low = _amount(condition.value)
        if low is None:
            return False
        if op == Op.EQUALS:
            return amount == low
        if op == Op.GREATER_THAN:
            return amount > low
        if op == Op.LESS_THAN:
            return amount < low
        if op == Op.BETWEEN:
            high = _amount(condition.value_to)
            return high is not None and low <= amount <= high
        return False
    if condition.field == ConditionField.ANY_TEXT:
        texts = [getattr(line, name) for name in TEXT_FIELDS]
    elif condition.field in TEXT_FIELDS:
        texts = [getattr(line, condition.field)]
    else:
        return False
    if op == Op.NOT_CONTAINS:
        return not any(_text_match(Op.CONTAINS, text, condition.value) for text in texts)
    if op == Op.IS_BLANK:
        return all(_text_match(Op.IS_BLANK, text, "") for text in texts)
    return any(_text_match(op, text, condition.value) for text in texts)


def matches_all(conditions: list[Condition], line: LineFacts, *, mode: str) -> bool:
    """``all`` — every condition holds; ``any`` — at least one. A rule without conditions never
    matches (it would code everything)."""
    if not conditions:
        return False
    results = (evaluate(c, line) for c in conditions)
    return all(results) if mode == "all" else any(results)
