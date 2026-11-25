"""G-03b-T12 (server side) — the editor's calculate answer carries ``REGISTRATION_STOPPED`` for a
15 Jul document with a GST/HST code after a stop on 30 Jun; none on 30 Jun or with an
out-of-scope code; a warning, the figures are still calculated."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client

from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.orgsettings.models import TaxRegistration
from numo9.tax.filing_service import switch_frequency
from numo9.tax.resolver import code_for
from numo9.tax.stop_restart import stop
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people
from tests.stop_helpers import TODAY

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    client = Client()
    owner = people(org)["owner"]
    client.force_login(owner)
    with org_context(org):
        reg = TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2026, 1, 1),
        )
        reg.save()
        switch_frequency(reg, "quarterly", dt.date(2026, 1, 1), today=TODAY)
        revenue = Account.objects.filter(subtype="revenue").order_by("code").first()
    stop(reg, dt.date(2026, 6, 30), "deregistration", user=owner, today=TODAY)
    return {"org": org, "client": client, "revenue": str(revenue.public_id)}  # type: ignore[union-attr]


def calculate(ctx: dict[str, Any], day: str, key: str) -> dict[str, Any]:
    org = ctx["org"]
    code = code_for(key, "sales", dt.date.fromisoformat(day), org)
    body = {
        "date": day,
        "lines": [
            {
                "account": ctx["revenue"],
                "quantity": "1",
                "unit_price": "100",
                "tax_code": str(code.public_id),
            }
        ],
    }
    response = ctx["client"].post(
        f"/api/v1/o/{org.public_id}/documents/sales/calculate",
        body,
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    result: dict[str, Any] = response.json()
    return result


def test_warning_on_a_15_july_invoice(ctx: dict[str, Any]) -> None:
    found = calculate(ctx, "2026-07-15", "sales.ON.standard")
    assert [w["code"] for w in found["warnings"]] == ["REGISTRATION_STOPPED"]
    assert found["total"] == "113.00"  # still calculated
    assert calculate(ctx, "2026-06-30", "sales.ON.standard")["warnings"] == []
    assert calculate(ctx, "2026-07-15", "sales.out_of_scope")["warnings"] == []
