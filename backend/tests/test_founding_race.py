"""U-08-T04 — Concurrency: 1,500 parallel first payments → exactly 1,000 founding slots.

30 threads, each on its own PostgreSQL connection, released together, allocate a slot for 1,500
organisations (every 10th is allocated twice: a replayed webhook). Acceptance: exactly 1,000
slots, numbered 1..1000 with no gap or duplicate, counter = 1,000, nobody holds two slots, the
other 500 refused.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from numo9.founding.models import FoundingCounter, FoundingSlot
from numo9.founding.race import founding_race
from numo9.tenancy.models import Organisation


@pytest.mark.django_db(transaction=True)
def test_1500_parallel_allocations_give_exactly_1000_slots() -> None:
    FoundingCounter.objects.update_or_create(pk=1, defaults={"cap": 1000, "allocated": 0})
    organisations = Organisation.objects.bulk_create(
        Organisation(name=f"Race {n:04d}") for n in range(1500)
    )
    report = founding_race(organisations, workers=30, replay_every=10)
    assert report.errors == []
    assert report.ok(1000), report
    assert report.numbers == list(range(1, 1001))
    assert report.attempts == 1650  # 150 replays
    assert report.refused >= 500
    assert FoundingCounter.current().remaining == 0


@pytest.mark.django_db(transaction=True)
def test_counter_at_999_with_simultaneous_payments() -> None:
    FoundingCounter.objects.update_or_create(pk=1, defaults={"cap": 1, "allocated": 0})
    organisations = Organisation.objects.bulk_create(
        Organisation(name=f"Last {n}") for n in range(20)
    )
    report = founding_race(organisations, workers=20)
    assert report.ok(1), report
    assert FoundingSlot.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_command_refuses_a_database_with_slots() -> None:
    from django.core.management.base import CommandError

    FoundingCounter.objects.update_or_create(pk=1, defaults={"allocated": 1})
    with pytest.raises(CommandError):
        call_command("founding_race_test", orgs=5, workers=2)


@pytest.mark.django_db(transaction=True)
def test_command_runs_on_a_scratch_database() -> None:
    FoundingCounter.objects.update_or_create(pk=1, defaults={"cap": 10, "allocated": 0})
    call_command("founding_race_test", orgs=25, workers=5, replay_every=4)
    assert FoundingSlot.objects.count() == 10
