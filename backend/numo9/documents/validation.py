"""Side validator (D-01-T06): every line of a document fits its side and its date.

``validate_lines(kind, date, lines)`` checks, per line (numbered from 1):

- the **account** is allowed for the side (``numo9.ledger.contexts``: sales — revenue, other
  income, deposits; purchase — expenses and the assets a bill buys; never archived, never an
  account the engine posts to) and has no sub-accounts;
- the **tax code** belongs to the side (a purchase code on an invoice line is refused, gap-07);
- the tax code version is **in force on the document date** and not archived (G-01-T08) —
  an old draft whose date moves past a rate change is flagged: re-pick the code;
- the document's **tax mode** is known; a no-tax document carries no tax codes.

All problems are collected and raised together as ``DocumentInvalid`` (a ``LedgerError`` with
code ``documents.lines.invalid``) whose ``problems`` name the line, the field and a message key —
the API answers 400 with them (D-01-T09).

Document kinds and their side: quote, invoice, credit note, recurring invoice → sales; bill,
purchase order, supplier credit, expense claim → purchase.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.contexts import allowed_in_context
from numo9.ledger.models import Account, LedgerError

from .models import TaxMode

SALES = "sales"
PURCHASE = "purchase"

SIDES: dict[str, str] = {
    "quote": SALES,
    "invoice": SALES,
    "credit_note": SALES,
    "recurring_invoice": SALES,
    "bill": PURCHASE,
    "purchase_order": PURCHASE,
    "supplier_credit": PURCHASE,
    "expense_claim": PURCHASE,
}


@dataclass(frozen=True)
class LineProblem:
    line: int
    field: str
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {"line": self.line, "field": self.field, "code": self.code, "message": self.message}


class DocumentInvalid(LedgerError):
    """One or more lines don't fit the document (``problems``)."""

    def __init__(self, problems: Sequence[LineProblem]) -> None:
        self.problems = tuple(problems)
        first = self.problems[0]
        message = (
            _("Line %(line)d: %(message)s") % {"line": first.line, "message": first.message}
            if first.line
            else first.message
        )
        # The message is final (no params: it isn't %-formatted again — rates say "13 %").
        super().__init__(message, code="documents.lines.invalid")


@dataclass(frozen=True)
class LineCheck:
    """What the validator reads from a line: its account and tax code version (either may be
    None) — model lines, API input and calculator rows all map to this."""

    account: Account | None = None
    tax_code: Any = None


def side_of(kind: str) -> str:
    try:
        return SIDES[kind]
    except KeyError:
        raise LedgerError(
            _("Unknown document type %(kind)s."),
            code="documents.kind.unknown",
            params={"kind": kind},
        ) from None


def _account_problem(number: int, account: Account, side: str) -> LineProblem | None:
    from numo9.ledger.tree import has_children

    label = f"{account.code} {account.name}"
    if not allowed_in_context(account, side):
        message = (
            _(
                "%(account)s can't be used on a sales line: choose a revenue or other income "
                "account."
            )
            if side == SALES
            else _(
                "%(account)s can't be used on a purchase line: choose an expense or asset account."
            )
        )
        return LineProblem(
            number, "account", f"documents.line.account_{side}", message % {"account": label}
        )
    if has_children(account):
        return LineProblem(
            number,
            "account",
            "documents.line.account_parent",
            _("%(account)s has sub-accounts: choose one of them.") % {"account": label},
        )
    return None


def _tax_problem(number: int, code: Any, side: str, day: dt.date) -> LineProblem | None:
    from numo9.tax.resolver import TaxCodeExpired, check_code

    if code.side != side:
        message = (
            _("%(code)s is a purchase tax code: choose a sales tax code.")
            if side == SALES
            else _("%(code)s is a sales tax code: choose a purchase tax code.")
        )
        return LineProblem(
            number, "tax_code", "documents.line.tax_side", message % {"code": code.name}
        )
    if code.archived_at is not None:
        return LineProblem(
            number,
            "tax_code",
            "tax.code.archived",
            _("%(code)s is archived: choose another code.") % {"code": code.name},
        )
    try:
        check_code(code, day)
    except TaxCodeExpired as error:
        return LineProblem(number, "tax_code", "tax.code.expired", str(error))
    return None


def problems(
    kind: str, day: dt.date, lines: Sequence[LineCheck], *, tax_mode: str = TaxMode.EXCLUSIVE
) -> list[LineProblem]:
    side = side_of(kind)
    found: list[LineProblem] = []
    if tax_mode not in TaxMode.values:
        found.append(
            LineProblem(
                0,
                "tax_mode",
                "documents.tax_mode.unknown",
                _("Choose tax exclusive, tax inclusive or no tax."),
            )
        )
    # One check per account, however many lines use it (50 lines on one account: one query).
    account_problems: dict[int, LineProblem | None] = {}
    for number, line in enumerate(lines, start=1):
        if line.account is not None:
            key = line.account.pk
            if key not in account_problems:
                account_problems[key] = _account_problem(1, line.account, side)
            problem = account_problems[key]
            if problem:
                found.append(LineProblem(number, problem.field, problem.code, problem.message))
        if line.tax_code is not None:
            if tax_mode == TaxMode.NO_TAX:
                found.append(
                    LineProblem(
                        number,
                        "tax_code",
                        "documents.line.tax_not_allowed",
                        _("The amounts have no tax: remove the tax code."),
                    )
                )
                continue
            problem = _tax_problem(number, line.tax_code, side, day)
            if problem:
                found.append(problem)
    return found


def validate_lines(
    kind: str, day: dt.date, lines: Sequence[LineCheck], *, tax_mode: str = TaxMode.EXCLUSIVE
) -> None:
    """Raise ``DocumentInvalid`` naming every problem (module docstring)."""
    found = problems(kind, day, lines, tax_mode=tax_mode)
    if found:
        raise DocumentInvalid(found)
