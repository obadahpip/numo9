"""A-05-T08 — numbering sequences per document type with row-lock allocation.

Acceptance: concurrent allocation gives unique numbers (threads on PostgreSQL, each with its own
connection and transaction). Also: default patterns ``INV-0001``, ``CN-0001``, ``QU-0001``,
``PO-0001``; padding and prefix; numbers past the padding grow; a rolled-back document gives its
number back (no gap); one sequence per document type (database); prefix and padding validated;
people's changes audited, allocations not; organisations have their own sequences.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections, transaction

from numo9.audit.models import AuditEvent
from numo9.orgsettings.models import DocType, NumberingSequence
from numo9.orgsettings.numbering import allocate_number, get_sequence
from numo9.tenancy.context import TenantContextMissing, org_context
from numo9.tenancy.models import Organisation


@pytest.fixture
def org(db: None) -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture
def active(org: Organisation) -> Iterator[Organisation]:
    with org_context(org):
        yield org


# ---- patterns -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("doc_type", "first"),
    [
        (DocType.INVOICE, "INV-0001"),
        (DocType.CREDIT_NOTE, "CN-0001"),
        (DocType.QUOTE, "QU-0001"),
        (DocType.PURCHASE_ORDER, "PO-0001"),
    ],
)
def test_default_patterns(active: Organisation, doc_type: str, first: str) -> None:
    assert allocate_number(doc_type) == first
    assert get_sequence(doc_type).preview == first.replace("0001", "0002")


def test_numbers_follow_one_another(active: Organisation) -> None:
    assert [allocate_number(DocType.INVOICE) for _ in range(3)] == [
        "INV-0001",
        "INV-0002",
        "INV-0003",
    ]
    assert allocate_number(DocType.QUOTE) == "QU-0001"  # each type its own sequence


def test_custom_pattern_and_numbers_past_the_padding(active: Organisation) -> None:
    sequence = get_sequence(DocType.INVOICE)
    sequence.prefix, sequence.padding, sequence.next_number = "", 1, 101
    sequence.save()
    assert allocate_number(DocType.INVOICE) == "101"
    sequence.refresh_from_db()
    sequence.prefix, sequence.padding, sequence.next_number = "2026/", 3, 999
    sequence.save()
    assert [allocate_number(DocType.INVOICE) for _ in range(2)] == ["2026/999", "2026/1000"]


def test_rolled_back_document_gives_its_number_back(active: Organisation) -> None:
    assert allocate_number(DocType.INVOICE) == "INV-0001"
    with pytest.raises(RuntimeError), transaction.atomic():
        assert allocate_number(DocType.INVOICE) == "INV-0002"
        raise RuntimeError("the invoice failed to save")
    assert allocate_number(DocType.INVOICE) == "INV-0002"


def test_unknown_document_type_is_refused(active: Organisation) -> None:
    with pytest.raises(ValueError):
        allocate_number("journal")


def test_allocation_needs_an_organisation(org: Organisation) -> None:
    with pytest.raises(TenantContextMissing):
        allocate_number(DocType.INVOICE)
    assert allocate_number(DocType.INVOICE, organisation=org) == "INV-0001"


def test_organisations_have_their_own_sequences(active: Organisation) -> None:
    allocate_number(DocType.INVOICE)
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        assert allocate_number(DocType.INVOICE) == "INV-0001"
        assert NumberingSequence.objects.count() == 1


# ---- rules --------------------------------------------------------------------------------------


def test_one_sequence_per_document_type(active: Organisation) -> None:
    get_sequence(DocType.INVOICE)
    with pytest.raises(IntegrityError), transaction.atomic():
        NumberingSequence.objects.bulk_create(
            [NumberingSequence(organisation=active, doc_type=DocType.INVOICE)]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prefix", "INV 01"),
        ("prefix", "ÉTÉ€"),
        ("prefix", "TOO-LONG-PREFIX"),
        ("padding", 0),
        ("padding", 11),
        ("next_number", 0),
    ],
)
def test_invalid_settings_are_refused(active: Organisation, field: str, value: object) -> None:
    sequence = get_sequence(DocType.INVOICE)
    setattr(sequence, field, value)
    with pytest.raises(ValidationError) as excinfo:
        sequence.save()
    assert field in excinfo.value.error_dict


def test_database_refuses_out_of_range_values(active: Organisation) -> None:
    sequence = get_sequence(DocType.INVOICE)
    for update in ({"next_number": 0}, {"padding": 0}, {"padding": 11}, {"doc_type": "bill"}):
        with pytest.raises(IntegrityError), transaction.atomic():
            NumberingSequence.objects.filter(pk=sequence.pk).update(**update)


def test_changes_are_audited_allocations_are_not(active: Organisation) -> None:
    sequence = get_sequence(DocType.INVOICE)
    for _ in range(5):
        allocate_number(DocType.INVOICE)
    sequence.refresh_from_db()
    sequence.next_number = 500
    sequence.save()
    actions = list(
        AuditEvent.objects.filter(object_type="orgsettings.NumberingSequence")
        .order_by("id")
        .values_list("action", "changes")
    )
    assert actions == [
        (
            "orgsettings.numberingsequence.created",
            {
                "doc_type": [None, "invoice"],
                "prefix": [None, "INV-"],
                "next_number": [None, 1],
                "padding": [None, 4],
            },
        ),
        ("orgsettings.numberingsequence.updated", {"next_number": [6, 500]}),
    ]


# ---- acceptance: concurrent allocation is unique ------------------------------------------------

THREADS = 8
PER_THREAD = 25


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(connection.vendor != "postgresql", reason="row locks need PostgreSQL")
def test_concurrent_allocation_is_unique_and_gap_free() -> None:
    org = Organisation.objects.create(name="Busy Shop Ltd.")
    numbers: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    start = threading.Barrier(THREADS)

    def worker() -> None:
        try:
            start.wait()
            with org_context(org):
                for _ in range(PER_THREAD):
                    with transaction.atomic():  # one document per transaction
                        number = allocate_number(DocType.INVOICE)
                    with lock:
                        numbers.append(number)
        except BaseException as error:  # reported below
            errors.append(error)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    total = THREADS * PER_THREAD
    assert len(numbers) == len(set(numbers)) == total
    assert sorted(numbers) == [f"INV-{n:04d}" for n in range(1, total + 1)]
    with org_context(org):
        assert NumberingSequence.objects.get(doc_type=DocType.INVOICE).next_number == total + 1
