"""Bulk operations as one audit batch (A-04-T06).

Acceptance: a 500-row operation is one batch — 500 row events and one summary event, all with the
same batch id, the summary counting the events by action and record type.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import transaction

from numo9.audit.batch import SUMMARY_ACTION, SUMMARY_TYPE, audit_batch, current_batch
from numo9.audit.models import AuditEvent
from numo9.audit.service import record
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.testapp.models import AuditedInvoice

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def test_500_row_operation_is_one_batch(org: Organisation) -> None:
    with org_context(org):
        AuditedInvoice.objects.bulk_create(
            [
                AuditedInvoice(organisation=org, number=f"INV-{n}", amount=Decimal("10.00"))
                for n in range(500)
            ]
        )
        with transaction.atomic(), audit_batch("Reprice invoices", meta={"to": "12.00"}) as batch:
            for invoice in AuditedInvoice.objects.all():
                invoice.amount = Decimal("12.00")
                invoice.save()
        in_batch = list(AuditEvent.objects.filter(batch_id=batch.id))
    rows = [e for e in in_batch if e.action != SUMMARY_ACTION]
    (summary,) = [e for e in in_batch if e.action == SUMMARY_ACTION]
    assert len(rows) == 500 and len(in_batch) == 501
    assert {e.action for e in rows} == {"testapp.auditedinvoice.updated"}
    assert summary.object_type == SUMMARY_TYPE and summary.object_id == str(batch.id)
    assert summary.object_label == "Reprice invoices"
    assert summary.meta == {
        "to": "12.00",
        "events": 500,
        "actions": {"testapp.auditedinvoice.updated": 500},
        "types": ["testapp.AuditedInvoice"],
        "status": "completed",
    }
    assert summary.organisation == org
    # The summary is the last event of the batch.
    assert summary.id == max(e.id for e in in_batch)


def test_events_outside_the_block_have_no_batch(org: Organisation) -> None:
    with audit_batch("Bulk edit", organisation=org):
        record("tests.inside", organisation=org)
    outside = record("tests.outside", organisation=org)
    assert outside.batch_id is None
    assert current_batch() is None


def test_nested_blocks_join_the_outer_batch(org: Organisation) -> None:
    with audit_batch("Import contacts", organisation=org) as outer:
        record("tests.a", organisation=org)
        with audit_batch("Inner step", organisation=org) as inner:
            record("tests.b", organisation=org)
        assert inner is outer
    summaries = AuditEvent.platform_events.filter(action=SUMMARY_ACTION)
    assert summaries.count() == 1 and summaries.get().meta["events"] == 2


def test_failed_block_in_a_transaction_leaves_nothing(org: Organisation) -> None:
    with (
        pytest.raises(RuntimeError),
        transaction.atomic(),
        audit_batch("Bulk edit", organisation=org),
    ):
        record("tests.a", organisation=org)
        raise RuntimeError("row 2 failed")
    assert AuditEvent.platform_events.count() == 0


def test_failed_block_whose_rows_committed_says_so(org: Organisation) -> None:
    with pytest.raises(RuntimeError), audit_batch("Step-by-step job", organisation=org):
        record("tests.a", organisation=org)  # committed on its own (autocommit)
        raise RuntimeError("row 2 failed")
    summary = AuditEvent.platform_events.get(action=SUMMARY_ACTION)
    assert summary.meta["status"] == "failed" and summary.meta["events"] == 1


def test_empty_batch_still_records_that_it_ran(org: Organisation) -> None:
    with audit_batch("Bulk edit (nothing matched)", organisation=org):
        pass
    summary = AuditEvent.platform_events.get(action=SUMMARY_ACTION)
    assert summary.meta["events"] == 0 and summary.meta["status"] == "completed"


def test_batch_needs_a_label() -> None:
    with pytest.raises(ValueError), audit_batch("  "):
        pass
