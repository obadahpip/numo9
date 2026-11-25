"""C-07-T02 — find & recode query builder: each condition type returns the expected lines of the
fixture (tests/recode_helpers.py), all / any, org scope, refusals."""

from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ValidationError

from numo9.ledger.recode_query import find_lines
from numo9.ledger.services import reverse
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.recode_helpers import recode_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return recode_books()


def found(
    books: dict[str, Any], *conditions: dict[str, Any], match: str = "all"
) -> list[tuple[int, int]]:
    """(entry index 1–4 in the fixture, line_no) of the matching lines."""
    index = {e.pk: n for n, e in enumerate(books["entries"], start=1)}
    with org_context(books["org"]):
        lines = find_lines(books["org"], {"match": match, "conditions": list(conditions)})
        return [(index.get(line.entry_id, 0), line.line_no) for line in lines]


def pid(books: dict[str, Any], key: str) -> str:
    return str(books[key].public_id)


CASES: list[tuple[str, Any, list[tuple[int, int]]]] = [
    ("type", lambda b: {"field": "type", "op": "is", "value": "sales"}, [(1, 1), (1, 2)]),
    (
        "account is",
        lambda b: {"field": "account", "op": "is", "value": pid(b, "expense")},
        [(2, 1), (4, 1)],
    ),
    (
        "account in",
        lambda b: {
            "field": "account",
            "op": "in",
            "value": [pid(b, "expense"), pid(b, "expense2")],
        },
        [(2, 1), (3, 1), (4, 1)],
    ),
    (
        "account not",
        lambda b: {"field": "account", "op": "not", "value": [pid(b, "bank")]},
        [(1, 2), (2, 1), (3, 1), (4, 1)],
    ),
    (
        "bank account",
        lambda b: {"field": "bank_account", "op": "is", "value": pid(b, "bank")},
        [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2), (4, 1), (4, 2)],
    ),
    ("date on", lambda b: {"field": "date", "op": "on", "value": "2026-02-15"}, [(2, 1), (2, 2)]),
    (
        "date before",
        lambda b: {"field": "date", "op": "before", "value": "2026-02-15"},
        [(1, 1), (1, 2)],
    ),
    (
        "date after",
        lambda b: {"field": "date", "op": "after", "value": "2026-03-20"},
        [(4, 1), (4, 2)],
    ),
    (
        "date between",
        lambda b: {
            "field": "date",
            "op": "between",
            "value": {"from": "2026-02-01", "to": "2026-03-31"},
        },
        [(2, 1), (2, 2), (3, 1), (3, 2)],
    ),
    ("amount eq", lambda b: {"field": "amount", "op": "eq", "value": "200"}, [(2, 1), (2, 2)]),
    ("amount gt", lambda b: {"field": "amount", "op": "gt", "value": "200"}, [(1, 1), (1, 2)]),
    (
        "amount between",
        lambda b: {"field": "amount", "op": "between", "value": {"from": "50", "to": "75"}},
        [(3, 1), (3, 2), (4, 1), (4, 2)],
    ),
    (
        "tax code",
        lambda b: {"field": "tax_code", "op": "is", "value": "sales.ON.standard"},
        [(1, 2)],
    ),
    (
        "tax code empty",
        lambda b: {"field": "tax_code", "op": "empty"},
        [(1, 1), (2, 2), (3, 1), (3, 2), (4, 1), (4, 2)],
    ),
    (
        "entered by",
        lambda b: {"field": "entered_by", "op": "is", "value": pid(b, "owner")},
        [(2, 1), (2, 2)],
    ),
    ("contact", lambda b: {"field": "contact", "op": "is", "value": pid(b, "bolt")}, [(2, 1)]),
    (
        "contact empty",
        lambda b: {"field": "contact", "op": "empty"},
        [(1, 1), (2, 2), (3, 1), (3, 2), (4, 1), (4, 2)],
    ),
    (
        "number",
        lambda b: {"field": "number", "op": "is", "value": b["entries"][2].number},
        [(3, 1), (3, 2)],
    ),
    (
        "reference",
        lambda b: {"field": "reference", "op": "contains", "value": "rent"},
        [(3, 1), (3, 2)],
    ),
    (
        "tracking",
        lambda b: {"field": "tracking", "op": "is", "value": {"region": "west"}},
        [(3, 1)],
    ),
    (
        "book tax",
        lambda b: {"field": "book", "op": "is", "value": "tax"},
        [(1, 1), (1, 2), (2, 1), (2, 2), (4, 1), (4, 2)],
    ),
    (
        "book both",
        lambda b: {"field": "book", "op": "is", "value": "both"},
        [(1, 1), (1, 2), (2, 1), (2, 2)],
    ),
]


@pytest.mark.parametrize(("name", "condition", "expected"), CASES, ids=[c[0] for c in CASES])
def test_each_condition(
    books: dict[str, Any], name: str, condition: Any, expected: list[tuple[int, int]]
) -> None:
    assert found(books, condition(books)) == expected


def test_all_and_any(books: dict[str, Any]) -> None:
    expense = {"field": "account", "op": "is", "value": pid(books, "expense")}
    tax_book = {"field": "book", "op": "is", "value": "tax"}
    assert found(books, expense, {"field": "date", "op": "after", "value": "2026-03-01"}) == [
        (4, 1)
    ]
    assert found(
        books, expense, {"field": "contact", "op": "is", "value": pid(books, "acme")}, match="any"
    ) == [(1, 2), (2, 1), (4, 1)]
    assert found(books, expense, tax_book) == [(2, 1), (4, 1)]


def test_status_and_org_scope(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        reverse(books["entries"][3], user=books["adviser"])
    expense = {"field": "account", "op": "is", "value": pid(books, "expense")}
    # the reversed entry is left out; its (posted) reversal is found — the exclusion engine
    # (C-07-T03) lists it with its reason
    assert found(books, expense) == [(2, 1), (0, 1)]
    assert found(books, expense, {"field": "status", "op": "is", "value": "reversed"}) == [(4, 1)]
    other = Organisation.objects.create(name="Other Co")
    with org_context(other):
        assert list(find_lines(other, {"conditions": [expense]})) == []


@pytest.mark.parametrize(
    "criteria",
    [
        {"conditions": []},
        {"match": "most", "conditions": [{"field": "type", "op": "is", "value": "sales"}]},
        {"conditions": [{"field": "colour", "op": "is", "value": "red"}]},
        {"conditions": [{"field": "date", "op": "between", "value": "2026-01-01"}]},
        {"conditions": [{"field": "amount", "op": "gt", "value": "lots"}]},
        {"conditions": [{"field": "account", "op": "is", "value": "not-a-uuid"}]},
        {"conditions": [{"field": "status", "op": "is", "value": "draft"}]},
        {"conditions": [{"field": "book", "op": "is", "value": "cash"}]},
    ],
)
def test_refused(books: dict[str, Any], criteria: dict[str, Any]) -> None:
    with org_context(books["org"]), pytest.raises(ValidationError) as caught:
        list(find_lines(books["org"], criteria))
    assert caught.value.code == "ledger.recode.condition_invalid"
