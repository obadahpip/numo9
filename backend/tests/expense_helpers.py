"""Expense claim test helpers (E-04): an Ontario organisation with its chart and tax table, a
claim by the owner, lines."""

from __future__ import annotations

import datetime as dt
from typing import Any

from numo9.ledger.template import load_template
from numo9.purchases.models import ExpenseClaim, ExpenseClaimLine, ExpenseLineKind
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

DAY = dt.date(2026, 6, 15)


def expense_org(name: str = "Refined Interiors Inc.") -> tuple[Organisation, dict[str, Any]]:
    organisation = Organisation.objects.create(name=name)
    load_template(organisation, "ON")
    return organisation, people(organisation)


def make_claim(org: Organisation, claimant: Any, **fields: Any) -> ExpenseClaim:
    fields.setdefault("title", "Client visits")
    with org_context(org):
        item = ExpenseClaim(organisation=org, claimant=claimant, **fields)
        item.save()
    return item


def add_line(claim: ExpenseClaim, **fields: Any) -> ExpenseClaimLine:
    fields.setdefault("date", DAY)
    with org_context(claim.organisation):
        item = ExpenseClaimLine(organisation=claim.organisation, claim=claim, **fields)
        item.save()
    return item


def add_trip(claim: ExpenseClaim, km: str, day: dt.date = DAY, **fields: Any) -> ExpenseClaimLine:
    from decimal import Decimal

    return add_line(
        claim,
        kind=ExpenseLineKind.MILEAGE,
        from_place=fields.pop("from_place", "Office"),
        to_place=fields.pop("to_place", "Client"),
        distance_km=Decimal(km),
        date=day,
        **fields,
    )
