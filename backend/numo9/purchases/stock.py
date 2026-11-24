"""Stock movements from goods receipts (E-01-T05): the interface inventory (H-04, Phase 2) plugs
into.

A receipt of a **tracked** item emits ``+quantity`` (its reversal ``−quantity``) as a
``Movement``: the item, the quantity, the date, the PO line and the receipt it came from (the
source, so H-04 can match a reversal to its receipt). Untracked items — every Phase 1 item
(``items_item_untracked_until_h01``) — record the quantity received on the PO and move no stock.

- ``StockMovementSink`` — what an inventory implements: ``record(movements)``, called in the
  receipt's transaction (an error rolls the receipt back).
- ``NullSink`` — the Phase 1 default: nothing to record yet.
- ``RecordingSink`` — the test double: keeps every movement (``movements``) and the running
  quantity per item (``on_hand``); H-04 keeps the same contract test.
- ``sink()`` / ``use_sink(s)`` — the active sink; ``use_sink`` swaps it for a block (tests, or
  H-04 at start-up through ``set_sink``).
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class Movement:
    item_id: int
    quantity: Decimal
    date: dt.date
    po_line_id: int
    receipt_id: int
    organisation_id: int
    reason: str = "receipt"  # receipt | reversal

    @classmethod
    def of(cls, receipt: Any, line: Any, quantity: Decimal, reason: str = "receipt") -> Movement:
        return cls(
            item_id=line.item_id,
            quantity=Decimal(quantity),
            date=receipt.date,
            po_line_id=line.pk,
            receipt_id=receipt.pk,
            organisation_id=receipt.organisation_id,
            reason=reason,
        )


class StockMovementSink(Protocol):
    def record(self, movements: Sequence[Movement]) -> None: ...


class NullSink:
    """Phase 1: no inventory yet."""

    def record(self, movements: Sequence[Movement]) -> None:
        return None


@dataclass
class RecordingSink:
    """The test double: every movement, and the quantity per item."""

    movements: list[Movement] = field(default_factory=list)

    def record(self, movements: Sequence[Movement]) -> None:
        self.movements.extend(movements)

    @property
    def on_hand(self) -> dict[int, Decimal]:
        totals: dict[int, Decimal] = defaultdict(Decimal)
        for movement in self.movements:
            totals[movement.item_id] += movement.quantity
        return dict(totals)


_active: list[StockMovementSink] = [NullSink()]


def sink() -> StockMovementSink:
    return _active[-1]


def set_sink(new: StockMovementSink) -> None:
    _active[0] = new


@contextmanager
def use_sink[S: StockMovementSink](new: S) -> Iterator[S]:
    _active.append(new)
    try:
        yield new
    finally:
        _active.pop()


def tracked(line: Any) -> bool:
    item = line.item if line.item_id is not None else None
    return bool(item is not None and item.is_tracked)
