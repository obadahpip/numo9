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
ROW_DUPLICATE = define(
    "banking.statement.row.duplicate",
    _(
        "Row %(row)s is already in this account (imported before, or from an overlapping "
        "statement). It won't be imported twice."
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


# ---- file problems (the whole file is refused) --------------------------------------------------
FILE_EMPTY = define(
    "banking.statement.file.empty",
    _(
        "%(name)s has no statement lines. Download the statement again for a period with "
        "transactions."
    ),
)
FILE_TYPE = define(
    "banking.statement.file.type",
    _(
        "%(name)s isn't a statement file Numo9 can read. Download the statement from your bank "
        "as CSV, Excel (.xlsx), OFX, QFX or QBO and try again."
    ),
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
)
FILE_LEGACY_XLS = define(
    "banking.statement.file.legacy_xls",
    _(
        "%(name)s is an old Excel (.xls) file. Open it in Excel and save it as .xlsx or .csv, or "
        "download the statement as CSV, then try again."
    ),
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
)
FILE_UNREADABLE = define(
    "banking.statement.file.unreadable",
    _("%(name)s can't be opened: it may be damaged or password-protected. Download it again."),
)
FILE_MALFORMED = define(
    "banking.statement.file.malformed",
    _("%(name)s is malformed near row %(row)s (%(reason)s). Download the statement again."),
)
FILE_TOO_LARGE = define(
    "banking.statement.file.too_large",
    _("%(name)s is larger than %(max)s MB. Download a shorter period and try again."),
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
)
FILE_TOO_MANY_LINES = define(
    "banking.statement.file.too_many_lines",
    _("%(name)s has more than %(max)s lines. Download a shorter period and try again."),
)
FILE_TOO_MANY_COLUMNS = define(
    "banking.statement.file.too_many_columns",
    _("%(name)s has more than %(max)s columns. Check that it is a bank statement."),
)
OFX_NO_STATEMENT = define(
    "banking.statement.file.no_statement",
    _(
        "%(name)s has no bank or credit-card statement in it. Download the account's statement "
        "(not an investment or tax file) and try again."
    ),
)
OFX_SEVERAL_ACCOUNTS = define(
    "banking.statement.file.several_accounts",
    _(
        "The file holds %(count)s accounts; only account %(account)s is imported. Download one "
        "file per account to import the others."
    ),
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
