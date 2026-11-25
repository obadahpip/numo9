"""G-03-T06 — return workflow: prepare → review (reviewer ≠ preparer) → file with the
confirmation number; send back; audit entries. Acceptance: self-review is refused."""

from __future__ import annotations

import pytest

from numo9.audit.models import AuditEvent
from numo9.rbac.duties import SelfApprovalRefused
from numo9.tax import returns
from numo9.tax.models import ReturnStatus, TaxError, TaxReturn
from numo9.tenancy.context import org_context
from tests.return_helpers import quarterly_books

pytestmark = pytest.mark.django_db


def test_prepare_review_file_with_audit() -> None:
    reg, periods, who = quarterly_books()
    draft = returns.prepare(periods[0], who["owner"])
    assert (draft.version, draft.status, draft.prepared_by) == (1, ReturnStatus.DRAFT, who["owner"])
    assert returns.prepare(periods[0], who["adviser"]).pk == draft.pk  # the one in progress
    with pytest.raises(SelfApprovalRefused) as refused:
        returns.review(draft, who["owner"])  # the preparer can't review their own return
    assert refused.value.get_codes() == "approval.self_approval"
    with pytest.raises(TaxError) as early:
        returns.file(draft, who["adviser"], confirmation_no="GH-2026-0001")
    assert early.value.code == "tax.return.status"  # not reviewed yet
    reviewed = returns.review(draft, who["adviser"])
    assert (reviewed.status, reviewed.reviewed_by) == (ReturnStatus.REVIEWED, who["adviser"])
    with pytest.raises(TaxError) as blank:
        returns.file(reviewed, who["owner"], confirmation_no="  ")
    assert blank.value.code == "tax.return.confirmation_required"
    filed = returns.file(reviewed, who["owner"], confirmation_no=" GH-2026-0001 ")
    assert (filed.status, filed.confirmation_no, filed.filed_by) == (
        ReturnStatus.FILED, "GH-2026-0001", who["owner"],
    )  # fmt: skip
    assert filed.filed_on is not None and filed.filed_at is not None
    with pytest.raises(TaxError) as again:
        returns.prepare(periods[0], who["owner"])
    assert again.value.code == "tax.return.already_filed"
    with org_context(reg.organisation):
        events = AuditEvent.objects.filter(action__startswith="tax.return.").order_by("pk")
        assert [e.action.rsplit(".", 1)[1] for e in events] == ["prepared", "reviewed", "filed"]
        assert [e.actor_user for e in events] == [who["owner"], who["adviser"], who["owner"]]
        assert events[2].meta["confirmation_no"] == "GH-2026-0001"
        assert all(e.object_type == "tax.TaxReturn" for e in events)


def test_send_back_needs_a_reason_and_reopens_review() -> None:
    _reg, periods, who = quarterly_books("Back Ltd.")
    draft = returns.prepare(periods[1], who["owner"])
    with pytest.raises(TaxError):
        returns.send_back(draft, who["adviser"], "wrong")  # a draft isn't under review
    reviewed = returns.review(draft, who["adviser"])
    with pytest.raises(TaxError) as blank:
        returns.send_back(reviewed, who["adviser"], " ")
    assert blank.value.code == "tax.return.reason_required"
    back = returns.send_back(reviewed, who["adviser"], "Line 106 misses the March bill")
    assert (back.status, back.reviewed_by, back.reviewed_at) == (ReturnStatus.DRAFT, None, None)
    with pytest.raises(TaxError):
        returns.review(returns.review(back, who["adviser"]), who["adviser"])  # already reviewed
    with org_context(back.organisation):
        assert TaxReturn.objects.get(pk=back.pk).status == ReturnStatus.REVIEWED
        event = AuditEvent.objects.get(action="tax.return.sent_back")
    assert event.meta["reason"] == "Line 106 misses the March bill"


def test_a_return_prepared_by_a_system_job_can_be_reviewed_by_anyone() -> None:
    _reg, periods, who = quarterly_books("Job Ltd.")
    draft = returns.prepare(periods[0])  # no person: a scheduled job
    assert draft.prepared_by is None
    assert returns.review(draft, who["owner"]).status == ReturnStatus.REVIEWED
