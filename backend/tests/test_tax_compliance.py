"""G-01-T15 — compliance fixtures: tests/fixtures/compliance/sales_tax_2026.yaml.

Every case (13 jurisdictions × sales / purchase standard codes, the 50 % ITC purchase codes,
zero-rated / exempt / out-of-scope × tax exclusive and inclusive × six amounts) is calculated with
the seeded table and the TaxCalculator on 15 Jun 2026; acceptance: 100 % pass, to the cent.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from numo9.ledger.template import load_template
from numo9.tax.calculator import calculate
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = [pytest.mark.django_db, pytest.mark.compliance]

FIXTURE = Path(__file__).parent / "fixtures" / "compliance" / "sales_tax_2026.yaml"
DOCUMENT: dict[str, Any] = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
JURISDICTIONS = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


def test_fixture_covers_every_jurisdiction_side_and_type() -> None:
    cases = DOCUMENT["cases"]
    for side in ("sales", "purchase"):
        assert {
            c["province"] for c in cases if c["side"] == side and c["province"]
        } == JURISDICTIONS
        assert {c["type"] for c in cases if c["side"] == side} == {
            "taxable",
            "zero_rated",
            "exempt",
            "out_of_scope",
        }
    assert any(c["code"].endswith(".itc50") for c in cases)
    assert {c["inclusive"] for c in cases} == {True, False}


def test_every_case_to_the_cent() -> None:
    org = Organisation.objects.create(name="Compliance Inc.")
    load_template(org, "ON")
    day = dt.date.fromisoformat(DOCUMENT["date"])
    failures = []
    with org_context(org):
        versions: dict[tuple[str, str], Any] = {}
        for case in DOCUMENT["cases"]:
            key = (case["code"], case["side"])
            if key not in versions:
                version = code_for(case["code"], case["side"], day)
                versions[key] = (
                    version,
                    list(version.components.select_related("component", "tax_code")),
                )
            version, links = versions[key]
            out = calculate(
                version, Decimal(case["amount"]), inclusive=case["inclusive"], links=links
            )
            got = {
                "net": f"{out.net:.2f}",
                "taxes": [f"{c.amount:.2f}" for c in out.components],
                "gross": f"{out.gross:.2f}",
                "claimable": f"{out.claimable:.2f}",
                "cost": f"{out.cost:.2f}",
            }
            want = {k: case[k] for k in got}
            if got != want:
                failures.append((case["code"], case["amount"], case["inclusive"], want, got))
    assert not failures, failures[:5]
    assert len(DOCUMENT["cases"]) > 400
