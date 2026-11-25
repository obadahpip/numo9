"""G-03b-T05 — documents after a stop: the invoices (and other documents) dated after the stop
date with GST/HST codes are listed for review; a new 15 Jul document with a GST code gets the
warning REGISTRATION_STOPPED; no warning before the stop, for out-of-scope codes, or after a
restart; a QST stop doesn't flag GST-only documents."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.orgsettings.models import TaxRegistration
from numo9.tax.filing_service import switch_frequency
from numo9.tax.post_stop import CODE, post_stop_documents, stop_warning
from numo9.tax.resolver import code_for
from numo9.tax.stop_restart import restart, stop
from numo9.tenancy.context import org_context
from tests.sales_helpers import draft, sales_books
from tests.stop_helpers import TODAY

pytestmark = pytest.mark.django_db
day = dt.date


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    org = books["org"]
    with org_context(org):
        reg = TaxRegistration(
            organisation=org, type="rt", number="123456782RT0001", effective_from=day(2026, 1, 1)
        )
        reg.save()
        switch_frequency(reg, "quarterly", day(2026, 1, 1), today=TODAY)
    books["reg"] = reg
    books["user"] = User.objects.create_user("dana@refined.ca", name="Dana Lee")
    return books


def test_documents_after_the_stop_are_listed(books: dict[str, Any]) -> None:
    before = draft(books, [("1", "100", "sales.ON.standard")], date=day(2026, 6, 20))
    after = draft(books, [("1", "100", "sales.ON.standard")], date=day(2026, 7, 15))
    draft(books, [("1", "100", "sales.out_of_scope")], date=day(2026, 7, 16))
    stop(books["reg"], day(2026, 6, 30), "deregistration", user=books["user"], today=TODAY)
    with org_context(books["org"]):
        rows = post_stop_documents(books["reg"])
    assert [r["id"] for r in rows] == [str(after.public_id)]
    assert rows[0]["kind"] == "invoice"
    assert rows[0]["url"].endswith(f"/sales/invoices/{after.public_id}")
    assert str(before.public_id) not in [r["id"] for r in rows]


def test_warning_on_a_15_july_gst_document(books: dict[str, Any]) -> None:
    org = books["org"]
    stop(books["reg"], day(2026, 6, 30), "deregistration", user=books["user"], today=TODAY)
    with org_context(org):
        hst = code_for("sales.ON.standard", "sales", day(2026, 7, 15), org)
        out = code_for("sales.out_of_scope", "sales", day(2026, 7, 15), org)
        warning = stop_warning(org, day(2026, 7, 15), [hst])
        assert warning is not None and warning["code"] == CODE == "REGISTRATION_STOPPED"
        assert "2026-06-30" in warning["message"]
        assert stop_warning(org, day(2026, 6, 30), [hst]) is None
        assert stop_warning(org, day(2026, 7, 15), [out]) is None
        assert stop_warning(org, day(2026, 7, 15), []) is None
    restart(books["reg"], day(2027, 1, 1), "quarterly", user=books["user"], today=TODAY)
    with org_context(org):
        assert stop_warning(org, day(2027, 1, 5), [hst]) is None
        assert stop_warning(org, day(2026, 12, 31), [hst]) is not None


def test_qst_stop_ignores_gst_only_documents(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        qst = TaxRegistration(
            organisation=org, type="qst", number="1234567890TQ0001", effective_from=day(2026, 1, 1)
        )
        qst.save()
        switch_frequency(qst, "quarterly", day(2026, 1, 1), today=TODAY)
    stop(qst, day(2026, 6, 30), "other", user=books["user"], today=TODAY)
    draft(books, [("1", "100", "sales.ON.standard")], date=day(2026, 7, 15))
    quebec = draft(books, [("1", "100", "sales.QC.standard")], province="QC", date=day(2026, 7, 20))
    with org_context(org):
        assert [r["id"] for r in post_stop_documents(qst)] == [str(quebec.public_id)]
        hst = code_for("sales.ON.standard", "sales", day(2026, 7, 15), org)
        assert stop_warning(org, day(2026, 7, 15), [hst]) is None
