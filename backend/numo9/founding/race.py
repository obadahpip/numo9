"""Founding race (U-08-T04): many first payments allocating founding slots at once.

``founding_race(organisations, workers=30)`` calls ``allocate_founding_slot`` for every
organisation from ``workers`` threads, each on its own database connection, released together by
a barrier; each allocation runs in its own transaction (as the first-payment handler does). Every
``replay_every``-th organisation is allocated twice in a row (a replayed webhook).

The report (``RaceReport``) checks what U-08 promises: exactly ``min(cap, organisations)`` slots,
numbered ``1..allocated`` with no gap or duplicate, the counter equal to the slot count, and no
organisation holding two slots.

Used by ``tests/test_founding_race.py`` (CI) and ``manage.py founding_race_test`` against a
scratch database (it allocates real slots: never run it on production data).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from django.db import connection, transaction
from django.db.models import Count

from numo9.tenancy.models import Organisation

from .models import FoundingCounter, FoundingSlot
from .services import allocate_founding_slot


@dataclass
class RaceReport:
    attempts: int = 0
    granted: int = 0
    refused: int = 0
    errors: list[str] = field(default_factory=list)
    numbers: list[int] = field(default_factory=list)
    counter_allocated: int = 0
    cap: int = 0
    double_holders: int = 0
    seconds: float = 0.0

    @property
    def gap_free(self) -> bool:
        return self.numbers == list(range(1, len(self.numbers) + 1))

    def ok(self, expected: int) -> bool:
        return (
            not self.errors
            and self.gap_free
            and len(self.numbers) == expected
            and self.counter_allocated == expected
            and self.double_holders == 0
        )


def founding_race(
    organisations: Sequence[Organisation], *, workers: int = 30, replay_every: int = 0
) -> RaceReport:
    report = RaceReport()
    lock = threading.Lock()
    queue = list(organisations)
    barrier = threading.Barrier(workers)

    def one(organisation: Organisation, times: int) -> None:
        for _ in range(times):
            with transaction.atomic():
                slot = allocate_founding_slot(organisation, payment_ref=f"race-{organisation.pk}")
            with lock:
                report.attempts += 1
                if slot is None:
                    report.refused += 1
                else:
                    report.granted += 1

    def worker() -> None:
        try:
            barrier.wait()
            while True:
                with lock:
                    if not queue:
                        return
                    index = len(queue)
                    organisation = queue.pop()
                times = 2 if replay_every and index % replay_every == 0 else 1
                one(organisation, times)
        except Exception as error:  # pragma: no cover - reported, not raised
            with lock:
                report.errors.append(repr(error))
        finally:
            connection.close()

    started = time.monotonic()
    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    report.seconds = time.monotonic() - started

    counter = FoundingCounter.current()
    report.counter_allocated, report.cap = counter.allocated, counter.cap
    report.numbers = list(
        FoundingSlot.objects.order_by("slot_no").values_list("slot_no", flat=True)
    )
    report.double_holders = (
        FoundingSlot.objects.values("organisation").annotate(n=Count("id")).filter(n__gt=1).count()
    )
    return report
