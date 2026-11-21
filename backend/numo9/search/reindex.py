"""Rebuild and check an organisation's search index (A-09-T09) — the answer to index drift.

``reindex(organisation)`` builds every registered provider's documents for the organisation
from the records themselves, writes them and removes documents whose record is gone or no
longer searchable; afterwards the index holds exactly one document per searchable record.
``drift(organisation)`` compares without writing (the nightly consistency check): documents
missing, stale (no record behind them) and per-type counts.

Records are read inside the organisation's context (row-level security and tenant managers
apply), with each model's default manager — soft-deleted records are not searchable.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import SearchDocument
from .registry import Provider, build_document, identity, index, providers

Identity = tuple[str, str]  # (object_type, object_id)


@dataclass
class Report:
    organisation: str
    indexed: int = 0
    removed: int = 0
    missing: int = 0
    stale: int = 0
    counts: Counter[str] = field(default_factory=Counter)

    @property
    def consistent(self) -> bool:
        return not self.missing and not self.stale


def _records(provider: Provider, organisation: Organisation) -> Iterator[Any]:
    model = provider.model
    if model is Organisation:
        yield organisation
        return
    manager = model._default_manager
    if not any(f.name == "organisation" for f in model._meta.get_fields()):
        return
    yield from manager.filter(organisation=organisation).iterator(chunk_size=500)


def expected(organisation: Organisation) -> dict[Identity, Any]:
    """Every searchable record of the organisation, by the identity of its document."""
    found: dict[Identity, Any] = {}
    with org_context(organisation):
        for provider in providers():
            for record in _records(provider, organisation):
                doc = build_document(provider, record)
                if doc is None:
                    continue
                org_id, object_type, object_id = identity(provider, record, doc)
                if org_id == organisation.pk:
                    found[(object_type, object_id)] = record
    return found


def _existing(organisation: Organisation) -> set[Identity]:
    with org_context(organisation):
        return set(SearchDocument.objects.values_list("object_type", "object_id"))


def drift(organisation: Organisation) -> Report:
    want = expected(organisation)
    have = _existing(organisation)
    report = Report(str(organisation.public_id))
    report.missing = len(set(want) - have)
    report.stale = len(have - set(want))
    report.counts = Counter(object_type for object_type, _ in want)
    return report


def reindex(organisation: Organisation) -> Report:
    report = Report(str(organisation.public_id))
    with transaction.atomic():
        want = expected(organisation)
        have = _existing(organisation)
        stale = have - set(want)
        with org_context(organisation):
            for object_type, object_id in stale:
                SearchDocument.objects.filter(object_type=object_type, object_id=object_id).delete()
            for record in want.values():
                index(record)
        report.indexed = len(want)
        report.removed = len(stale)
        report.counts = Counter(object_type for object_type, _ in want)
    return report
