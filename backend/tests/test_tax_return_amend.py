"""G-03-T09 — amendment: version n + 1 from a filed return with a reason; the original stays
viewable. Acceptance: two versions visible, the latest marked current."""

from __future__ import annotations

import pytest

from numo9.audit.models import AuditEvent
from numo9.tax import returns
from numo9.tax.models import FilingPeriod, PeriodStatus, ReturnStatus, TaxError, TaxReturn
from numo9.tenancy.context import org_context
from tests.return_helpers import quarterly_books

pytestmark = pytest.mark.django_db


def test_amend_a_filed_return() -> None:
    reg, periods, who = quarterly_books()
    q1 = periods[0]
    draft = returns.prepare(q1, who["owner"])
    with org_context(reg.organisation):
        draft.lines = {"101": "1000.00", "103": "130.00"}
        draft.save()
    with pytest.raises(TaxError) as early:
        returns.amend(draft, who["owner"], "typo")  # only a filed return is amended
    assert early.value.code == "tax.return.status"
    filed = returns.file(
        returns.review(draft, who["adviser"]), who["owner"], confirmation_no="GH-1"
    )
    with pytest.raises(TaxError) as blank:
        returns.amend(filed, who["owner"], "  ")
    assert blank.value.code == "tax.return.reason_required"
    second = returns.amend(filed, who["owner"], "March invoice 118 was missed")
    assert (second.version, second.status, second.amends) == (2, ReturnStatus.DRAFT, filed)
    assert second.lines == {"101": "1000.00", "103": "130.00"}  # starts from the filed values
    assert returns.prepare(q1, who["adviser"]).pk == second.pk  # the amendment is the open one
    with pytest.raises(TaxError) as twice:
        returns.amend(filed, who["owner"], "another reason")
    assert twice.value.code == "tax.return.amendment_open"
    # Until the amendment is filed, the filed return stands.
    assert [(v["version"], v["status"], v["current"]) for v in returns.versions(q1)] == [
        (2, "draft", True),
        (1, "filed", False),
    ]
    with pytest.raises(Exception, match="created this return"):
        returns.review(second, who["owner"])  # reviewer ≠ preparer applies to amendments too
    returns.file(returns.review(second, who["adviser"]), who["owner"], confirmation_no="GH-1-A")
    shown = returns.versions(q1)
    assert [(v["version"], v["status"], v["current"], v["confirmation_no"]) for v in shown] == [
        (2, "filed", True, "GH-1-A"),
        (1, "amended", False, "GH-1"),
    ]
    assert shown[0]["amend_reason"] == "March invoice 118 was missed"
    with org_context(reg.organisation):
        original = TaxReturn.objects.get(pk=filed.pk)  # still there, with its values
        assert original.lines["103"] == "130.00" and not original.is_current
        assert FilingPeriod.objects.get(pk=q1.pk).status == PeriodStatus.FILED
        event = AuditEvent.objects.get(action="tax.return.amended")
        assert event.meta == {"reason": "March invoice 118 was missed", "amends_version": 1}
        current = returns.current_return(q1)
        assert current is not None and current.version == 2
    third = returns.amend(returns.current_return_of(q1), who["owner"], "ITC on bill 77")
    assert third.version == 3
