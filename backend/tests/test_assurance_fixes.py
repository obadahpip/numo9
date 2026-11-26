"""K-09-T16 — fix-to-draft: a finding's proposed entry becomes a draft journal (C-04) linked to
the finding; posting the draft resolves the finding.

Acceptance: on the teardown fixture the NEG_CASH fix is a **draft** Dr 1000 Petty Cash 994.17 /
Cr 2900 Shareholder Loan 994.17 (never posted by the engine); posting it resolves NEG_CASH; the
fix journal itself is not flagged by the journal rules; the drawer's edited lines are used;
a finding without a journal fix, or not active, is refused.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.assurance.fixes import FixRefused, create_fix_draft
from numo9.assurance.models import ExceptionFinding
from numo9.assurance.runner import run
from numo9.audit.models import AuditEvent
from numo9.ledger.services import post_entry
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, at, refined
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


def _books() -> dict[str, Any]:
    books = refined()
    with at(NOW):
        run(books["org"], now=NOW)
    with org_context(books["org"]):
        books["people"] = people(books["org"])
        books["finding"] = ExceptionFinding.objects.get(rule_code="NEG_CASH")
    return books


def test_posting_the_draft_fix_resolves_neg_cash() -> None:
    books = _books()
    org, finding = books["org"], books["finding"]
    adviser = books["people"]["adviser"]
    with at(NOW):
        draft = create_fix_draft(finding, adviser)
    assert draft.status == "draft" and draft.number is None  # never posted by the engine
    with org_context(org):
        lines = [
            (line.account.code, line.debit, line.credit)
            for line in draft.lines.order_by("line_no").select_related("account")
        ]
        finding.refresh_from_db()
        assert finding.fix_entry_id == draft.pk and finding.status == "open"
        assert AuditEvent.objects.filter(action="assurance.finding.fix_drafted").count() == 1
    assert lines == [
        ("1000", Decimal("994.17"), Decimal("0.00")),
        ("2900", Decimal("0.00"), Decimal("994.17")),
    ]
    assert draft.journal_type == "adjusting" and str(draft.date) == "2026-06-03"
    with at(NOW):
        post_entry(draft, user=adviser)
    with org_context(org):
        finding.refresh_from_db()
        event = AuditEvent.objects.filter(action="assurance.finding.resolved").get()
    assert finding.status == "resolved"
    assert event.meta["fixed_by"]
    # the fix is a manual journal to cash dated back: not a finding of its own
    with at(NOW):
        run(org, now=NOW)
    with org_context(org):
        flagged = set(
            ExceptionFinding.objects.filter(
                rule_code__in=("JOURNAL_TO_CASH", "BACKDATED"), status="open"
            ).values_list("subject_id", flat=True)
        )
    assert str(draft.public_id) not in flagged
    assert str(books["journal1"].public_id) in flagged


def test_edited_lines_are_used_and_asking_again_replaces_the_draft() -> None:
    books = _books()
    finding = books["finding"]
    acc = books["accounts"]
    edited = [
        {"account": str(acc["1000"].public_id), "debit": "1000.00"},
        {"account": str(acc["2900"].public_id), "credit": "1000.00", "description": "Float"},
    ]
    first = create_fix_draft(finding, books["people"]["adviser"], lines=edited, narration="Float")
    again = create_fix_draft(finding, books["people"]["adviser"])
    assert again.pk == first.pk
    with org_context(books["org"]):
        assert [line.debit for line in again.lines.order_by("line_no")] == [
            Decimal("994.17"),
            Decimal("0.00"),
        ]
    bad = [{"account": "00000000-0000-0000-0000-000000000000", "debit": "1"}]
    with pytest.raises(FixRefused) as error:
        create_fix_draft(finding, None, lines=bad)
    assert error.value.code == "assurance.fix.invalid"


def test_no_journal_fix_or_inactive_finding_is_refused() -> None:
    books = _books()
    with org_context(books["org"]):
        exempt = ExceptionFinding.objects.filter(rule_code="EXEMPT_ON_TAXABLE_ACCOUNT").first()
        backdated = ExceptionFinding.objects.get(rule_code="BACKDATED")
    assert exempt is not None
    with pytest.raises(FixRefused) as error:
        create_fix_draft(exempt, None)  # its fix is a recode, not a journal
    assert error.value.code == "assurance.fix.none"
    with pytest.raises(FixRefused):
        create_fix_draft(backdated, None)
    finding = books["finding"]
    with org_context(books["org"]):
        finding.status = "resolved"
        finding.save()
    with pytest.raises(FixRefused) as error:
        create_fix_draft(finding, None)
    assert error.value.code == "assurance.fix.not_active"
