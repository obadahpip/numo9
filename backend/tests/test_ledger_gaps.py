"""C-01-T14 — fixtures + gap tests gap-18 / 29 / 30 / 44 / 45 / 46 for the chart of accounts.

Each test loads the Canadian template (``fixtures/coa_ca_v1/expected.json`` holds the expected
chart per home province) and observes the row of the Phase 0 gap table (xero_teardown §5.4–§6.10):

- gap-18 — the Inventory account is typed Inventory (Xero: Current asset, which blocks
  inventory tracking);
- gap-29 — correct typing (intangibles are intangible, not fixed assets), separate GST/HST
  payable, ITC receivable, PST, QST, QST ITR and payroll control accounts, consistent 4-digit
  codes, system accounts renumberable, parent/child sub-accounts;
- gap-30 — 100 % GIFI-mapped with codes that fit each account's type;
- gap-44 — every change attributed (template load and renumbering name the person, never a bare
  "System");
- gap-45 — expense accounts default to the home-province purchase rate, not Exempt;
- gap-46 — require-contact / tracking / attachment flags per account.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.ledger.models import TYPE_GIFI_SECTIONS, Account
from numo9.ledger.renumber import renumber_account
from numo9.ledger.template import PROVINCES, load_template, unmapped_gifi_count
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

EXPECTED: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "coa_ca_v1" / "expected.json").read_text("utf-8")
)

#: Template accounts for supplies that carry GST/HST when bought on a bill (gap-45).
TAXABLE_BY_NATURE = {
    "6000",
    "6070",
    "6080",
    "6090",
    "6100",
    "6110",
    "6120",
    "6130",
    "6140",
    "6150",
    "6160",
    "6170",
    "6180",
    "6190",
    "6200",
    "6210",
    "5000",
    "5010",
    "5020",
}


@pytest.fixture
def owner() -> User:
    return User.objects.create_user("owner@maple.example", name="Dana Owner")


@pytest.fixture
def chart(owner: User) -> Iterator[tuple[Organisation, dict[str, Account]]]:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        load_template(org, "ON", actor=owner)
        yield org, {a.code: a for a in Account.objects.select_related("gifi")}


@pytest.mark.parametrize("province", PROVINCES)
def test_fixture_chart_per_home_province(province: str) -> None:
    expected = EXPECTED["provinces"][province]
    org = Organisation.objects.create(name=f"Org {province}")
    with org_context(org):
        load_template(org, province)
        accounts = list(Account.objects.all())
        assert len(accounts) == expected["accounts"]
        assert unmapped_gifi_count(org) == expected["unmapped_gifi"] == 0
        assert sorted(a.system_role for a in accounts if a.system_role) == expected["system_roles"]
        keys = {a.default_tax_key for a in accounts if a.default_tax_key.startswith("purchase.")}
        assert expected["purchase_key"] in keys


@pytest.mark.gap("gap-18")
def test_gap18_inventory_typed_inventory(chart: tuple[Organisation, dict[str, Account]]) -> None:
    _, accounts = chart
    inventory = accounts["1200"]
    assert (inventory.type, inventory.subtype, inventory.system_role) == (
        "asset",
        "inventory",
        "inventory",
    )
    assert inventory.gifi_id == "1121"  # Inventory of goods for sale


@pytest.mark.gap("gap-29")
def test_gap29_typing_controls_codes_renumber_and_sub_accounts(
    chart: tuple[Organisation, dict[str, Account]], owner: User
) -> None:
    org, accounts = chart
    for code in ("1700", "1710", "1720", "1730", "1740", "1750"):  # goodwill … R&D
        assert accounts[code].subtype == "intangible", code
    controls = {a.system_role: a for a in accounts.values() if a.system_role}
    # Separate controls (Xero: one 820 Sales Tax for everything).
    gst, itc = controls["gst_hst_payable"], controls["itc_receivable"]
    assert gst.pk != itc.pk and gst.subtype == "sales_tax_control" and itc.type == "asset"
    for role in (
        "wages_payable",
        "cpp_payable",
        "ei_payable",
        "income_tax_withheld",
        "vacation_payable",
        "workers_comp_payable",
        "eht_payable",
    ):
        assert controls[role].subtype == "payroll_liability", role
    qc = Organisation.objects.create(name="Fromagerie inc.")
    with org_context(qc):
        load_template(qc, "QC")
        qc_roles = set(
            Account.objects.exclude(system_role="").values_list("system_role", flat=True)
        )
    assert {"qst_payable", "qst_itr"} <= qc_roles
    bc = Organisation.objects.create(name="Coast Ltd.")
    with org_context(bc):
        load_template(bc, "BC")
        assert Account.objects.filter(system_role="pst_payable").exists()
    # Consistent 4-digit codes: system accounts sort with the others.
    assert all(len(code) == 4 and code.isdigit() for code in accounts)
    # System accounts renumber into the user's scheme.
    renumber_account(accounts["1100"], "1105", actor=owner)
    assert Account.objects.get(system_role="ar").code == "1105"
    # Sub-accounts.
    fuel = account(org, "6211", "Fuel", parent=accounts["6210"])
    assert fuel.parent_id == accounts["6210"].pk


@pytest.mark.gap("gap-30")
def test_gap30_gifi_100_percent_mapped(chart: tuple[Organisation, dict[str, Account]]) -> None:
    org, accounts = chart
    assert unmapped_gifi_count(org) == 0
    for item in accounts.values():
        assert item.gifi is not None, item.code
        assert item.gifi.is_assignable, item.code
        assert item.gifi.section in TYPE_GIFI_SECTIONS[item.type], item.code


@pytest.mark.gap("gap-44")
def test_gap44_every_change_attributed(
    chart: tuple[Organisation, dict[str, Account]], owner: User
) -> None:
    _, accounts = chart
    renumber_account(accounts["6130"], "6131", actor=owner)
    events = AuditEvent.objects.filter(object_type="ledger.Account")
    assert events.exists()
    assert set(events.values_list("actor_user", flat=True)) == {owner.pk}
    assert not events.filter(actor_label="System").exists()


@pytest.mark.gap("gap-45")
def test_gap45_expense_defaults_home_purchase_rate(
    chart: tuple[Organisation, dict[str, Account]],
) -> None:
    _, accounts = chart
    for code in TAXABLE_BY_NATURE:
        assert accounts[code].default_tax_key == "purchase.ON.standard", code
    assert accounts["6010"].default_tax_key == "purchase.ON.standard.itc50"  # meals 50 %
    exempt = [a.code for a in accounts.values() if a.default_tax_key.endswith(".exempt")]
    # Exempt only where the supply is exempt by law (financial services, insurance, interest).
    assert sorted(exempt) == ["4500", "6030", "6040", "6050", "6060"]
    expenses_with_purchase_tax = [
        a
        for a in accounts.values()
        if a.type == "expense" and a.default_tax_key.startswith("purchase.ON.")
    ]
    assert len(expenses_with_purchase_tax) >= len(TAXABLE_BY_NATURE) + 1


@pytest.mark.gap("gap-46")
def test_gap46_require_flags_per_account(chart: tuple[Organisation, dict[str, Account]]) -> None:
    _, accounts = chart
    assert accounts["1100"].require_contact and accounts["2000"].require_contact
    assert accounts["2600"].require_contact  # due to shareholder: whose loan
    meals = accounts["6010"]
    meals.require_attachment = True
    meals.require_tracking = True
    meals.save()
    meals.refresh_from_db()
    assert meals.require_attachment and meals.require_tracking
    event = AuditEvent.objects.filter(action="ledger.account.updated").last()
    assert event is not None
    assert event.changes == {"require_attachment": [False, True], "require_tracking": [False, True]}
