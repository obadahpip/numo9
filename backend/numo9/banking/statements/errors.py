"""Statement import messages (F-02-T03, catalogue completed in F-02-T15).

Every message is a stable key in the A-10 error catalogue (``numo9.i18n.errors.define``) plus a
gettext text that says **which row** and **what to do** — "Row 14: date '13/25/2026' doesn't
match DD/MM/YYYY. …". Line problems (``row.*``) are reported per line in the preview; file and
layout problems refuse the whole file; import problems answer the API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import status

from numo9.i18n.errors import ErrorMessage, define

# ---- line problems (one row of the file) --------------------------------------------------------
ROW_DATE_MISSING = define(
    "banking.statement.row.date_missing",
    _("Row %(row)s: the date is empty. Fill it in, or remove the row from the file."),
)
ROW_DATE_FORMAT = define(
    "banking.statement.row.date_format",
    _(
        "Row %(row)s: date '%(value)s' doesn't match %(format)s. Choose the date format your "
        "bank uses on the Map step, or correct the row."
    ),
)
ROW_AMOUNT_MISSING = define(
    "banking.statement.row.amount_missing",
    _(
        "Row %(row)s: there's no amount. Map the amount column (or the withdrawal and deposit "
        "columns) on the Map step, or remove the row."
    ),
)
ROW_AMOUNT_INVALID = define(
    "banking.statement.row.amount_invalid",
    _(
        "Row %(row)s: amount '%(value)s' isn't a number. Check the decimal separator on the Map "
        "step, or correct the row."
    ),
)
ROW_AMOUNT_TOO_LARGE = define(
    "banking.statement.row.amount_too_large",
    _("Row %(row)s: amount '%(value)s' is too large. Correct the row."),
)
ROW_TWO_AMOUNTS = define(
    "banking.statement.row.two_amounts",
    _(
        "Row %(row)s: both the withdrawal (%(debit)s) and the deposit (%(credit)s) columns have "
        "an amount. Keep only one of them in the row."
    ),
)

# ---- layout problems (how the columns are read) -------------------------------------------------
LAYOUT_NO_DATE = define(
    "banking.statement.layout.no_date",
    _("Choose the column that holds the date."),
)
LAYOUT_NO_AMOUNT = define(
    "banking.statement.layout.no_amount",
    _("Choose the amount column, or the withdrawal and deposit columns."),
)
LAYOUT_NO_DEBIT_CREDIT = define(
    "banking.statement.layout.no_debit_credit",
    _(
        "With separate withdrawal and deposit columns, choose both columns (or switch to a single "
        "amount column)."
    ),
)
LAYOUT_DATE_FORMAT = define(
    "banking.statement.layout.date_format",
    _("“%(format)s” isn't a date format Numo9 knows. Choose one from the list."),
)
LAYOUT_INVALID = define(
    "banking.statement.layout.invalid",
    _("The column mapping is incomplete: %(reason)s"),
)


@dataclass(frozen=True)
class LineProblem:
    """Why one line can't be imported: a catalogue key and the message's parameters."""

    error: ErrorMessage
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def code(self) -> str:
        return self.error.code

    def message(self) -> str:
        """The message in the active language."""
        return self.error.text(**self.params)


class StatementError(ValidationError):
    """A whole file, layout or import is refused; ``error`` is its catalogue entry."""

    def __init__(self, error: ErrorMessage, status_code: int | None = None, **params: Any) -> None:
        super().__init__(error.text(**params), code=error.code)
        self.error = error
        self.error_params = params
        self.status_code = status_code or error.status or status.HTTP_400_BAD_REQUEST

    @property
    def text(self) -> str:
        """The message in the active language (translated when read, not when raised)."""
        return self.error.text(**self.error_params)
