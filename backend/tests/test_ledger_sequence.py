"""C-02-T05 — JournalSequence gap-free allocator.

Acceptance: sequential numbers in-transaction. Also: the first posting creates the sequence and
takes 1; a rolled-back allocation gives its number back (no gap); organisations number
independently; allocation outside a transaction is refused; formatting; and, on real
connections, concurrent allocators in several threads (some rolling back) end with numbers
1…N without gaps or duplicates — the full 1,000-posting test is C-02-T12.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from django.db import IntegrityError, connection, transaction

from numo9.ledger.models import JournalSequence
from numo9.ledger.sequence import (
    SequenceOutsideTransaction,
    allocate_journal_number,
    format_journal_number,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation


@pytest.fixture
def org(db: None) -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_numbers_are_sequential_in_the_transaction(org: Organisation) -> None:
    with transaction.atomic():
        numbers = [allocate_journal_number(org) for _ in range(5)]
    assert numbers == [1, 2, 3, 4, 5]
    assert JournalSequence.objects.get().next_number == 6


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_a_rolled_back_number_is_given_back(org: Organisation) -> None:
    with transaction.atomic():
        assert allocate_journal_number(org) == 1
    with pytest.raises(RuntimeError), transaction.atomic():
        assert allocate_journal_number(org) == 2
        raise RuntimeError("posting failed")
    with transaction.atomic():
        assert allocate_journal_number(org) == 2


@pytest.mark.django_db
def test_organisations_number_independently(org: Organisation) -> None:
    other = Organisation.objects.create(name="Birch Garage")
    with transaction.atomic():
        with org_context(org):
            assert [allocate_journal_number(org) for _ in range(3)] == [1, 2, 3]
        with org_context(other):
            assert allocate_journal_number(other) == 1
        with org_context(org):
            assert allocate_journal_number(org) == 4


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_one_sequence_row_per_organisation(org: Organisation) -> None:
    JournalSequence(organisation=org).save()
    with pytest.raises(IntegrityError), transaction.atomic():
        JournalSequence(organisation=org).save()
    with transaction.atomic():
        assert allocate_journal_number(org) == 1  # uses the existing row


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_format(org: Organisation) -> None:
    assert format_journal_number(org, None) == ""
    assert format_journal_number(org, 42) == "JE-000042"  # defaults before the first posting
    JournalSequence(organisation=org, prefix="GJ", padding=4).save()
    assert format_journal_number(org, 42) == "GJ0042"
    assert format_journal_number(org, 123456) == "GJ123456"


@pytest.mark.django_db(transaction=True)
def test_allocation_outside_a_transaction_is_refused(org: Organisation) -> None:
    with org_context(org), pytest.raises(SequenceOutsideTransaction):
        allocate_journal_number(org)


# ---- concurrency on real connections ---------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_allocations_are_gap_free(org: Organisation) -> None:
    workers, per_worker = 6, 15
    committed: list[int] = []
    lock = threading.Lock()
    errors: list[BaseException] = []
    start = threading.Barrier(workers)

    def work(worker: int) -> None:
        try:
            start.wait()
            with org_context(org):
                for i in range(per_worker):
                    try:
                        with transaction.atomic():
                            number = allocate_journal_number(org)
                            if (worker + i) % 4 == 0:
                                raise LookupError("roll this posting back")
                        with lock:
                            committed.append(number)
                    except LookupError:
                        pass
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=work, args=(n,)) for n in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not errors, errors
    assert sorted(committed) == list(range(1, len(committed) + 1))
    assert len(committed) == sum(
        1 for worker in range(workers) for i in range(per_worker) if (worker + i) % 4
    )
