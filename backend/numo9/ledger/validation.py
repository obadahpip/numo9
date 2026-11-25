"""Journal validation (C-02-T06, ADR-0003 §1–2): the rules every posting passes.

``validate_journal(spec)`` checks a ``JournalSpec`` (date, lines, type, narration, source) for the
active organisation and returns a ``ValidatedJournal`` (lines with exact ``Decimal`` amounts, the
books the entry touches, totals per book). Any problem raises ``JournalInvalid`` (a
``LedgerError``) listing **every** problem, each with a stable code and a message that names the
exact reason:

=================================  ===============================================================
code                               when
=================================  ===============================================================
``ledger.journal.too_few_lines``   fewer than 2 lines
``ledger.journal.amount_type``     an amount that isn't a ``Decimal``/``int``/decimal string —
                                   floats are refused, never converted (no binary rounding)
``ledger.journal.amount_precision`` more than 2 decimals (the engine never rounds a caller's
                                   split: callers allocate the pennies)
``ledger.journal.amount_negative`` a negative debit or credit
``ledger.journal.amount_too_large`` beyond ``numeric(18, 2)``
``ledger.journal.line_one_side``   both debit and credit, or neither
``ledger.journal.book_invalid``    a book other than both / accounting / tax
``ledger.journal.account_missing`` an account that isn't one of the organisation's
``ledger.journal.contact_missing`` a line contact that isn't one of the organisation's contacts
                                   (another organisation's, or deleted) — C-03-T02
``ledger.account.archived``        an archived account (C-01 ``assert_postable``)
``ledger.account.not_leaf``        a parent account (post to a sub-account)
``ledger.journal.unbalanced``      debits ≠ credits in a book the entry touches —
                                   "Debits 1,000.00 ≠ credits 999.99 in the tax book
                                   (difference 0.01)"
=================================  ===============================================================

**Books** — the accounting book is the lines with ``book`` ∈ {both, accounting}, the tax book the
lines with ``book`` ∈ {both, tax}. The entry must balance in **each book it touches**; its
``book_scope`` is ``both`` when it touches both books, else the one it touches.

The lock-date and period checks are C-02-T07; numbering, insertion and the audit event are the
posting service (C-02-T08), which calls this first.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import translation
from django.utils.translation import gettext as _

from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation

from .models import (
    MONEY_DIGITS,
    MONEY_PLACES,
    Account,
    Book,
    JournalCategory,
    JournalType,
    LedgerError,
)
from .tree import assert_postable

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
#: The largest amount numeric(18, 2) holds.
MAX_AMOUNT = Decimal(10 ** (MONEY_DIGITS - MONEY_PLACES)) - CENT
BOOKS_OF_LINE: dict[str, tuple[str, ...]] = {
    Book.BOTH: (Book.ACCOUNTING, Book.TAX),
    Book.ACCOUNTING: (Book.ACCOUNTING,),
    Book.TAX: (Book.TAX,),
}


class JournalInvalid(LedgerError):
    """The journal breaks one or more posting rules; ``error_list`` has every problem."""


@dataclass(frozen=True)
class LineSpec:
    """One line as a caller describes it. ``account`` is an ``Account`` or its id."""

    account: Account | int
    debit: Any = ZERO
    credit: Any = ZERO
    book: str = Book.BOTH
    contact: Any = None
    tracking: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    tax_code: str = ""


@dataclass(frozen=True)
class JournalSpec:
    date: dt.date
    lines: Sequence[LineSpec]
    type: str = JournalType.MANUAL
    narration: str = ""
    source_type: str = ""
    source_id: str = ""
    #: General / Adjusting / Reclass / Tax adjustment, or a system type (C-03-T01).
    journal_type: str = JournalCategory.GENERAL
    #: Post the reversal by itself on this date (C-03-T09).
    auto_reverse_on: dt.date | None = None
    #: A document dated inside a filed tax period, posted knowingly: its tax goes to the next
    #: open return as an adjustment instead of being refused by the Tax lock (G-03-T08).
    late_adjustment: bool = False


@dataclass(frozen=True)
class ValidatedLine:
    line_no: int
    account: Account
    debit: Decimal
    credit: Decimal
    book: str
    spec: LineSpec


@dataclass(frozen=True)
class ValidatedJournal:
    spec: JournalSpec
    lines: tuple[ValidatedLine, ...]
    book_scope: str
    #: Σ debit and Σ credit per book the entry touches: {"accounting": (d, c), "tax": (d, c)}.
    totals: dict[str, tuple[Decimal, Decimal]]


def format_amount(value: Decimal) -> str:
    """``1,000.00`` (English) / ``1 000,00`` (French) — amounts in messages, without currency."""
    whole, cents = f"{abs(value):.2f}".split(".")
    groups = f"{int(whole):,}"
    sign = "-" if value < 0 else ""
    if (translation.get_language() or "").lower().startswith("fr"):
        return f"{sign}{groups.replace(',', ' ')},{cents}"
    return f"{sign}{groups}.{cents}"


def _book_label(book: str) -> str:
    return _("accounting book") if book == Book.ACCOUNTING else _("tax book")


def to_amount(value: Any) -> Decimal:
    """An amount as an exact Decimal; raises ``TypeError``/``ValueError`` for bad input."""
    if isinstance(value, bool | float):
        raise TypeError("float")
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, int):
        amount = Decimal(value)
    elif isinstance(value, str):
        try:
            amount = Decimal(value.strip() or "0")
        except InvalidOperation as exc:
            raise ValueError(value) from exc
    elif value is None:
        amount = ZERO
    else:
        raise TypeError(type(value).__name__)
    if not amount.is_finite():
        raise ValueError(str(value))
    return amount


class _Problems:
    def __init__(self) -> None:
        self.errors: list[ValidationError] = []

    def add(self, message: str, code: str, **params: Any) -> None:
        text = message % params if params else message
        self.errors.append(ValidationError(text, code=code, params=None))


def _amount(problems: _Problems, line_no: int, side: str, raw: Any) -> Decimal | None:
    """The amount quantised to cents, or None after recording why it is refused."""
    side_label = _("debit") if side == "debit" else _("credit")
    try:
        amount = to_amount(raw)
    except TypeError:
        problems.add(
            _("Line %(line)d: the %(side)s must be an exact amount (Decimal), not %(value)r."),
            "ledger.journal.amount_type",
            line=line_no,
            side=side_label,
            value=raw,
        )
        return None
    except ValueError:
        problems.add(
            _("Line %(line)d: “%(value)s” isn't an amount."),
            "ledger.journal.amount_type",
            line=line_no,
            value=raw,
        )
        return None
    if amount != amount.quantize(CENT):
        problems.add(
            _(
                "Line %(line)d: %(value)s has more than two decimals. Amounts are in cents: "
                "allocate the pennies across lines."
            ),
            "ledger.journal.amount_precision",
            line=line_no,
            value=str(amount),
        )
        return None
    if amount < 0:
        problems.add(
            _("Line %(line)d: the %(side)s can't be negative (%(value)s)."),
            "ledger.journal.amount_negative",
            line=line_no,
            side=side_label,
            value=format_amount(amount),
        )
        return None
    if amount > MAX_AMOUNT:
        problems.add(
            _("Line %(line)d: %(value)s is larger than the largest amount the ledger holds."),
            "ledger.journal.amount_too_large",
            line=line_no,
            value=format_amount(amount),
        )
        return None
    return amount.quantize(CENT)


def _accounts(organisation: Organisation, lines: Sequence[LineSpec]) -> dict[int, Account]:
    ids = {line.account.pk if isinstance(line.account, Account) else line.account for line in lines}
    return {
        item.pk: item
        for item in Account._base_manager.filter(
            organisation=organisation, pk__in=[i for i in ids if isinstance(i, int)]
        )
    }


def _contact_key(value: Any) -> int | None:
    if value is None or value == "":
        return None
    pk = getattr(value, "pk", value)
    try:
        return int(pk)
    except (TypeError, ValueError):
        return -1  # not an id at all: reported as missing


def _contacts(organisation: Organisation, lines: Sequence[LineSpec]) -> set[int]:
    from numo9.contacts.models import Contact

    keys = {key for line in lines if (key := _contact_key(line.contact)) and key > 0}
    if not keys:
        return set()
    return set(
        Contact._base_manager.filter(
            organisation=organisation, pk__in=keys, deleted_at__isnull=True
        ).values_list("pk", flat=True)
    )


def validate_journal(
    spec: JournalSpec, organisation: Organisation | None = None
) -> ValidatedJournal:
    """Check every posting rule (module docstring); raise ``JournalInvalid`` with all problems."""
    organisation = organisation or current_org()
    if organisation is None:
        raise ValueError("Validate a journal only with an active organisation.")
    problems = _Problems()
    lines = list(spec.lines)
    if len(lines) < 2:
        problems.add(
            _("A journal needs at least two lines (a debit and a credit); it has %(count)d."),
            "ledger.journal.too_few_lines",
            count=len(lines),
        )
    accounts = _accounts(organisation, lines)
    contacts = _contacts(organisation, lines)
    validated: list[ValidatedLine] = []
    # (debit, credit, book) of every line; balancing needs them all to be valid amounts.
    amounts: list[tuple[Decimal, Decimal, str]] = []
    amounts_valid = True
    for line_no, line in enumerate(lines, start=1):
        debit = _amount(problems, line_no, "debit", line.debit)
        credit = _amount(problems, line_no, "credit", line.credit)
        if debit is None or credit is None or line.book not in BOOKS_OF_LINE:
            amounts_valid = False
        else:
            amounts.append((debit, credit, line.book))
        if debit is not None and credit is not None and (debit > 0) == (credit > 0):
            problems.add(
                _("Line %(line)d needs a debit or a credit, not both and not neither."),
                "ledger.journal.line_one_side",
                line=line_no,
            )
        if line.book not in BOOKS_OF_LINE:
            problems.add(
                _("Line %(line)d: “%(book)s” isn't a book (both, accounting or tax)."),
                "ledger.journal.book_invalid",
                line=line_no,
                book=line.book,
            )
        contact = _contact_key(line.contact)
        if contact is not None and contact not in contacts:
            problems.add(
                _("Line %(line)d: the contact isn't one of this organisation's contacts."),
                "ledger.journal.contact_missing",
                line=line_no,
            )
        key = line.account.pk if isinstance(line.account, Account) else line.account
        account = accounts.get(key) if isinstance(key, int) else None
        if account is None:
            problems.add(
                _("Line %(line)d: the account isn't one of this organisation's accounts."),
                "ledger.journal.account_missing",
                line=line_no,
            )
        else:
            try:
                assert_postable(account)
            except ValidationError as error:
                problems.errors.append(
                    ValidationError(
                        _("Line %(line)d: %(reason)s")
                        % {"line": line_no, "reason": " ".join(error.messages)},
                        code=getattr(error, "code", None) or "ledger.journal.account",
                    )
                )
            validated.append(
                ValidatedLine(line_no, account, debit or ZERO, credit or ZERO, line.book, line)
            )
    # A balance message about a journal whose amounts are themselves wrong would only confuse.
    totals = _totals(amounts) if amounts_valid else {}
    for book, (debits, credits) in totals.items():
        if debits != credits:
            problems.add(
                _(
                    "Debits %(debits)s ≠ credits %(credits)s in the %(book)s "
                    "(difference %(difference)s)."
                ),
                "ledger.journal.unbalanced",
                debits=format_amount(debits),
                credits=format_amount(credits),
                book=_book_label(book),
                difference=format_amount(abs(debits - credits)),
            )
    if problems.errors:
        raise JournalInvalid(problems.errors)
    touched = set(totals)
    scope = Book.BOTH if touched == {Book.ACCOUNTING, Book.TAX} else touched.pop()
    return ValidatedJournal(spec, tuple(validated), scope, totals)


def _totals(lines: Sequence[tuple[Decimal, Decimal, str]]) -> dict[str, tuple[Decimal, Decimal]]:
    sums: dict[str, list[Decimal]] = {}
    for debit, credit, line_book in lines:
        for book in BOOKS_OF_LINE[line_book]:
            debit_credit = sums.setdefault(book, [ZERO, ZERO])
            debit_credit[0] += debit
            debit_credit[1] += credit
    return {book: (values[0], values[1]) for book, values in sums.items()}
