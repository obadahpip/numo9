"""Fingerprints and duplicate detection (F-02-T07).

A statement line's **fingerprint** identifies it across imports (``StatementLine.fingerprint``,
unique per bank account):

    SHA-256( bank account | date | amount | normalised description | FITID or reference | n )

- the **normalised description** ignores case, accents, punctuation and spacing — the same line
  exported as Windows-1252 or UTF-8, or with "Café  Dépôt" vs "CAFE DEPOT", matches;
- the bank's transaction ID (``FITID``) is used when the file has one, else the reference;
- ``n`` is the **sequence counter**: the n-th line of the file with that same date, amount,
  description and reference. Two identical coffees on the same day are lines 1 and 2 — both are
  kept on the first import — and the same file imported again finds both fingerprints already
  there: 0 new lines. A later statement that overlaps the first by whole days numbers the same
  day's identical lines the same way, so the overlap adds nothing either.

Lines that can't be read (problems) get no fingerprint: they are reported, never stored. They
don't take a sequence number, so fixing a broken line later doesn't renumber the others.

``existing_fingerprints(bank, fingerprints)`` — which of them the account already has (queried in
chunks, one index scan each: ``banking_stmt_line_fingerprint``).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence

from ..models import BankAccount, StatementLine
from .layout import RawLine

CHUNK = 5000
_NOT_WORD = re.compile(r"[^A-Z0-9]+")


def normalise_description(text: str) -> str:
    """``"  Café  Dépôt #12 "`` → ``"CAFE DEPOT 12"``."""
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in plain if not unicodedata.combining(c)).upper()
    return " ".join(_NOT_WORD.sub(" ", plain).split())


def line_key(line: RawLine) -> tuple[str, str, str, str]:
    """What makes two lines "the same": date, amount, description, FITID / reference."""
    assert line.date is not None and line.amount is not None  # noqa: S101 - only readable lines
    reference = (line.fitid or line.reference).strip().upper()
    return (
        line.date.isoformat(),
        f"{line.amount:.2f}",
        normalise_description(line.description),
        reference,
    )


def fingerprint(account_key: str, key: tuple[str, str, str, str], sequence: int) -> str:
    text = "|".join((account_key, *key, str(sequence)))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def account_key(bank: BankAccount) -> str:
    return str(bank.public_id)


def fingerprint_lines(account: str, lines: Sequence[RawLine]) -> list[str | None]:
    """One fingerprint per line (``None`` for a line with problems), in the lines' order."""
    seen: Counter[tuple[str, str, str, str]] = Counter()
    prints: list[str | None] = []
    for line in lines:
        if not line.ok:
            prints.append(None)
            continue
        key = line_key(line)
        seen[key] += 1
        prints.append(fingerprint(account, key, seen[key]))
    return prints


def existing_fingerprints(bank: BankAccount, fingerprints: Iterable[str | None]) -> set[str]:
    """The fingerprints among ``fingerprints`` that the bank account already has."""
    wanted = sorted({f for f in fingerprints if f})
    found: set[str] = set()
    for start in range(0, len(wanted), CHUNK):
        found.update(
            StatementLine.objects.filter(
                bank_account=bank, fingerprint__in=wanted[start : start + CHUNK]
            ).values_list("fingerprint", flat=True)
        )
    return found
