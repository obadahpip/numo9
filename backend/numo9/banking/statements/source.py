"""Statement sources (F-02-T03): where statement lines come from.

Every way lines reach Numo9 goes through one interface, so the preview, duplicate detection and
commit (F-02-T07 – T09) never care where a line came from:

``BankStatementSource``

- ``source_name`` — a short stable name stored on the import batch (``StatementImport
  .source_name``): ``file`` for uploads; Numo9's own banking app (W-02) adds ``numo9_bank``;
- ``fetch_lines()`` — the statement's lines as normalised ``RawLine`` objects (``layout``), in
  the order the statement gives them: date, amount signed from the account holder's side
  (positive = money in), description, payee, reference, the bank's transaction ID (``fitid``),
  the running balance when given, and the problems of a line that can't be read (each naming the
  row and the fix). A source never drops a line silently: an unreadable line is returned with
  its problems and the preview reports it;
- ``balances()`` — the statement's opening and closing balance when the source knows them
  (F-02-T14), else ``StatementBalances()``.

``FileStatementSource(data, filename, layout=None)`` reads an uploaded file. The file's format
is recognised from its content (``parse_statement``, F-02-T04: OFX / QFX / QBO, CSV, XLSX).
Structured formats (OFX family) carry their own fields; tabular ones (CSV, XLSX) need a
``Layout`` — the column roles, date format and sign convention of a saved mapping (F-02-T05) —
and ``fetch_lines()`` refuses to guess without one (``LayoutRequired``).
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cached_property
from typing import ClassVar

from .layout import Layout, RawLine, Table, apply_layout

__all__ = [
    "Balance",
    "BankStatementSource",
    "FileStatementSource",
    "LayoutRequired",
    "ParsedStatement",
    "RawLine",
    "StatementBalances",
    "set_parser",
]


@dataclass(frozen=True)
class Balance:
    amount: Decimal
    date: dt.date | None = None


@dataclass(frozen=True)
class StatementBalances:
    """Opening and closing balance of a statement (either may be unknown)."""

    opening: Balance | None = None
    closing: Balance | None = None


@dataclass(frozen=True)
class ParsedStatement:
    """What a parser read from a file (F-02-T04).

    ``format`` — ``ofx``, ``qfx``, ``qbo``, ``csv`` or ``xlsx``; ``encoding`` / ``delimiter`` —
    what was detected (shown in the wizard); exactly one of ``lines`` (structured formats:
    already normalised) and ``table`` (tabular formats: rows of text, read with a layout).
    ``balances`` and ``account_id`` (the bank's account number in an OFX file) when the file has
    them; ``warnings`` — things the person should know (several accounts in one file…)."""

    format: str
    encoding: str = ""
    delimiter: str = ""
    lines: tuple[RawLine, ...] | None = None
    table: Table | None = None
    balances: StatementBalances = field(default_factory=StatementBalances)
    account_id: str = ""
    currency: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_tabular(self) -> bool:
        return self.table is not None


class LayoutRequired(LookupError):
    """A CSV / XLSX file is read only with a layout (the columns are never guessed silently)."""


class BankStatementSource(ABC):
    """The interface every statement source implements (see the module docstring)."""

    source_name: ClassVar[str]

    @abstractmethod
    def fetch_lines(self) -> list[RawLine]:
        """The statement's lines, normalised, in statement order."""

    def balances(self) -> StatementBalances:
        return StatementBalances()


Parser = Callable[[bytes, str], ParsedStatement]

#: The file parser (``parsers.parse_statement``, F-02-T04); a seam so the source can be tested on
#: its own and so another parser can be plugged in.
_parser: Parser | None = None


def set_parser(parser: Parser | None) -> Parser | None:
    """Install the file parser; returns the previous one."""
    global _parser  # noqa: PLW0603 - a module-level seam, set once at import
    previous, _parser = _parser, parser
    return previous


def _parse(data: bytes, filename: str, last4: str = "") -> ParsedStatement:
    if _parser is None:
        from . import parsers  # noqa: F401 - installs parsers.parse_statement

    assert _parser is not None  # noqa: S101 - parsers installs it on import
    if last4:
        return _parser(data, filename, last4=last4)  # type: ignore[call-arg]
    return _parser(data, filename)


class FileStatementSource(BankStatementSource):
    """An uploaded statement file (see the module docstring)."""

    source_name = "file"

    def __init__(
        self, data: bytes, filename: str, layout: Layout | None = None, *, last4: str = ""
    ) -> None:
        self.data = data
        self.filename = filename
        self.layout = layout
        self.last4 = last4  # an OFX file with several accounts: the one ending with these

    @cached_property
    def parsed(self) -> ParsedStatement:
        """The parsed file (raises the parser's ``StatementError`` for a file it refuses)."""
        return _parse(self.data, self.filename, self.last4)

    @property
    def format(self) -> str:
        return self.parsed.format

    def with_layout(self, layout: Layout | None) -> FileStatementSource:
        """The same file read with another layout (parsed once)."""
        other = FileStatementSource(self.data, self.filename, layout, last4=self.last4)
        if "parsed" in self.__dict__:
            other.__dict__["parsed"] = self.parsed
        return other

    def fetch_lines(self) -> list[RawLine]:
        parsed = self.parsed
        if parsed.lines is not None:
            return list(parsed.lines)
        if self.layout is None or parsed.table is None:
            raise LayoutRequired(self.filename)
        return list(apply_layout(parsed.table, self.layout))

    def balances(self) -> StatementBalances:
        return self.parsed.balances
