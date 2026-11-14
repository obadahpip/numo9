"""Does an account have posted transactions? (hook filled by the posting engine, C-02).

The chart rules need the answer before C-02 exists: an account with transactions can't become a
parent (it would stop being postable) and can't be deleted (archive it instead). Modules that own
journal lines register a probe; until C-02 registers its own there are no transactions, so the
answer is "no".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Account

Probe = Callable[["Account"], bool]

_probes: list[Probe] = []


def register_posting_probe(probe: Probe) -> Probe:
    """Register ``probe(account) -> bool`` (usable as a decorator); idempotent."""
    if probe not in _probes:
        _probes.append(probe)
    return probe


def unregister_posting_probe(probe: Probe) -> None:
    if probe in _probes:
        _probes.remove(probe)


def has_postings(account: Account) -> bool:
    if account.pk is None:
        return False
    return any(probe(account) for probe in _probes)
