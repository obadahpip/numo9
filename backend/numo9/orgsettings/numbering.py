"""Document numbers from the organisation's sequences (A-05-T08).

    number = allocate_number(DocType.INVOICE)   # "INV-0042", inside the approval transaction

``allocate_number()`` locks the sequence row (``SELECT … FOR UPDATE``), takes ``next_number`` and
moves it on by one, in the caller's transaction:

- **unique** — a second transaction allocating the same document type waits for the first to
  commit or roll back, then reads the moved-on number;
- **gap-free** — if the caller's transaction rolls back (the document fails to save), the increment
  rolls back with it and the number is handed out again;
- the sequence row is created on first use with the default pattern (``INV-0001``…); two first
  uses at the same moment are settled by the unique constraint.

Call it as late as possible — when the document is approved (D-03a) — so the lock is held briefly.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import F, QuerySet
from django.utils import timezone

from numo9.tenancy.context import TenantContextMissing, current_org
from numo9.tenancy.models import Organisation

from .models import DEFAULT_PADDING, DEFAULT_PREFIXES, DocType, NumberingSequence


def get_sequence(doc_type: str, organisation: Organisation | None = None) -> NumberingSequence:
    """The organisation's sequence for a document type, created with the default pattern."""
    org = _organisation(organisation)
    existing = _sequences(org, doc_type).first()
    if existing is not None:
        return existing
    return _create(org, doc_type)


def allocate_number(doc_type: str, organisation: Organisation | None = None) -> str:
    """The next number of a document type, unique and gap-free (see the module docstring)."""
    org = _organisation(organisation)
    if doc_type not in DocType.values:
        raise ValueError(f"Unknown document type {doc_type!r}.")
    with transaction.atomic():
        sequence = _sequences(org, doc_type).select_for_update().first()
        if sequence is None:
            _create(org, doc_type)
            sequence = _sequences(org, doc_type).select_for_update().get()
        number = sequence.next_number
        NumberingSequence._base_manager.filter(pk=sequence.pk).update(
            next_number=F("next_number") + 1, updated_at=timezone.now()
        )
        return sequence.format(number)


def _organisation(organisation: Organisation | None) -> Organisation:
    org = organisation or current_org()
    if org is None:
        raise TenantContextMissing("Document numbers need an active organisation.")
    return org


def _sequences(org: Organisation, doc_type: str) -> QuerySet[NumberingSequence]:
    return NumberingSequence._base_manager.filter(
        organisation=org, doc_type=doc_type, deleted_at__isnull=True
    )


def _create(org: Organisation, doc_type: str) -> NumberingSequence:
    sequence = NumberingSequence(
        organisation=org,
        doc_type=doc_type,
        prefix=DEFAULT_PREFIXES.get(doc_type, ""),
        padding=DEFAULT_PADDING,
    )
    try:
        with transaction.atomic():  # a savepoint: a lost race doesn't break the caller
            sequence.save()
    except IntegrityError:
        return _sequences(org, doc_type).get()
    return sequence
