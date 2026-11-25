# Core financial statements — presentation (K-02-T01)

Status: draft for review by the client's accountant. The statement definitions of
`numo9.reports.statements` (K-02-T02 onwards) implement this presentation; the tests use the
examples below.

The statements follow **ASPE** (Accounting Standards for Private Enterprises, CPA Canada Handbook
Part II) presentation for a Canadian private company. Every account is placed by its **type and
sub-type** (C-01); no statement has a hand-kept list of accounts.

## 1. Income statement (Profit and loss)

| Section | Accounts (sub-types) | Sign shown |
|---|---|---|
| **Revenue** | `revenue` | Credit balance shown positive |
| **Cost of sales** | `cost_of_sales` | Debit balance shown positive |
| = **Gross profit** | Revenue − cost of sales | |
| **Operating expenses** | `operating_expense`, `amortisation` | Debit positive |
| = **Operating income** | Gross profit − operating expenses | |
| **Other income** | `other_income` | Credit positive |
| **Other expenses** | `other_expense` | Debit positive |
| = **Income before income taxes** | Operating income + other income − other expenses | |
| **Income taxes** | `income_tax` | Debit positive |
| = **Net income** | Income before income taxes − income taxes | A loss shows negative: (1,234.56) in exports with accounting style |

Comparatives: none, *N previous periods* or *prior year* (K-01-T03), up to 12 columns, each a full
set of sections and sub-totals.

## 2. Balance sheet

The three sections are **always printed**, with 0.00 totals for a new organisation.

| Section | Group | Accounts (sub-types) |
|---|---|---|
| **Assets** | Current assets | `bank`, `current_asset`, `inventory`, `prepayment` |
| | Non-current assets | `fixed_asset` each followed by its **contra** `accumulated_amortisation` (the account whose parent it is; unparented contras after the last fixed asset), `intangible`, `non_current_asset` |
| = **Total assets** | | |
| **Liabilities** | Current liabilities | `current_liability`, `sales_tax_control`, `payroll_liability` |
| | Long-term liabilities | `non_current_liability` |
| = **Total liabilities** | | |
| **Equity** | | `share_capital`, `other_equity`, `dividends` (a debit, reducing equity), **Retained earnings** (the retained earnings account plus every revenue and expense **before** the current financial year), **Current year earnings** (revenue − expenses from the start of the financial year to the balance date — computed, never posted until year end, C-06) |
| = **Total equity** | | |
| = **Total liabilities and equity** | | Must equal total assets (integrity, §5) |

- Assets show debit balances positive; liabilities and equity credit balances positive; a contra
  account shows negative under its asset ("Accumulated amortization — Equipment (4,200.00)").
- **Overdrafts** (K-02-T04, with F-07): a bank or cash account with a credit balance is moved to
  current liabilities as "Bank overdraft — <name>" with the note *"Overdrawn bank and cash
  accounts are presented as current liabilities (ASPE 1510)."*
- Default date: **today** (not the end of the last financial year).

## 3. Cash flow statement

Cash = the accounts whose bank type the **cash definition** setting includes (K-02-T09):
chequing, savings, cash (petty cash) by default; credit cards, lines of credit, loans and
clearing accounts are not cash unless chosen.

**Indirect method** (K-02-T07):

| Section | Lines |
|---|---|
| Operating activities | Net income; add back non-cash items (`amortisation`); changes in working capital: each `current_asset`, `inventory`, `prepayment` (an increase uses cash), each `current_liability`, `sales_tax_control`, `payroll_liability` (an increase provides cash) |
| Investing activities | Changes in `fixed_asset`, `intangible`, `non_current_asset` (purchases use cash) |
| Financing activities | Changes in `non_current_liability`, `share_capital`, `other_equity`, `dividends`, the retained earnings account |
| = Net change in cash | Must equal cash at the end − cash at the start |

**Direct method** (K-02-T08): each line posted to a cash account is classified by the
**other side** of its journal — receipts from customers (AR, revenue), payments to suppliers (AP,
expenses, inventory), payroll (payroll liabilities, wages), sales taxes (tax control accounts),
investing (fixed and non-current assets), financing (loans, equity), other. Total = the indirect
total.

## 4. Other statements

- **Trial balance**: every account with a balance, sorted by code, opening / movement / closing
  in debit and credit columns; the totals of each pair of columns are equal.
- **General ledger detail / Account transactions**: the lines of each account in a period with
  a running balance from the opening balance; the closing balance equals the trial balance's.
- **Journal report**: the posted journals of a period with their lines, ordered by number or
  date, ascending or descending.
- **Statement of retained earnings / movements in equity**: opening retained earnings, net income,
  dividends, other movements, closing retained earnings (= the balance sheet's retained earnings
  plus current-year earnings), with a comparative period.

## 5. Integrity

Every balance sheet run checks **assets = liabilities + equity**; every income statement /
equity run checks **net income = Δ retained earnings + Δ current-year earnings**. A failure shows a
red banner on the statement ("The balance sheet doesn't balance by 12.34 — the books need a
look before this is used") and logs a `reports.integrity_failed` event for monitoring (S-04).

## Sign-off

| Role | Name | Date |
|---|---|---|
| Client's accountant | | |
| Product owner | | |
