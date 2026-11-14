"""export_coa_template — write the chart-of-accounts review spreadsheet (C-01-T01).

The accountant reviews ``docs/accounting/coa_template_ca_v1.xlsx``; the loader reads
``backend/numo9/ledger/data/coa_ca_v1.json``. This tool writes the spreadsheet from the JSON so
the reviewed file and the loaded chart are the same rows:

    python backend/tools/export_coa_template.py            # write the spreadsheet
    python backend/tools/export_coa_template.py --check    # exit 1 if it is out of date

Changes the reviewers ask for are made in the JSON, then the spreadsheet is written again.
Sheets: Read me · Template · Tax defaults · Checks · Review questions · Sign-off.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "backend" / "numo9" / "ledger" / "data"
TEMPLATE = LEDGER / "coa_ca_v1.json"
GIFI = LEDGER / "gifi_rc4088_rev23.csv"
OUTPUT = ROOT / "docs" / "accounting" / "coa_template_ca_v1.xlsx"

PROVINCES = ("AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT")
PROVINCE_TAX = {
    "AB": "GST 5 %",
    "BC": "GST 5 % + PST 7 %",
    "MB": "GST 5 % + RST 7 %",
    "NB": "HST 15 %",
    "NL": "HST 15 %",
    "NS": "HST 14 %",
    "NT": "GST 5 %",
    "NU": "GST 5 %",
    "ON": "HST 13 %",
    "PE": "HST 15 %",
    "QC": "GST 5 % + QST 9.975 %",
    "SK": "GST 5 % + PST 6 %",
    "YT": "GST 5 %",
}
SUBTYPE_TYPE = {
    **dict.fromkeys(
        (
            "current_asset",
            "bank",
            "inventory",
            "prepayment",
            "fixed_asset",
            "accumulated_amortisation",
            "non_current_asset",
            "intangible",
        ),
        "Asset",
    ),
    **dict.fromkeys(
        ("current_liability", "sales_tax_control", "payroll_liability", "non_current_liability"),
        "Liability",
    ),
    **dict.fromkeys(
        (
            "share_capital",
            "retained_earnings",
            "current_year_earnings",
            "dividends",
            "other_equity",
        ),
        "Equity",
    ),
    **dict.fromkeys(("revenue", "other_income"), "Revenue"),
    **dict.fromkeys(
        ("cost_of_sales", "operating_expense", "amortisation", "income_tax", "other_expense"),
        "Expense",
    ),
}
TAX_KINDS = {
    "purchase": ("purchase.<PROV>.standard", "Home-province purchase tax (ITC/ITR recoverable)"),
    "purchase_itc50": (
        "purchase.<PROV>.standard.itc50",
        "Home-province purchase tax, ITC/ITR restricted to 50 % (meals and entertainment)",
    ),
    "sales": ("sales.<PROV>.standard", "Home-province sales tax"),
    "exempt_purchase": ("purchase.exempt", "Exempt supply (financial services, insurance)"),
    "exempt_sales": ("sales.exempt", "Exempt supply (interest income)"),
    "none": ("(none)", "No tax on the account's lines (balance sheet, wages, amortization…)"),
}
REVIEW_QUESTIONS = [
    "ITCs (1400) and QST ITRs (1410) are current assets mapped to GIFI 1066 Taxes receivable, "
    "separate from GST/HST payable (2100, GIFI 2680). Keep as assets, or present as contra "
    "liabilities?",
    "Petty cash (1000) is a Bank-type account so it counts as cash and gets the negative-balance "
    "warning. Agree?",
    "PST payable (BC, MB, SK) and the QST accounts (QC) load only for those home provinces; an "
    "organisation that registers elsewhere gets the account added from this template when it "
    "registers. Agree, or load every control account in every chart?",
    "CPP and EI payable load in every chart (Quebec employers also withhold CPP/EI for "
    "employees outside Quebec and EI at the Quebec rate); QPP and QPIP load for Quebec. Agree?",
    "Employer health tax (2260 / 6340) loads for ON, BC, MB, NL and QC (QC Health Services "
    "Fund). Agree?",
    "Meals and entertainment (6010) defaults to the purchase code with a 50 % ITC/ITR "
    "restriction. Agree?",
    "Exempt defaults: 4500 Interest income, 6030 Bank charges, 6040 Payment processing fees, "
    "6050 Interest expense, 6060 Insurance. Any other account that should default to exempt "
    "(e.g. residential rent)?",
    "Accounts with no tax default: wages and employer contributions, amortization, donations, "
    "property taxes, government fees, bad debts, income taxes, grants, gains/losses. Agree?",
    "Current year earnings (3210) and Retained earnings (3200) both map to GIFI 3600 on the "
    "balance sheet; the T2 schedule 125/100 roll-forward uses 3660–3849 from the year-end "
    "process. Agree?",
    "Goodwill (1700) and Incorporation costs (1710) have no accumulated amortization account "
    "(ASPE: goodwill is tested for impairment; CCA class 14.1 is in the tax book, I-03). Agree?",
    "Require a contact: AR, AP, employee advances, customer deposits, due to/from shareholder. "
    "Any account that should also require an attachment or a tracking category by default?",
    "Codes: 4 digits, assets 1000–1999, liabilities 2000–2999, equity 3000–3999, revenue "
    "4000–4999, cost of sales 5000–5999, expenses 6000–6999, income taxes 7000–7999. Agree?",
]

HEADER = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="1F1F1F")
TITLE = Font(bold=True, size=14)
WRAP = Alignment(wrap_text=True, vertical="top")
FIXED_TIME = datetime(2026, 11, 14)  # stable file metadata: rewrites change only content


def load() -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    with GIFI.open(encoding="utf-8", newline="") as handle:
        gifi = {row["code"]: row for row in csv.DictReader(handle)}
    return template, gifi


def label(value: str) -> str:
    return value.replace("_", " ").capitalize() if value else ""


def table(sheet: Any, headers: list[str], rows: list[list[Any]], widths: list[int]) -> None:
    sheet.append(headers)
    for cell in sheet[sheet.max_row]:
        cell.font, cell.fill = HEADER, HEADER_FILL
    for row in rows:
        sheet.append(row)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = sheet.cell(row=sheet.max_row - len(rows) + 1, column=1)


def build() -> Workbook:
    template, gifi = load()
    accounts = template["accounts"]
    book = Workbook()
    book.properties.creator = "Numo9 (C-01-T01)"
    book.properties.created = book.properties.modified = FIXED_TIME

    readme = book.active
    readme.title = "Read me"
    lines = [
        [template["title"]],
        [],
        ["Template", template["template"]],
        ["Version", template["version"]],
        ["Status", template["status"]],
        ["GIFI list", f"CRA {template['gifi_list']} (2023-08-23)"],
        ["Accounts", len(accounts)],
        [],
        ["How to review"],
        ["1", "Template: check each account's type, sub-type, GIFI code and tax default."],
        ["2", "Write changes in the Reviewer comment column; mark Approved (Yes / No)."],
        ["3", "Answer the Review questions sheet."],
        ["4", "Project lead and client accountant sign the Sign-off sheet."],
        [
            "5",
            "Changes are made in backend/numo9/ledger/data/coa_ca_v1.json and this file is "
            "regenerated (backend/tools/export_coa_template.py) — never edited by hand.",
        ],
        [],
        ["Tax default kinds", "Key stored on the account", "Meaning"],
        *[[kind, key, meaning] for kind, (key, meaning) in TAX_KINDS.items()],
        [],
        ["Keys are resolved to the tax codes of G-01 in Phase 1; <PROV> is the home province."],
    ]
    for line in lines:
        readme.append(line)
    readme["A1"].font = TITLE
    readme["A9"].font = Font(bold=True)
    readme["A16"].font = readme["B16"].font = readme["C16"].font = Font(bold=True)
    readme.column_dimensions["A"].width = 22
    readme.column_dimensions["B"].width = 60
    readme.column_dimensions["C"].width = 70

    sheet = book.create_sheet("Template")
    rows = []
    for row in accounts:
        code = gifi[row["gifi"]]
        rows.append(
            [
                row["code"],
                row["name"],
                SUBTYPE_TYPE[row["subtype"]],
                label(row["subtype"]),
                label(row.get("system_role", "")),
                "Yes" if row.get("is_bank") or row["subtype"] == "bank" else "",
                "Yes" if row.get("require_contact") else "",
                row["gifi"],
                code["description"],
                label(code["section"]),
                row["tax"],
                TAX_KINDS[row["tax"]][0],
                ", ".join(row.get("provinces", [])) or "All",
                row.get("note", ""),
                "",
                "",
            ]
        )
    table(
        sheet,
        [
            "Code",
            "Name",
            "Type",
            "Sub-type",
            "System role",
            "Bank account",
            "Requires contact",
            "GIFI code",
            "GIFI description",
            "GIFI section",
            "Tax default",
            "Tax key",
            "Home provinces",
            "Notes",
            "Reviewer comment",
            "Approved",
        ],
        rows,
        [7, 44, 10, 24, 26, 8, 9, 8, 52, 24, 16, 30, 16, 60, 40, 10],
    )
    for cells in sheet.iter_rows(min_row=2):
        for cell in cells:
            cell.alignment = WRAP
    sheet.auto_filter.ref = sheet.dimensions

    taxes = book.create_sheet("Tax defaults")
    kinds = [k for k in TAX_KINDS if k != "none"]
    table(
        taxes,
        ["Home province", "Home purchase tax (2026)", *kinds],
        [
            [p, PROVINCE_TAX[p], *[TAX_KINDS[k][0].replace("<PROV>", p) for k in kinds]]
            for p in PROVINCES
        ],
        [14, 24, 26, 32, 24, 18, 16],
    )

    checks = book.create_sheet("Checks")
    types = Counter(SUBTYPE_TYPE[row["subtype"]] for row in accounts)
    mapped = sum(1 for row in accounts if row["gifi"] in gifi)
    totals = [row["code"] for row in accounts if gifi[row["gifi"]]["is_summary"] == "1"]
    roles = [row["system_role"] for row in accounts if row.get("system_role")]
    check_rows: list[list[Any]] = [
        ["Accounts in the template", len(accounts)],
        *[
            [f"{t} accounts", types[t]]
            for t in ("Asset", "Liability", "Equity", "Revenue", "Expense")
        ],
        ["Accounts with a GIFI code", f"{mapped} / {len(accounts)}"],
        ["Unmapped GIFI (gap-30: must be 0)", len(accounts) - mapped],
        ["Accounts mapped to a GIFI total line (must be 0)", len(totals)],
        [
            "4-digit codes",
            "Yes" if all(len(r["code"]) == 4 and r["code"].isdigit() for r in accounts) else "No",
        ],
        ["System roles (one account each)", f"{len(roles)} roles, {len(set(roles))} distinct"],
        [
            "Expense accounts defaulting to exempt",
            sum(
                1
                for r in accounts
                if SUBTYPE_TYPE[r["subtype"]] == "Expense" and r["tax"] == "exempt_purchase"
            ),
        ],
        [],
        ["Accounts loaded per home province"],
        *[
            [p, sum(1 for r in accounts if not r.get("provinces") or p in r["provinces"])]
            for p in PROVINCES
        ],
    ]
    table(checks, ["Check", "Result"], check_rows, [52, 24])

    questions = book.create_sheet("Review questions")
    table(
        questions,
        ["#", "Question", "Answer"],
        [[i, q, ""] for i, q in enumerate(REVIEW_QUESTIONS, start=1)],
        [5, 100, 60],
    )
    for cells in questions.iter_rows(min_row=2):
        for cell in cells:
            cell.alignment = WRAP

    sign = book.create_sheet("Sign-off")
    table(
        sign,
        ["Role", "Name", "Decision", "Date", "Signature", "Comments"],
        [
            ["Project lead (GMA)", "", "", "", "", ""],
            ["Client accountant (Profitex)", "", "", "", "", ""],
        ],
        [30, 28, 34, 14, 24, 60],
    )
    sign.append([])
    sign.append(["Decision: Approved · Approved with the changes noted · Not approved"])
    return book


def values(book: Any) -> dict[str, list[tuple[Any, ...]]]:
    """Cell values per sheet ("" and empty cells alike: a saved file reads both as None)."""
    return {
        ws.title: [tuple(None if v == "" else v for v in r) for r in ws.iter_rows(values_only=True)]
        for ws in book
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    book = build()
    if args.check:
        if not args.output.is_file():
            print(f"{args.output} is missing: run export_coa_template.py", file=sys.stderr)
            return 1
        if values(load_workbook(args.output)) != values(book):
            print(
                f"{args.output} is out of date with coa_ca_v1.json: run export_coa_template.py",
                file=sys.stderr,
            )
            return 1
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    book.save(args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
