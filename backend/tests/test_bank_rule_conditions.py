"""F-04-T04 — condition evaluator: every operator, case-insensitive with accent folding; regex
with a 50 ms timeout guard.

Acceptance: the operator truth table passes (parametrised); a malicious (catastrophically
backtracking) regex is refused at save; a pattern that times out at evaluation never matches;
operators that don't fit the field, missing values and reversed ranges are refused at save.
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from numo9.banking.rules import conditions as C
from numo9.banking.rules.conditions import Condition, LineFacts, evaluate, validate_condition

LINE = LineFacts(
    amount=Decimal("-45.10"),
    payee="Café Dépanneur",
    description="PETRO-CANADA  #1234 Montréal",
    reference="",
)


@pytest.mark.parametrize(
    ("field", "operator", "value", "value_to", "expected"),
    [
        # equals — case, accents and repeated spaces ignored
        ("payee", "equals", "cafe depanneur", "", True),
        ("payee", "equals", "CAFÉ", "", False),
        ("description", "equals", "petro-canada #1234 montreal", "", True),
        # contains / does not contain
        ("description", "contains", "petro", "", True),
        ("description", "contains", "MONTREAL", "", True),
        ("description", "contains", "shell", "", False),
        ("description", "not_contains", "shell", "", True),
        ("description", "not_contains", "Petro", "", False),
        # starts / ends with
        ("description", "starts_with", "PETRO-can", "", True),
        ("description", "starts_with", "canada", "", False),
        ("description", "ends_with", "montréal", "", True),
        ("description", "ends_with", "#1234", "", False),
        # regex — case-insensitive, accent-folded
        ("description", "regex", r"petro.?canada\s+#\d{4}", "", True),
        ("description", "regex", r"^shell", "", False),
        ("payee", "regex", r"^caf[eé] d", "", True),
        # is blank
        ("reference", "is_blank", "", "", True),
        ("payee", "is_blank", "", "", False),
        # any text field
        ("any_text", "contains", "dépanneur", "", True),
        ("any_text", "contains", "nowhere", "", False),
        ("any_text", "not_contains", "nowhere", "", True),
        ("any_text", "not_contains", "petro", "", False),
        ("any_text", "is_blank", "", "", False),
        ("any_text", "regex", r"\d{4}", "", True),
        # amount — without its sign, bounds included
        ("amount", "equals", "45.10", "", True),
        ("amount", "equals", "45", "", False),
        ("amount", "between", "20", "200", True),
        ("amount", "between", "45.10", "45.10", True),
        ("amount", "between", "50", "200", False),
        ("amount", "gt", "45", "", True),
        ("amount", "gt", "45.10", "", False),
        ("amount", "lt", "45.11", "", True),
        ("amount", "lt", "45.10", "", False),
    ],
)
def test_truth_table(field: str, operator: str, value: str, value_to: str, expected: bool) -> None:
    condition = Condition(field, operator, value, value_to)
    validate_condition(condition)
    assert evaluate(condition, LINE) is expected


def test_blank_any_text_and_mismatched_operator_never_match() -> None:
    blank = LineFacts(amount=Decimal("10"))
    assert evaluate(Condition("any_text", "is_blank"), blank) is True
    assert evaluate(Condition("amount", "contains", "10"), blank) is False
    assert evaluate(Condition("amount", "between", "x", "y"), blank) is False


def test_match_modes() -> None:
    fuel = [Condition("description", "contains", "petro"), Condition("amount", "gt", "100")]
    assert C.matches_all(fuel, LINE, mode="all") is False
    assert C.matches_all(fuel, LINE, mode="any") is True
    assert C.matches_all([], LINE, mode="any") is False


@pytest.mark.parametrize("pattern", [r"(a|aa)+$", r"(a|a)+b", r"((a+)+)+b", r"^(a+)+(b+)+$"])
def test_malicious_regex_refused_at_save(pattern: str) -> None:
    started = time.monotonic()
    with pytest.raises(ValidationError) as caught:
        validate_condition(Condition("description", "regex", pattern))
    assert caught.value.code == "banking.rule.regex_slow"
    assert time.monotonic() - started < 2


def test_regex_timeout_at_evaluation_is_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    class Slow:
        def search(self, text: str, timeout: float) -> None:
            assert timeout == C.REGEX_TIMEOUT == 0.05
            raise TimeoutError

    monkeypatch.setattr(C, "compile_pattern", lambda pattern: Slow())
    assert evaluate(Condition("description", "regex", "petro"), LINE) is False


@pytest.mark.parametrize(
    ("condition", "code"),
    [
        (Condition("description", "regex", "(unclosed"), "banking.rule.regex_invalid"),
        (Condition("description", "regex", "a" * 501), "banking.rule.regex_too_long"),
        (Condition("description", "regex", ""), "banking.rule.value_required"),
        (Condition("payee", "contains", "  "), "banking.rule.value_required"),
        (Condition("payee", "between", "1", "2"), "banking.rule.operator_field"),
        (Condition("amount", "contains", "1"), "banking.rule.operator_field"),
        (Condition("amount", "gt", "abc"), "banking.rule.amount_invalid"),
        (Condition("amount", "gt", "-5"), "banking.rule.amount_invalid"),
        (Condition("amount", "between", "200", "20"), "banking.rule.range_invalid"),
        (Condition("memo", "contains", "x"), "banking.rule.field"),
        (Condition("payee", "sounds_like", "x"), "banking.rule.operator"),
    ],
)
def test_invalid_conditions_refused(condition: Condition, code: str) -> None:
    with pytest.raises(ValidationError) as caught:
        validate_condition(condition)
    assert caught.value.code == code
