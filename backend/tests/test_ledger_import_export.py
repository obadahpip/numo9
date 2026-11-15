"""C-01-T13 — chart-of-accounts import/export (CSV/XLSX, mapping, dry run via the B-03 framework).

Acceptance: round trip 0 changes — the Ontario template exported as CSV and as XLSX and imported
again: the dry run and the applied import report every row unchanged and nothing is written.
Also: rows match by code (a renamed account is updated in place, never duplicated); blank cells
leave fields unchanged and ``__CLEAR__`` empties optional ones; new accounts with parents in the
same file (any order); duplicate codes and parent loops in the file; type, system role and status
are checked, not changed; every chart rule still applies (GIFI, tree, system guard); the dry run
writes no account and no audit event; the applied import is one audit batch; French headers map
themselves; the errors CSV.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator

import pytest

from numo9.audit.models import AuditEvent
from numo9.imports.mapping import as_columns, suggest
from numo9.imports.parser import parse_file
from numo9.imports.report import Action, ImportReport
from numo9.ledger.importing import (
    ACCOUNT,
    ENTITY_KEY,
    export_csv,
    export_table,
    export_xlsx,
    import_accounts,
    import_labels,
    run_import,
)
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

HEADERS = [str(item.label) for item in ACCOUNT.fields]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def chart(org: Organisation) -> list[Account]:
    return load_template(org, "ON")


def csv_bytes(rows: list[dict[str, str]], headers: list[str] | None = None) -> bytes:
    headers = headers or list(rows[0])
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def actions(report: ImportReport) -> dict[str, str]:
    return {row.key: row.action.value for row in report.rows}


def snapshot() -> list[tuple[object, ...]]:
    return list(
        Account.objects.order_by("pk").values_list(
            "pk", "code", "name_i18n", "subtype", "parent_id", "gifi_id", "default_tax_key"
        )
    )


# ---- round trip (acceptance) -----------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_round_trip_changes_nothing(org: Organisation, chart: list[Account], fmt: str) -> None:
    # A sub-account (parent column) and a French name ride along.
    advertising = Account.objects.get(code="6000")
    sub = account(org, "6001", "Online ads", parent=advertising, gifi_id="8520")
    sub.set_name("Publicité en ligne", "fr-ca")
    sub.save()
    data = export_csv(org) if fmt == "csv" else export_xlsx(org)
    before = snapshot()
    account_events = AuditEvent.objects.filter(object_type="ledger.Account").count()
    for apply in (False, True):
        report = run_import(data, f"chart.{fmt}", apply=apply)
        assert report.counts == {
            "create": 0,
            "update": 0,
            "unchanged": len(chart) + 1,
            "error": 0,
        }, [r for r in report.rows if r.action != Action.UNCHANGED]
    assert snapshot() == before
    assert AuditEvent.objects.filter(object_type="ledger.Account").count() == account_events


def test_export_shape(org: Organisation, chart: list[Account]) -> None:
    headers, rows = export_table(org)
    assert headers == HEADERS
    assert len(rows) == len(chart)
    by_code = {row[0]: dict(zip(headers, row, strict=True)) for row in rows}
    ar = next(a for a in chart if a.system_role == "ar")
    assert by_code[ar.code]["System role"] == "Accounts receivable"
    assert by_code[ar.code]["Sub-type"] == "Current asset"
    assert by_code[ar.code]["Status"] == "Active"
    assert all(row[HEADERS.index("GIFI code")] for row in rows)  # gap-30: every account mapped
    assert [row[0] for row in rows] == sorted(row[0] for row in rows)


def test_csv_export_has_a_bom_and_xlsx_keeps_codes_as_text(org: Organisation) -> None:
    account(org, "0100", "Leading zero", subtype="current_asset", gifi_id="1060")
    data = export_csv(org)
    assert data.startswith(b"\xef\xbb\xbf")
    sheet = parse_file(export_xlsx(org), "chart.xlsx").sheet
    assert sheet.headers == tuple(HEADERS)
    assert sheet.rows[0].cells[0] == "0100"
    assert parse_file(data, "chart.csv").sheet.rows == sheet.rows


def test_export_needs_the_active_organisation(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other Ltd.")
    with pytest.raises(ValueError, match="active organisation"):
        export_csv(other)


# ---- matching and non-destructive updates -------------------------------------------------------


def test_renamed_account_is_updated_in_place_by_code(
    org: Organisation, chart: list[Account]
) -> None:
    target = Account.objects.get(code="6000")
    count = Account.objects.count()
    data = csv_bytes([{"Code": target.code, "Name": "Office supplies and postage"}])
    report = run_import(data, "rename.csv", apply=True)
    row = report.rows[0]
    assert row.action == Action.UPDATE
    assert row.changes == {"name": [target.name_in("en-ca"), "Office supplies and postage"]}
    target.refresh_from_db()
    assert target.name == "Office supplies and postage"
    assert Account.objects.count() == count
    # Importing the same file again: unchanged.
    assert actions(run_import(data, "rename.csv", apply=True)) == {target.code: "unchanged"}


def test_codes_match_without_case(org: Organisation) -> None:
    account(org, "AB-10", "Mixed case", subtype="current_asset")
    report = run_import(csv_bytes([{"Code": "ab-10", "Name": "Renamed"}]), "c.csv", apply=True)
    assert actions(report) == {"ab-10": "update"}
    assert Account.objects.get(code="AB-10").name == "Renamed"


def test_blank_cells_change_nothing_and_clear_token_empties(org: Organisation) -> None:
    item = account(
        org,
        "6200",
        "Rent",
        gifi_id="8910",
        default_tax_key="purchase.ON.standard",
        description="Store lease",
    )
    item.set_name("Loyer", "fr-ca")
    item.save()
    blank = csv_bytes(
        [{"Code": "6200", "Name": "", "Name (French)": "", "GIFI code": "", "Description": ""}]
    )
    assert actions(run_import(blank, "c.csv", apply=True)) == {"6200": "unchanged"}
    cleared = csv_bytes(
        [
            {
                "Code": "6200",
                "Name (French)": "__CLEAR__",
                "GIFI code": "__CLEAR__",
                "Default tax code": "__CLEAR__",
                "Description": "__CLEAR__",
            }
        ]
    )
    report = run_import(cleared, "c.csv", apply=True)
    assert report.rows[0].changes == {
        "name_fr": ["Loyer", ""],
        "gifi": ["8910", ""],
        "default_tax_key": ["purchase.ON.standard", ""],
        "description": ["Store lease", ""],
    }
    item.refresh_from_db()
    assert (item.name_i18n, item.gifi_id, item.default_tax_key, item.description) == (
        {"en-ca": "Rent"},
        None,
        "",
        "",
    )


def test_required_fields_cannot_be_cleared(org: Organisation) -> None:
    account(org, "6200", "Rent")
    report = run_import(
        csv_bytes([{"Code": "6200", "Name": "__CLEAR__", "Sub-type": "__CLEAR__"}]), "c.csv"
    )
    assert [e.code for e in report.rows[0].errors] == [
        "ledger.import.required_clear",
        "ledger.import.required_clear",
    ]


# ---- creating accounts ----------------------------------------------------------------------


def test_new_accounts_with_parents_in_the_same_file_in_any_order(org: Organisation) -> None:
    rows = [
        {"Code": "6111", "Name": "Courier", "Sub-type": "Operating expense", "Parent code": "6110"},
        {
            "Code": "6110",
            "Name": "Shipping",
            "Sub-type": "operating_expense",
            "Parent code": "6100",
        },
        {"Code": "6100", "Name": "Office", "Sub-type": "Charge d’exploitation", "Parent code": ""},
    ]
    report = run_import(csv_bytes(rows), "new.csv", apply=True)
    # Reported in file order; the French label isn't translated yet, so row 4 is refused.
    assert [r.row for r in report.rows] == [2, 3, 4]
    assert actions(report)["6100"] == "error"
    rows[2]["Sub-type"] = "Operating expense"
    report = run_import(csv_bytes(rows), "new.csv", apply=True)
    assert actions(report) == {"6111": "create", "6110": "create", "6100": "create"}
    courier = Account.objects.select_related("parent__parent").get(code="6111")
    assert courier.parent is not None and courier.parent.code == "6110"
    assert courier.parent.parent is not None and courier.parent.parent.code == "6100"
    assert report.rows[0].changes["subtype"] == ["", "Operating expense"]


def test_new_account_needs_name_and_subtype(org: Organisation) -> None:
    report = run_import(csv_bytes([{"Code": "7000", "Name": "", "Sub-type": ""}]), "c.csv")
    assert {e.field for e in report.rows[0].errors} == {"name", "subtype"}
    assert report.rows[0].errors[0].message == "A new account needs a name."


def test_booleans_accept_yes_no_in_english_and_french(org: Organisation) -> None:
    rows = [
        {"Code": "6300", "Name": "A", "Sub-type": "Operating expense", "Require a contact": "Oui"},
        {"Code": "6301", "Name": "B", "Sub-type": "Operating expense", "Require a contact": "TRUE"},
        {
            "Code": "6302",
            "Name": "C",
            "Sub-type": "Operating expense",
            "Require a contact": "maybe",
        },
    ]
    report = run_import(csv_bytes(rows), "c.csv", apply=True)
    assert actions(report) == {"6300": "create", "6301": "create", "6302": "error"}
    assert report.rows[2].errors[0].message == "Require a contact is Yes or No, not “maybe”."
    assert Account.objects.get(code="6300").require_contact is True


# ---- refusals ----------------------------------------------------------------------------------


def test_duplicate_codes_in_the_file_are_errors_on_every_copy(org: Organisation) -> None:
    rows = [
        {"Code": "6400", "Name": "A", "Sub-type": "Operating expense"},
        {"Code": "6401", "Name": "B", "Sub-type": "Operating expense"},
        {"Code": "6400", "Name": "C", "Sub-type": "Operating expense"},
    ]
    report = run_import(csv_bytes(rows), "c.csv", apply=True)
    assert [r.action.value for r in report.rows] == ["error", "create", "error"]
    assert report.rows[0].errors[0].message == (
        "Code 6400 appears more than once in the file (rows 2, 4)."
    )
    assert not Account.objects.filter(code="6400").exists()


def test_parent_loop_in_the_file(org: Organisation) -> None:
    rows = [
        {"Code": "6500", "Name": "A", "Sub-type": "Operating expense", "Parent code": "6501"},
        {"Code": "6501", "Name": "B", "Sub-type": "Operating expense", "Parent code": "6500"},
        {"Code": "6502", "Name": "C", "Sub-type": "Operating expense", "Parent code": "6502"},
    ]
    report = run_import(csv_bytes(rows), "c.csv", apply=True)
    assert [r.action.value for r in report.rows] == ["error", "error", "error"]
    assert {e.code for r in report.rows for e in r.errors} == {"ledger.import.parent_cycle"}
    assert (
        report.rows[0].errors[0].message == "The parent codes in the file form a loop (rows 2, 3)."
    )


def test_unknown_parent(org: Organisation) -> None:
    rows = [{"Code": "6600", "Name": "A", "Sub-type": "Operating expense", "Parent code": "9999"}]
    report = run_import(csv_bytes(rows), "c.csv")
    assert report.rows[0].errors[0].message == "No account has the code 9999 (parent code)."


def test_type_system_role_and_status_are_checked_not_changed(
    org: Organisation, chart: list[Account]
) -> None:
    ar = next(a for a in chart if a.system_role == "ar")
    expense = Account.objects.filter(subtype="operating_expense").first()
    assert expense is not None
    rows = [
        {"Code": ar.code, "System role": "Accounts payable"},
        {"Code": expense.code, "Type": "Revenue"},
        {"Code": "6009", "Name": "New", "Sub-type": "Operating expense", "Status": "Archived"},
    ]
    headers = ["Code", "Name", "Sub-type", "System role", "Type", "Status"]
    report = run_import(csv_bytes(rows, headers), "c.csv", apply=True)
    codes = [[e.code for e in r.errors] for r in report.rows]
    assert codes[0] == ["ledger.import.system_role_locked"]
    assert codes[1] == ["ledger.import.type_locked"]
    assert codes[2] == ["ledger.import.status_locked"]
    assert report.rows[1].errors[0].message == (
        "The type follows the sub-type (Expense): change the sub-type instead."
    )
    # The same values as the account are fine (the export carries them).
    same = [
        {"Code": ar.code, "System role": "Accounts receivable", "Type": "Asset", "Status": "Active"}
    ]
    assert actions(run_import(csv_bytes(same), "c.csv")) == {ar.code: "unchanged"}


def test_chart_rules_still_apply(org: Organisation, chart: list[Account]) -> None:
    ar = next(a for a in chart if a.system_role == "ar")
    rows = [
        # GIFI from another section, unknown GIFI, system account sub-type change.
        {"Code": "6700", "Name": "A", "Sub-type": "Operating expense", "GIFI code": "1060"},
        {"Code": "6701", "Name": "B", "Sub-type": "Operating expense", "GIFI code": "0001"},
        {"Code": ar.code, "Name": "", "Sub-type": "Bank", "GIFI code": ""},
        {"Code": "bad code!", "Name": "C", "Sub-type": "Operating expense", "GIFI code": ""},
    ]
    report = run_import(csv_bytes(rows), "c.csv", apply=True)
    assert [e.code for r in report.rows for e in r.errors] == [
        "ledger.account.gifi_section",
        "ledger.account.gifi_unknown",
        "ledger.account.system_role_subtype",
        "ledger.account.code_invalid",
    ]
    assert report.rows[0].errors[0].message == (
        "GIFI 1060 is in Current assets: it doesn't fit a expense account."
    )
    assert not Account.objects.filter(code__in=["6700", "6701"]).exists()


def test_a_failing_row_never_undoes_the_others(org: Organisation) -> None:
    rows = [
        {"Code": "6800", "Name": "Good", "Sub-type": "Operating expense", "GIFI code": "8810"},
        {"Code": "6801", "Name": "Bad", "Sub-type": "Operating expense", "GIFI code": "1599"},
        {"Code": "6802", "Name": "Good too", "Sub-type": "Operating expense", "GIFI code": ""},
    ]
    report = run_import(csv_bytes(rows), "c.csv", apply=True)
    assert actions(report) == {"6800": "create", "6801": "error", "6802": "create"}
    assert set(Account.objects.values_list("code", flat=True)) == {"6800", "6802"}


# ---- dry run, audit, mapping, errors CSV ---------------------------------------------------------


def test_dry_run_writes_nothing(org: Organisation) -> None:
    rows = [
        {"Code": "6900", "Name": "A", "Sub-type": "Operating expense", "Parent code": ""},
        {"Code": "6901", "Name": "B", "Sub-type": "Operating expense", "Parent code": "6900"},
    ]
    events = AuditEvent.objects.count()
    report = run_import(csv_bytes(rows), "c.csv")
    assert report.applied is False
    assert actions(report) == {"6900": "create", "6901": "create"}  # child resolves its new parent
    assert Account.objects.count() == 0
    assert AuditEvent.objects.count() == events
    applied = run_import(csv_bytes(rows), "c.csv", apply=True)
    assert [(r.action, r.changes) for r in applied.rows] == [
        (r.action, r.changes) for r in report.rows
    ]


def test_applied_import_is_one_audit_batch(org: Organisation) -> None:
    rows = [
        {"Code": "7100", "Name": "A", "Sub-type": "Other income"},
        {"Code": "7101", "Name": "B", "Sub-type": "Other income"},
    ]
    run_import(csv_bytes(rows), "import-2026.csv", apply=True)
    created = AuditEvent.objects.filter(action="ledger.account.created")
    assert created.count() == 2
    batch_ids = set(created.values_list("batch_id", flat=True))
    assert len(batch_ids) == 1 and None not in batch_ids
    summary = AuditEvent.objects.get(action="audit.batch", batch_id=batch_ids.pop())
    assert summary.meta["file"] == "import-2026.csv"


def test_french_headers_map_themselves() -> None:
    headers = ["Numéro de compte", "Nom du compte", "Sous-type", "Code IGRF", "Compte parent"]
    assert as_columns(suggest(ENTITY_KEY, headers)) == {
        "Numéro de compte": "code",
        "Nom du compte": "name",
        "Sous-type": "subtype",
        "Code IGRF": "gifi",
        "Compte parent": "parent",
    }


def test_every_exported_header_maps_exactly() -> None:
    assert [s.field for s in suggest(ENTITY_KEY, HEADERS)] == list(ACCOUNT.field_keys)


def test_mapping_is_validated(org: Organisation) -> None:
    from django.core.exceptions import ValidationError

    sheet = parse_file(csv_bytes([{"Name": "A"}]), "c.csv").sheet
    with pytest.raises(ValidationError):
        import_accounts(sheet, {"Name": "name"})  # the code column is required


def test_errors_csv(org: Organisation) -> None:
    rows = [{"Code": "6600", "Name": "A", "Sub-type": "Operating expense", "Parent code": "9999"}]
    report = run_import(csv_bytes(rows), "c.csv")
    text = report.errors_csv(import_labels()).decode("utf-8-sig")
    assert list(csv.reader(io.StringIO(text))) == [
        ["Row", "Column", "Reason"],
        ["2", "Parent code", "No account has the code 9999 (parent code)."],
    ]
