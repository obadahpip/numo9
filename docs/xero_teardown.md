# XERO FUNCTIONAL TEARDOWN — Organisation "REFINED" (Canada, CAD, GST/HST/PST)
Explored: 26 Oct 2026 via Chrome, logged-in user "OA".
Method: READ-ONLY exploration. Every page opened, every menu/dropdown/modal expanded, every "New" form opened
and inspected WITHOUT saving/approving/sending/deleting (this is a live ledger — creating test transactions
would pollute the books and audit trail). Org has no transactional data, so list pages show empty states.

## 0. GLOBAL SHELL
URL scheme: go.xero.com/app/!<orgShortCode>/<module>  (new React pages) + legacy ASP.NET pages (*.aspx, /Accounts/...)
 -> Mixed generations of UI: legacy aspx pages (small fonts, grey buttons) and new pages (larger, rounded) — visibly inconsistent.
Top bar: Org switcher (REFINED ▾) | Home | Sales | Purchases | Reporting | Accounting | Contacts | [+] Create | Search | JAX AI (sparkle) | Help (?) | Notifications (bell) | App launcher (grid) | Avatar (OA)
Org switcher menu: Settings, list of other orgs (Venus Family Toy Box, ZZ Ledger 004/005/006), Demo Company, Add new organization,
  Xero Partner Hub, Classic Workpapers, My Xero.
App launcher: Hubdoc, Expenses, Projects, Xero App Store.
Nav menus:
 - Sales: Sales overview, Invoices, Quotes, Products and services, Customers, Sales settings
 - Purchases: Purchases overview, Bills, Purchase orders, Checks, Suppliers, Purchases settings
 - Reporting: All reports, Account Transactions, Balance Sheet, Profit and Loss (favourites), Reporting settings
 - Accounting: Bank accounts, Bank rules, Documents, Chart of accounts, Fixed assets, Manual journals, Find and recode,
   Assurance dashboard, History and notes, Accounting settings
 - Contacts: All contacts, Customers, Suppliers, Contacts settings
"+" Quick create (with keyboard shortcuts): Invoice Alt+I, Bill Alt+B, Contact Alt+C, Quote Alt+Q, Purchase order Alt+O,
  Document upload Alt+U, Manual journal Alt+J, Spend money Alt+S, Receive money Alt+R, Transfer money Alt+T
Avatar menu: Profile, Account, Support (Xero Central), Product ideas, Log out.
Gaps (global):
 - Root URL go.xero.com/app/!vHDB1/ returns a 404 "Sorry, we can't show this page right now" instead of redirecting to Home.
 - Two UI generations coexist; breadcrumbs, button styles, list filters and empty states differ module to module.
 - Settings for Sales/Purchases/Reporting/Accounting/Contacts all point to the same generic /settings page (no deep-link to the relevant section).

## 1. HOME (Dashboard) — /app/!vHDB1/homepage
Header: org avatar + name, "Last login: 18 hours ago from Jordan" (link to login history). Button "Edit homepage" (widget customisation).
Widgets: 
 - Invoices owed to you: awaiting payment / overdue totals, aged bar chart (Older, This week, next weeks, Future), drafts, awaiting approval, New invoice, View all invoices.
 - Bills to pay: same structure for AP; Add bills, View all bills.
 - Tasks: quick add task, New task, task list.
 - Recent invoice payments (last 90 days).
 - Cash in and out: last 6 months, cash in / cash out / difference column chart, link to Bank Summary report.
 - Apps that connect with Xero (App Store ads: Shopify, Wagepoint, RBC PayEdge, TaxCycle) — "Hide".
Gaps:
 - No bank-account balance widget visible by default (no bank feeds connected); no "Account watchlist", no P&L snapshot unless added.
 - Empty charts render axis labels as "—k" instead of 0 (cosmetic bug).
 - Advertising widget occupies dashboard real estate in an accounting tool.

## 2. SALES
### 2.1 Sales overview — /app/!vHDB1/sales/overview
Header: Export (download icon), Search, Create ▾, settings cog.
Tabs/links: Invoices, Repeating invoices, Statements. "Edit dashboard".
Status tiles: Draft, Awaiting approval, Awaiting payment, Overdue (count + amount).
Cards: Quick links (Create invoice, Create repeating invoice); Money coming in (due this week / next week, chart Older..Future);
 Customers owing the most; Billable expenses; Online payments (showed "Unable to load – Refresh"); Quotes (Draft/Sent/Accepted/Expired).
Gaps:
 - "Online payments" card failed to load ("Unable to load. Refresh or try again later") — reliability issue.
 - Quotes card shows "Expired" status, but the Quotes list has no Expired tab (it shows Declined/Invoiced instead) — inconsistent status model.

### 2.2 Invoices list — /AccountsReceivable/Search.aspx (legacy)
Plan banner: "You can currently create and save invoices. To approve and track them, upgrade your plan." (plan-gated workflow)
Buttons: New Invoice ▾, New Repeating Invoice, New Credit Note, Import, Export, Invoice Reminders: Off (toggle).
Tabs: All | Draft | Awaiting Approval | Awaiting Payment | Paid.  Link: "Show deleted & voided items".
Gaps:
 - No "Overdue" tab (only visible on overview) and no "Credit notes" tab; credit notes mixed in All.
 - Legacy page: no column chooser, no saved filters, no bulk-send of statements from here.
 - Approval is paywalled — a starter plan cannot approve invoices, so invoices never reach AR. Accountant would flag that drafts are not in the ledger.

### 2.3 New invoice editor — /app/!vHDB1/invoicing/
Top: breadcrumb Sales overview › Invoices; title "New invoice" + status badge "Draft".
Actions: Preview | Save & close ▾ (Save & add another, Submit for approval) | Approve & email ▾ (Approve Ctrl+Alt+A, Approve & add another Ctrl+Alt+O,
 Approve & get link, Approve & print PDF Ctrl+Alt+R) | ⋮ (Print PDF Alt+Shift+P, Email Alt+Shift+M, Copy to draft invoice, Copy to draft quote, Delete, Sales preferences).
Banners (3 stacked): "Your invoice templates will be updated soon" (Update your templates / Invoice settings), online-payments upsell
 (Visa/MC/Amex/Apple Pay/GPay, Add online payments), "Set up invoice template" (Skip for now / Add details -> modal: Logo upload, Postal address
 (Canada address search or manual), live invoice preview, Cancel/Save).
Header fields: Contact (search/create), Issue date (default today), Due date, Invoice number (auto INV-0001), Reference,
 Online payments (Set up online payments), Amounts are: Tax exclusive / Tax inclusive / No tax.
Line grid: drag handle | Item | Description | Qty. | Price | Disc. (info tooltip) | Account | Tax rate | Tax amount | Amount | delete.
 Add row ▾ (Add 5 / 10 / 20 rows). Columns (n hidden) ▾: toggle Item, Quantity, Price, Discount, Tax amount ("won't change what customers see").
 Due-date picker: calendar + shortcuts (In 7 days, In 14 days, 1st of next month, 20th of next month, End of next month, Reset to default due date).
 Files ▾ (attachments). Footer toggle: "Send via Xero Network" (e-invoice to another Xero org; requires contact). Totals: Subtotal, Total tax, Total.
 Account dropdown: "+ Create new account", grouped by type (Revenue: 4000 Revenue 1, 4010 Revenue 2, 4020 Revenue 3, 4100 Services 1..3, 4200 Sales Returns ...).
 Tax rate dropdown: "+ Create new tax rate", provincial rates: AB GST on Purchases/Sales 5%, BC GST/PST 12%, Exempt Sales 0%, MB GST/RST 12%,
  MB GST/RST on Purchases (pre 1 July '19) 13% ...
Gaps (accountant view):
 - Tax-rate picker on a SALES invoice lists PURCHASE tax rates too (e.g. "AB - GST on Purchases") and the account picker lists every account
   type — nothing stops posting a sale to an expense account or with an input-tax code. Should filter / warn.
 - Historic, expired rates (MB RST pre-1 July 2019) still selectable on a 2026 invoice — no effective-date validation.
 - No place-of-supply logic: user must manually choose the province rate; no automatic determination from customer address.
 - Discount is per-line only (tooltip: enter a numeric value or include % for a percentage); no invoice-level discount and no early-payment (e.g. 2/10 net 30) terms.
 - No multi-currency visible on this plan (Currency field absent) — CAD only.
 - Due date field starts empty with no required marker (default terms not set for this org).
 - Three promotional banners above the form push the actual form below the fold.

### 2.4 New Repeating Invoice — /RepeatTransactions/Edit.aspx?type=AR (legacy)
Entire form is DISABLED on this plan ("ask the subscriber to upgrade their plan").
Fields: Repeat this transaction every [n] [Week(s)/Month(s)...], Invoice Date, Due Date ("Due [n] of the following month" etc.), End Date (optional),
 Save as Draft / Approve / Approve for Sending (radio), "Invoice no. will be set on invoice creation date", Invoice to, Reference,
 Online Payments, Tax Exclusive/Inclusive selector, line grid (Item, Description, Qty, Unit Price, Account, Tax Rate, Amount CAD),
 Add a new line, Subtotal/Tax/TOTAL, "Preview placeholders" (dynamic text like [Month] [Year]), Save, Cancel.
Gaps: old legacy UI, different grid from the new invoice editor (no discount column, no tax amount column); no proration, no
 usage-based billing, no contract/subscription object.

### 2.5 New Credit Note — /AccountsReceivable/EditCreditNote.aspx -> /app/!vHDB1/invoicing/credit-note
 Silently redirects back to the Invoices list on this plan — no message explaining why. (Gap: silent failure / no upgrade prompt.)

### 2.6 Import sales invoices — /Import/Import.aspx?type=IMPORTTYPE/ARINVOICES
 3-step wizard: (1) Download CSV template, (2) Copy data into template (do not change headings; dates in English (Canada) format e.g. 25-12-2026),
 (3) Browse .csv/.txt, "Update contact address details?" (No/Yes), "Is UnitAmount tax inclusive or exclusive?", Import / Cancel.
 Gaps: CSV only (no XLSX), no column-mapping step (headers must match exactly), no dry-run/validation preview shown before import.
 Direct-URL access without ?type silently redirects to Invoices list.

### 2.7 Invoice Reminders — /Settings/InvoiceSettings/Reminders/
 Disabled on plan. Config: "Email customers when an invoice is..." 7 / 14 / 21 days overdue (each Edit template), + Add reminder,
 Include button to online invoice and detail summary, Include link to invoice PDF, Don't send reminders under [amount],
 Send replies to [user email], Save.
 Gaps: overdue-only — no "before due" reminders; no escalation (e.g. stop credit / notify salesperson); no SMS/WhatsApp channel;
 no late-fee/interest automation.

### 2.8 Quotes list — /app/!vHDB1/quotes-list/
 Tabs: All | Draft | Sent | Declined | Accepted | Invoiced (counts). New quote, ⋮ menu. Search (contact, amount, reference, quote number), Filter.
 Empty state "Start creating quotes".
### 2.9 New quote editor — /app/!vHDB1/quotes/
 Fields: Contact, Issue date, Expiration date, Quote number (QU-0001), Reference, "+ Add a title & summary", Tax (Tax exclusive/...).
 Grid: Item, Description, Qty., Price, Disc., Account, Tax rate, Amount; Add row; Columns (n hidden). Terms ("edit your branding theme in Invoice settings"),
 Files, Subtotal, Total. Save ▾ (Save & close, Save & add another). ⋮ (Print PDF, Invoice settings).
 Gaps:
 - Date format differs from invoice editor ("Oct 26, 2026" vs "26 Oct 2026") — inconsistent locale handling.
 - No Tax amount column / no "Total tax" line on the quote form (unlike invoice).
 - No optional lines / alternative options, no deposit request, no e-signature acceptance on the form itself.
 - "Expired" exists on the overview card but not as a tab here.

### 2.10 Products and services — /app/!vHDB1/products-and-services
 Header: Import ▾ (Items, Opening Balances), Export ▾, New item ▾, ⋮ (Inventory Item List report, Inventory Item Summary report, Adjustment history).
 Search, + Add filter (Status, Inventory type), default chip "Status: Active", Clear filters, column settings (cog).
 Columns: Code (sorted asc), Name, Cost price, Sale price, Quantity, Actions. Paging "Showing items 0-0 of 0".
 New item modal: Code (required), Name, [ ] Track inventory item (disabled — "you'll need an Inventory account in your Chart of Accounts"),
  [x] Purchase (Cost price, Purchase account, Tax rate, Description), [x] Sell (Sale price, Sales account, Tax rate, Description),
  Save & duplicate, Save.
 Gaps (accountant):
 - Inventory tracking blocked because the chart has no Inventory-type asset account; the UI only links to help instead of offering to create it.
 - No unit of measure, no item categories/groups, no barcode/SKU separate from Code, no multiple price lists/customer-specific pricing.
 - No costing-method choice shown (FIFO vs average), no multi-location/warehouse, no reorder level, no lot/serial/expiry tracking.
 - No BOM/assemblies.

## 3. CONTACTS
### 3.1 All contacts / Customers / Suppliers — /app/!vHDB1/contacts/{all|customers|suppliers}
 Header "Contacts", New contact. Onboarding panel "Make the most of contacts in Xero" (activity/payment history/notes, custom groups,
 overdue tracking, merge duplicates; Learn more; Watch video 1:53; Close). Empty state: "You don't have any contacts yet" -> Import contacts / New contact.
 (With data the list provides search, groups, archive, merge, export — not exercisable with zero contacts.)
 Gaps:
 - Customers and Suppliers pages render the identical generic "Contacts" page (no title change) — user can't tell which filter is active.
 - Customer/Supplier role is inferred from transactions, not set on the contact; a brand-new contact appears in neither list.

### 3.2 Add contact — /app/!vHDB1/contacts/add
 Left section nav: Contact details | Addresses | Financial details | Default settings: Sales defaults | Purchase defaults.
 Contact details: Contact name (required), Account number (unique ref), Primary person (First, Last, Email), + Add another person,
  Business information: Phone (+ Add phone number), Website, Business registration number, Notes (0/4000, internal only).
 Addresses: Billing address & Delivery address (Canada address search or manual).
 Financial details: Bank account name, Bank account number, Details (used in batch payments), Tax ID number (printed on PDFs).
 Sales defaults: Sales account, Invoice due date ([n] of the following month / days after...), Amounts are (Use organisation settings),
  Sales tax (Use org settings), Discount %, Credit limit amount, [ ] Block new invoices when credit limit is reached, Xero network key.
 Purchase defaults: Purchase account, Bill due date, Amounts are, Purchase tax.
 Buttons: Cancel, Save & close.
 Gaps (accountant):
 - No default currency on contact (plan/CAD-only); no payment-terms master list (terms typed per contact).
 - No separate AR/AP control account per contact; no withholding/T4A/1099 flag; no tax-exempt certificate tracking.
 - No duplicate warning on name/tax ID while typing; credit limit has no "warn only" vs "block" approval workflow.
 - No contact-level portal / statement preference fields.

### 3.3 Import contacts — /app/!vHDB1/contacts/import/upload
 2-step wizard: Upload contacts -> Complete import. Download template, Export contacts to CSV, instructions link,
 File to upload (drag & drop). Rules shown: existing contacts are updated when *ContactName matches; blank Person1..Person5 columns
 DELETE additional people; max 1,000 contacts per import.
 Gaps: matching on name instead of a stable ID (renames create duplicates); destructive blank-column behaviour; max 5 extra people.

## 4. PURCHASES
### 4.1 Purchases overview — /Accounts/Payable/Dashboard/ (legacy)
 Help panel (video; links: purchase orders, copy contents to bills and sales invoices, bill, payments; Hide Help).
 Plan banner: "You can currently create and save draft bills and purchase orders. To approve and track them, upgrade your plan."
 Buttons: + New ▾, Import, Search (Document type, Search for, Within, Start, End, Search, Clear).
 Bills tiles: Draft / Awaiting Approval / Awaiting Payment / Overdue. Upcoming bills (Due | Paid toggle).
 Purchase orders tiles: Draft / Awaiting Approval / Approved.
 Gap: Sales overview is a modern React dashboard, Purchases overview is still legacy — the two "overview" pages look and behave differently.

### 4.2 Bills list — /app/!vHDB1/bills/list/{all|draft|...}
 Tabs: All | Draft | Awaiting approval | Awaiting payment | Paid | Repeating.
 New bill ▾: "Copy your forwarding email address" (bills.<org>.<token>@xerofiles.com — forward emails with attachments to auto-create draft bills),
  Upload bills (AI autofill, Alt+Shift+U), New bill (Alt+Shift+N).
 ⋮: Review duplicate bills, Export bills, Default bill page, Compact view (toggle).
 Search bar (contact, amount, reference), Start date, End date, Date type (Any date / Transaction date / Due date / Paid date),
 Filter panel: Deleted & voided, Show overdue bills, Document types (Bills, Credit notes...), Reset to default.
 Columns panel (drag to reorder, tick to show): View, From (locked), Status, Reference, Date, Due date (locked)… Reset to default / Save.
 Empty state: "No bills here yet – Upload, email, or create a bill manually", Upload bills, forwarding address with Copy.
 Good features worth copying conceptually: per-org inbound email for bills, AI extraction, duplicate-bill review.
 Gaps: no supplier-statement reconciliation, no early-payment-discount capture, no approval routing by amount/department (plan-gated anyway).

### 4.3 New Bill — /AccountsPayable/Edit.aspx (legacy)
 Banner: create and save only; "To approve this bill, upgrade your plan."
 Header: From (supplier), Date (26 Oct 2026), Due Date (calendar), Reference, attachment icon, Total (control-total box at top right).
 Amounts are: Tax Exclusive ▾. Grid (5 blank rows): Item, Description, Qty, Unit Price, Account, Tax Rate (ⓘ), Amount CAD, ✕.
 Add a new line ▾, "Assign expenses to a customer" (billable expenses — disabled until lines exist).
 Subtotal / Tax / TOTAL, Save, Cancel. Section "History & Notes" with Add Note.
 Gaps:
 - Bill editor is the OLD grid while invoice editor is NEW: no Disc. column, no Tax amount column, no column chooser on bills.
 - No supplier invoice-number uniqueness check visible at entry (duplicates only via separate "Review duplicate bills").
 - No withholding / holdback (construction) fields; no 3-way match against PO + receipt.

### 4.4 Purchase orders list — /app/!vHDB1/purchase-orders/list/
 Tabs: All | Draft | Awaiting approval | Approved | Billed (counts). New purchase order, ⋮.
 Search, Start/End date, Date type, Filter, Columns, "0 items".
 Columns: Number, Supplier, Reference, Date raised ↓, Delivery date, Status, Sent, Amount, Files. Paging.
### 4.5 New purchase order — /app/!vHDB1/purchase-orders/new
 Banner: "Add your organisation's contact details before sending purchase orders".
 Fields: Contact, Date raised, Delivery date, Order number (PO-0001), Reference, Currency (Canadian Dollar, locked), Tax (Tax exclusive).
 Grid: Item, Description, Qty., Price, Disc., Account, Tax rate, Tax amount, Amount; Add row ▾; Columns.
 Delivery address, Attention, Telephone, Delivery instructions (0/500). Subtotal, Total.
 Files ▾, Save ▾ (Save & close, Save & add another, Submit for approval), ⋮ (Help with purchase orders).
 Gaps (accountant):
 - No goods-received / partial receipt step; "Billed" is the only fulfilment status — no Received / Partially received.
 - POs are non-posting; no commitment/encumbrance reporting against budget.
 - No PO approval limits per user.

### 4.6 Checks / Cheques — /Checks/Search.aspx
 Intro: "All your cheques in one place… for any of your CAD bank accounts… print on standard voucher style pre-printed cheque paper."
 Buttons: Spend Money, Export, Edit Check Styles.
### 4.7 Cheque Styles — /Checks/CheckPrintStyles.aspx
 New Style; style card "Standard" with Options ▾. Paper layout: 1 cheque (on top) with 2 vouchers; Paper type: Blank;
 Font: Arial 10pt. Show on cheque: payee address, payee name, company logo, company name & address, memo, cheque number,
 account & routing numbers (MICR), cut line, bank name & address. Show on voucher: payee name, date, bank account, account number,
 item, description, amount, total, cheque number. Upload Logo, Company details.
 Gaps: spelling inconsistency in one feature — nav says "Checks", page says "Cheques", button says "Edit Check Styles";
 no positive-pay file export, no cheque register void/stale-dated tracking visible, no signature image/approval.

## 5. ACCOUNTING
### 5.1 Bank accounts — /app/!vHDB1/manage-bank-accounts
 Empty state: "No bank accounts to show — The current subscription plan for this organisation doesn't support connecting a bank feed".
 Button: Add account without bank feed -> /add-bank-account ("Add accounts for your financial institution… you'll need to manually import
 bank statements") -> Add account details modal: Bank name, Account name (unique), Account type (Credit card / Other), Currency (CAD only), Cancel/Add.
 (From the chart of accounts, "Add Bank Account" goes to /bank-search — the bank-feed institution search.)
 Gaps:
 - Account type list offers only "Credit card" and "Other" — no Chequing / Savings / Line of credit / Loan types.
 - No bank account exists, yet transactions were posted (see 5.4 — petty cash) — the system lets an org run with no bank at all.
 - Manual statement import only (CSV/OFX) on this plan; no reconciliation without a bank account.

### 5.2 Bank rules — /app/!vHDB1/bank-rules/{spend|receive|transfer}
 Tabs: Spend money rules | Receive money rules | Transfer money rules. Create rule. Onboarding panel + video. Search rules by name or condition.
### 5.3 Create bank rule — /app/!vHDB1/bank-rules/create?type=BANKRULETYPE/CASHPAY
 Tabs: Spend / Receive / Transfer money rule.
 1. Apply a bank rule: Any conditions match / All conditions match; conditions grid: Field (Payee, Description, Amount, Reference,
    Analysis code, Any text field) × Condition (equals, contains, starts with, is blank) × Value; Add condition.
 2. Set the contact: During bank reconciliation / To an existing or new contact / From the payee.
 3. Allocate line items: fixed-value lines (Description, Account, Tax Rate, Amount) + remainder by percent lines (must total 100%).
 4. Set the reference. 5. Rule details: Run this rule on (All bank accounts / specific), Name the rule. Save / Cancel.
 Gaps: no regex / "does not contain" / amount ranges visible in the condition list; no rule priority ordering shown on create;
 no "auto-reconcile without review" option; no test-against-history preview.

### 5.4 Chart of accounts — /GeneralLedger/ChartOfAccounts.aspx (legacy)
 Help panel. Buttons: Add Account, Add Bank Account, Manage GIFI Codes, Print PDF, Import, Export, Edit Report Code Mappings.
 Tabs: All Accounts | Assets | Liabilities | Equity | Expenses | Revenue | Archive. Bulk: Delete, Archive, Change Tax Rate. Search. Pager (10/25/50/100/200).
 Columns: Code ▲, Name (+description), Type, Tax Rate, Report Code (+label), YTD (link to account transactions).
 Content: 139 accounts — Current Asset 12, Fixed Asset 21, Non-current Asset 8, Current Liability 17, Non-current Liability 4, Equity 7,
  Revenue 17, Expense 53. Canadian small-business template (1000 Petty Cash … 1500 Inventory, 1700–1840 fixed/intangible with paired
  Accum. Amort. accounts, 2200–2900 liabilities incl. Source Deductions, WCB, Vacation payable, Shareholder Loan, 3400–3580 equity incl. RDTOH and
  capital dividend, 4000–4510 revenue, 5000–5950 expenses incl. EI/CPP/WCB, Meals & Entertainment non-deductible, 7050–7110 tax provisions)
  plus Xero system accounts 610 AR, 800 AP, 801 Unpaid Expense Claims, 803 Wages Payable, 820 Sales Tax, 840 Historical Adjustment,
  860 Rounding, 877 Tracking Transfers, 960 Retained Earnings.
 Add New Account modal: Account Type (ASSETS: Current Asset, Fixed Asset, Inventory, Non-current Asset, Prepayment | EQUITY: Equity |
  EXPENSES: Depreciation, Direct Costs, Expense, Overhead | LIABILITIES: Current Liability, Liability, Non-current Liability |
  REVENUE: Other Income, Revenue, Sales), Code (≤10 chars), Name (≤150), + add Reporting Name, Description, Tax (default),
  [ ] Show on Dashboard Watchlist, [ ] Show in Expense Claims, [ ] Enable payments to this account; side diagram "How account types affect
  your reports" (P&L / Balance Sheet structure). Save / Cancel.
 Import CoA (/GeneralLedger/ChartOfAccountsUploader.aspx): "What system are you importing from?", "Does the file contain balances?" (Yes / No),
  CSV/TXT file, example file, tips.
 ACCOUNTANT FINDINGS ON THIS ORG'S DATA:
 - 1000 Petty Cash has a CREDIT balance of (994.17) YTD. Cash on hand cannot be negative — expenses were paid "from petty cash"
   without any float being funded. The software allowed it with no warning.
 - The only non-zero expenses are 5515 Advertising & Promotions 117.22, 5590 Business Fees & Licenses 300.00 and 5920 Travel 576.95,
   which add up to exactly 994.17. No GST/HST input tax credit hit 820 Sales Tax, so either the purchases were coded tax-exempt or
   ITCs are being missed — worth reviewing.
 - 1500 "Inventory" is typed as Current Asset, not Inventory, which is why inventory tracking is blocked in Products & services.
 - Goodwill, Incorporation Costs, R&D, Licenses and Software are typed "Fixed Asset" — they're intangibles and belong in Non-current Asset.
 - One single 820 "Sales Tax" control account for GST, HST, PST, QST and ITCs — no separate GST/HST payable vs ITC receivable vs PST payable.
 - Mixed code lengths: 3-digit system accounts (610, 800, 820, 960) sort after 5950 in a 4-digit chart.
 GENERAL GAPS: system accounts can't be renumbered into the user's scheme; no sub-accounts / parent-child hierarchy (only report codes);
 no account-level "require tracking category / contact" controls; legacy page.

### 5.5 Tax Mapper (Map GIFI codes) — /app/!vHDB1/global-tax-mapper
 Tax form selector: T2 + T5013. Review mappings →. Left: Chart of accounts (search, Filter, sort by Account number, Period) with
 "Unmapped accounts 139" badge. Right: GIFI codes grouped (Current assets: 1000 Cash and deposits, 1001 Cash, 1002 Deposits in Canadian banks…,
 1003 Deposits… foreign…) each with Map button.
 Gaps: all 139 accounts are unmapped — the Canadian template ships with no default GIFI mapping, so a T2 export is not usable without
 manual work. Balances here show 0.00 for Petty Cash while the CoA shows (994.17) (different default period) — confusing.

### 5.6 Report codes — /GeneralLedger/ReportCodeMapping.aspx (opens in a new tab)
 Import, Export. Tabs: All Accounts | For Review (9) | Archived. Edit Mapping. Columns: Code, Account, Type, Report Code, Shortcut, Last Updated.
 The 9 "For Review" are the system accounts (610 Trade receivables, 800 Trade payables, 801/803 "Employee entitlements (wages, annual leave, etc)",
 820 "Value added tax", 840/860/877 Current liabilities, 960 Retained earnings).
 Gaps: localisation — a Canadian org gets "Value added tax" and "annual leave" (UK/AU terms) instead of GST/HST and vacation pay.

### 5.7 Documents (Files) — /Docs/Folders -> /app/!vHDB1/files/inbox
 Tabs: Inbox | Archive. Actions: Email to Documents Inbox (per-org address), Upload to Documents Inbox, Add to new (create bill/receipt/etc. from file),
 Archive to, Delete. 5-step onboarding tour: "Get a document into Xero and ready for review in less than 30 seconds" — smart capture by JAX
 (AI reads the document and pre-fills a transaction for review).
 Gaps: page was slow (several seconds of spinner; once froze the browser renderer); no folder tagging by period/tax year; no OCR
 confidence shown per field before creating the transaction.

### 5.8 Manual journals — /Journal/Search.aspx (legacy)
 Buttons: New Journal, New Repeating Journal, Import. Tabs: All | Draft | Posted | Voided | Repeating | Archive. Bulk: Archive, Void. Search.
 Columns: Narration, Date, Debit CAD, Credit CAD.
 DATA PRESENT (2 posted journals):
  - "Ontario Corporation" — 3 Jun 2026 — 417.22 / 417.22
  - "Las Vegas Trade Show" — 15 Jun 2026 — 576.95 / 576.95
 VERIFIED by opening Journal #1 (/Journal/View.aspx): "Posted Manual Journal #1", Journal Options ▾, Print PDF; Accrual and cash basis;
 amounts do not include tax. Lines: Dr 5590 Business Fees & Licenses 300.00, Dr 5515 Advertising & Promotions 26.99 + 89.10 + 1.13,
 Cr 1000 Petty Cash 417.22 — every line coded "Tax Exempt (0%)". History: "Posted by Tarik Dugmag on 15 Jun 2026" (journal dated 3 Jun).
 ACCOUNTANT FINDING: 417.22 + 576.95 = 994.17 = the petty-cash credit balance. All activity in this org is expenses booked by manual
 journal against Petty Cash. The tiny 1.13 line on Advertising looks like a tax amount expensed instead of claimed as an ITC.
 This is the textbook misuse a reviewer flags: purchases recorded through journals bypass the contact/AP ledger, receipts/attachments and
 the GST/HST input-tax-credit logic, and here they drove cash on hand negative. Journals are allowed on this plan even though invoice/bill
 approval is not — the software nudges small users toward the riskiest entry method.
 Probable owner adjustment: the money was really paid personally → credit 2900 Shareholder Loan, not Petty Cash; and split out recoverable GST/HST.
 (Travel to a Las Vegas trade show is foreign — no Canadian GST on the US portion — but the 300.00 Ontario corporation fee is a government fee, typically exempt.
 So ITCs may legitimately be nil; the main issue is the negative cash and the journal-based entry.)

### 5.9 New Manual Journal — /Journal/Edit.aspx (legacy)
 Status: Draft. Fields: Narration, Date, Auto Reversing Date (optional), [x] Default narration to journal line description,
 [x] Show journal on cash basis reports, Amounts are: No tax ▾. Grid: Description, Account, Tax Rate, Debit CAD, Credit CAD (5 rows),
 Add a new line, Subtotal / TOTAL (debit vs credit). Save as draft ▾, Post ▾, Cancel. History & Notes (Show History, Add Note).
 Gaps: no contact field on journal lines (can't tie a journal to a supplier/customer sub-ledger); no warning when a journal makes a cash/bank
 account negative; no approval/reviewer step before Post; no "journal type" (adjusting / closing / reclass) classification.

### 5.10 Fixed assets — /app/!vHDB1/fixed-assets/asset-summary/draft
 Header: "Last depreciation: none", Run depreciation, New asset (both disabled until setup), ⋮ (Import, Export — disabled; Settings).
 Onboarding: import asset register via CSV or add manually; guide link; video 2:33; Hide.
 Blocking empty state: "Start date hasn't been set" -> Set start date -> modal "Choose start date" (first day of a financial year, from when you
 started using Xero to next financial year), Cancel / Save.
 (Not exercised — setting a start date is a real change. Xero's documented flow after setup: Draft / Registered / Sold & disposed tabs, asset types, depreciation methods, period depreciation runs.)
 Gaps (accountant):
 - The module is unusable until a start date is chosen, and the menu gives no hint of that.
 - The direct URL /FixedAssets is a hard 404; the module lives only at /app/!<org>/fixed-assets.
 - Canada needs Capital Cost Allowance (CCA) classes and half-year rule as a separate TAX book; Xero's tax depreciation is limited —
   a CCA schedule is a clear differentiator for a Canadian product.
 - Org has 21 Fixed Asset accounts in the CoA but nothing links them to the register — balances and register can diverge.

### 5.11 Find and recode — /Accounts/Recoding (legacy)
 Help panel ("Find and select an entire group of transaction lines and recode them… accounts, tax rates, tracking codes and more").
 Button Find and recode. "History of Recoded Transactions": Date, Audit Report, Transactions Affected, Transaction Dates, Approved By, Status.
 Recode screen (/Accounts/Recoding/Recode): "Find transaction lines that match [All/Any] of the following conditions", + Add a condition
 (Type, Status, Account, Bank Account, Date, Reconciled Between, Transaction Total, Tax Rate, Entered By, Contact, Invoice Number/Reference, …), Search.
 Not run (it changes posted transactions). Documented flow: select lines -> choose new account/tax/tracking -> review -> recode, with an audit report kept in the history table above. Strong feature; worth copying conceptually.
 Gaps: no undo of a recode batch; recoding into a locked period depends on separate lock-date settings.

### 5.12 Assurance dashboard — /app/!vHDB1/assurance-dashboard
 Tabs: User Activity | Bank Accounts | Contacts | Invoices & Bills.
 - User Activity: a GitHub-style activity heatmap per user over 12 months (No activity -> Lots of activity), user role shown
   (Obada Abu Odeh — Advisor; Tarik Dugmag — Advisor). Toggle "Show deleted users".
 - Bank Accounts: "No bank accounts found" (edits to bank account details).
 - Contacts: contacts whose bank account details have been edited ("No edited bank accounts found") — anti-fraud check.
 - Invoices & Bills: "Invoices backdated by more than 30 days ago ▾" and "Bills backdated…" — both "No backdated".
 Gaps (accountant):
 - Backdating checks cover invoices and bills ONLY — manual journals are not monitored, though they're the riskiest entries
   (this org's only activity is two journals; Journal #1 dated 3 Jun was posted 15 Jun).
 - No segregation-of-duties check (same user creating and approving), no round-number / weekend-posting / duplicate-payment analytics.

### 5.13 History and notes — /app/!vHDB1/activity-summary
 Filters: Start date / End date (presets: This month, This quarter (1 Oct–31 Dec 2026), This financial year (1 Jan–31 Dec 2026),
 Last month, Last quarter, Last financial year), User (All users), Type (multi-select with search: Account, Asset, Bank feed, Bank rule,
 Bank statement line, Bill, Bill credit note, … Deselect all), Reset filters, Apply. Export ▾ (PDF, Excel). Result: "No results found" for last 7 days.
 Gaps: default range is only 7 days; no field-level before/after diff in the list; not exportable to CSV.

## 6. SETTINGS — /app/!vHDB1/settings (hub)
 Sections & items:
 - General: Organization details, Users, Subscription and billing, Connected apps, Email settings
 - Sales: Invoice settings (defaults, reminders, branding themes)
 - Purchases: Xero to Xero
 - Reporting: Reporting preferences, Report codes, Report fields
 - Accounting: Financial settings (year end, tax, lock dates, time zone), Chart of accounts, Fixed asset settings (fixedassets.xero.com),
   Tracking categories, Conversion balances, Export accounting data
 - Tax: Manual tax rates, Tax Mapper (GIFI)
 - Contacts: Custom contact links (CRM deep links)
 - Projects: Staff permissions
 - Footer: "Looking for user settings? Open My Xero"
 Gap: spelling flips within one screen — "Organization details" (US) / "organisation" (UK) in its own description; "Add new organization" vs URL /Organisation/Add.

### 6.1 Organization details — /app/!vHDB1/organisation-details
 Toggle: display additional details on online invoices (per-field checkboxes).
 Basic Information: Logo (1MB), Display name*, Legal name*, Industry (search), Business structure* (Company…), Business Registration Number,
 Organization description. Contact Information: Mailing address & Physical address (street/PO box, City, State, ZIP Code, Country, Attention),
 Telephone/Mobile/Fax (country code +1), Email, Website, Facebook, X (Twitter), LinkedIn. Save all changes / Cancel / Save. Privacy notice.
 Gaps (localisation): a CANADIAN org's address form uses "State" and "ZIP Code" instead of Province and Postal code; no province picker
 (which is exactly what tax-rate logic would need). No GST/HST BN field here (it's in Financial settings) and the branding editor
 shows "No BN" — information split across three pages.

### 6.2 Users — /app/!vHDB1/settings/users
 Tabs: Current users | Login history. Buttons: Add Xero Support (temporary support access), Invite a user.
 List: 2 users — Obada Abu Odeh (Xero Partner Advisor; Advisor • Contact bank account admin, Manage users, Reports; logged in 1 hour ago),
 Tarik Dugmag (Subscriber; Xero Partner Advisor; Advisor • Contact bank account admin, Manage users; logged in 4 months ago). ⋮ per user.
 Invite a user (/settings/users/invite): First name, Last name, Email; Permissions: [ ] Business and accounting -> "How much access do they need?"
 (only role offered on this plan: "Managed client"), then per-area: Expense claims, Bank accounts and balances (Comments only / Bank account admin),
 Reports (Read only / Publish reports / Set lock dates), Edit settings, Manage users, Provide support; Personalize the invite (Add a message);
 Cancel / Send invite. (Not sent.)
 Gaps: coarse role model — no custom roles, no per-module create/approve split, no approval limits by amount; the subscriber has not logged
 in for 4 months yet holds Manage users (no dormant-account alert).

### 6.3 Subscription — /Settings/ManageSubscription
 For non-subscribers: "Tarik Dugmag manages the subscription… ask them to update billing, cancel or transfer, change the pricing plan".
 Gap: advisor can't see which plan the org is on — yet half the features are plan-locked with generic "upgrade" banners.

### 6.4 Connected apps — /Settings/ConnectedApps/ -> redirects to apps.xero.com (separate domain; not inspected).

### 6.5 Email settings — /Settings/Email/
 Email address: sent as the logged-in user's name with replies to their address (Edit to set an org-wide reply-to).
 Templates (8 standard): Sales Invoice, Credit Note, Statement, Remittance, Receipt, Purchase Order, Repeating Invoice, Quote — each "DEFAULT/Basic";
 + Add email template.
 Gaps: no custom sending domain (SPF/DKIM) — emails come from Xero's domain; no per-contact language templates (no Arabic/French).

### 6.6 Invoice settings — /InvoiceSettings/InvoiceSettings.aspx (legacy)
 Help panel. Buttons: New Branding Theme ▾ (Standard, Standard (Legacy), DOCX), Default Settings, Payment Services, Sales Preferences.
 Theme card "Standard" (Options ▾): Page US Letter, margins in cm (Top 1.35cm, Bottom 1.00 cm, Address padding 1.00 cm), Font Arial Unicode MS 9pt;
 Show: tax number, column headings, tax column, unit price & qty, payment advice cut-away, registered address, logo; Logo align Right;
 Tax exclusive; tax subtotals by tax components over 0%; Headings (Draft Invoice, Invoice, Credit Note, Statement, PO, Quote, Remittance, Receipt);
 Payment service None; Terms & payment advice (none); Terms (quotes) (none); Contact details; Upload Logo.
 Gaps: US Letter page with metric margins (mixed units); three template systems coexist (Standard, Standard (Legacy), DOCX).
### 6.7 New branding theme editor — /app/!vHDB1/document-settings/editor  (not saved)
 Top: Theme name, Give feedback, Save theme; zoom (−/100%/+), desktop/mobile preview. Live invoice preview on the right.
 Left accordion:
 - Your business details: Address (Mailing / Physical / None), Additional business details (free text), Business details toggles: BN, Tax number, Email, Phone.
 - Customer details: address lines, attention to, contact name, country, preview shipping address (shown only when shipping applied); show account number, tax number, email, phone.
 - Brand and styling: Logo (JPEG/PNG/GIF), Logo position (Left/Center/Right), Brand color, Font (Inter …).
 - Content: per-column name & show (Item, Description, Quantity, Price, Discount, Tax, Amount), Preview discount, Show line items as
   (Use each invoice's setting / Tax exclusive / Tax inclusive), Tax breakdown (Combine to one line / Show tax rates separately /
   Show tax components separately / Exclude 0% rates), Currency (Always show currency code, Multi-currency conversion rate), Online links (Text links / QR Code).
 - Payment: Stripe card payments upsell (Apple Pay, Google Pay), Payment advice, Additional notes.
 - Advanced: Document titles (Approved invoice title, Draft invoice title…), printing options.
 Gaps: the preview for a Canadian org uses a New Zealand sample customer (Wellington, +64 phone); no RTL / bilingual layout (relevant for
 Arabic or French-Canadian invoices); no custom fields on documents.

### 6.8 Financial settings — /Setup/FinancialSettings.aspx (legacy)
 Banner: "Looking for the federal GST/HST return settings? … now updated from the GST/HST settings area. Updating the financial settings will
 no longer update the GST/HST return settings." -> Go to the GST/HST return settings.
 Currency: CAD Canadian Dollar (base, read-only). Financial Year End: 31 December (Change).
 Sales Tax: Tax Basis (Accrual Basis ▾), Tax ID Number (EMPTY), Tax ID Display Name (EMPTY), Tax Period (Annually ▾).
 Tax Defaults: For Sales "Based on last sale" (invoices, quotes, credit notes, receive money); For Purchases "Based on last purchase"
 (bills, POs, credit notes, spend money).
 Lock Dates: "Stop all users (except advisers) making changes on and before [date]. Auto-reconcile still runs" and
 "Stop all users making changes on and before [date]" — BOTH EMPTY.
 Time zone: (UTC-05:00) Eastern Time (US & Canada). Save / Cancel.
 History & Notes: "Edited by System Generated on 5 Jan 2026 at 16:33PM — GST Type – removed" (3 entries).
 ACCOUNTANT FINDINGS:
 - No lock date at all — every past period, including posted June journals, can still be edited by anyone. First thing to set after a close.
 - No GST/HST Business Number entered although the CoA has a Sales Tax control account; invoices would print without a BN.
 - "GST Type – removed" by the system in Jan 2026 — tax registration status changed silently with no user attribution.
 - Tax defaults "based on last sale/purchase" propagate a wrong tax code from one transaction to the next (here: Tax Exempt everywhere).
 GENERAL GAPS: tax config split over 4 places (Financial settings, GST/HST return settings, Tax rates, Tax Mapper); only two lock levels
 (no per-module locks like "AP locked, GL open"); timestamp bug "16:33PM" (24-hour time with PM suffix).

### 6.9 Tax rates — /Setup/TaxRates.aspx (legacy)
 "Getting Started with Tax Rates" panel (tax rates can have multiple components, e.g. "City Import Tax (8%)" = 5% city + 3% import; Hide).
 New Tax Rate, Delete (bulk). Columns: Name ▲, Tax Rate, Accounts using this Tax Rate, Assigned to sales tax return/s (✓).
 36 rates: per province, separate "on Purchases" / "on Sales" pairs — AB/NT/NU/YT GST 5%, BC GST/PST 12%, MB GST/RST 12% (+ pre 1 July '19 13%),
 NB/NL/PE HST 15%, NS HST 14% (+ pre 1 April '25 15%), ON HST 13%, QC GST/QST 14.975%, SK GST/PST 11%; plus Exempt Sales 0%, Sales Tax on Imports 0%,
 Tax Exempt 0%, Tax on Purchases 0%, Tax on Sales 0%.
 Add New Tax Rate modal: Display name (≤50 chars), Tax Components grid (Type of tax: GST/HST (CRA & Revenu Québec filers), QST Québec,
 PST British Columbia, PST Saskatchewan, RST Manitoba, Other; Display name; Rate %; [ ] Non-recoverable), + Add a Component, Total tax rate, Save/Cancel.
 ACCOUNTANT FINDINGS:
 - "Tax Exempt (0%)" is used by 142 accounts — i.e. EVERY account defaults to exempt, which is why the June expenses claimed no ITCs.
   For a GST registrant, expense accounts should default to the home-province purchase rate.
 - No distinction between ZERO-RATED (0%, ITCs allowed — exports, basic groceries) and EXEMPT (no ITCs) supplies other than one "Exempt Sales"
   code; the GST/HST return needs that split (lines 101 vs exempt).
 - Historical rates (MB pre-2019, NS pre-Apr-2025) can't be given an effective-date range — they just stay selectable forever.
 - No place-of-supply automation; user must pick one of 36 codes on every line.
 - Non-recoverable flag is per component (good — e.g. BC PST), but there's no partial ITC % (e.g. 50% meals & entertainment restriction).

### 6.10 Tracking categories — /Setup/Tracking.aspx (legacy)
 Help panel; "Add Tracking Category". None defined. (Per Xero docs: a small fixed number of active categories, each with options — e.g. Region, Department; not created here.)
 Gaps: no hierarchy within a category; no mandatory-tracking rule per account; a real cost-centre/project dimension is missing on this plan.

### 6.11 Conversion balances — /Setup/Welcome/EditConversionBalances.aspx (legacy)
 Buttons: Add Comparative Balances, Conversion Date. Period tab "1 Jan 2024 – 31 Dec 2024" (i.e. opening balances as at 31 Dec 2024).
 Grid: Account / Debit / Credit — pre-filled 610 Accounts Receivable, 800 Accounts Payable; Add a new line; Show all accounts; Remove zero balances.
 Totals: Total Debits / Total Credits / Adjustments (difference auto-posted). [ ] Lock balances at 31 Dec 2024 ("Only users with Adviser roles…").
 Right side guide: Starting with the right numbers — What's this?, 1. Enter bank balances, 2. Outstanding invoices, 3. Outstanding bills,
 4. Other balances, 5. Confirm.
 ACCOUNTANT FINDINGS: conversion date is 1 Jan 2025 but no opening balances were entered (no share capital, no shareholder loan, no retained
 earnings), and 2025 has no activity at all — the org's balance sheet starts from nothing, so the negative petty cash has no funding source.
 Gap: unbalanced openings are silently pushed to an "Adjustments" line (Historical Adjustment 840) instead of being blocked.
 Spelling: "Adviser" here vs "Advisor" on the Users page.

### 6.12 Export accounting data — /Reporting/GLExport/
 "Select product" dropdown grouped by GENERAL LEDGER: Accountants Enterprise (MAS), BGL Simple Fund, CaseWare, MYOB Accountants Office,
 Sage HandiLedger, … (practice/tax software targets, mostly AU/NZ). Gap: no generic CSV/JSON full-ledger export or open API export here.
### 6.13 Report fields — /Reporting/ReportFields
 "Report Fields (0) — placeholders specific to each client (e.g. Names of Directors). These can be created from your practice."
### 6.14 Reporting preferences — /app/!vHDB1/globalsettings
 "Changes affect all users". Reporting method: Accounting basis (Accrual / Cash) — note: doesn't affect custom reports or the tax basis.
 Report display: Show accounting basis, Show account code, Decimals, Include accounts with zero balance or activity (TB and layout-editor reports),
 Preview (123.00 / 45.00 / 1234.34 / 1402.34). Cancel / Save changes.
 Gap: accounting basis for reports and for tax are set on two different pages and can disagree.
### 6.15 Custom contact links — /Contacts/ContactLinks.aspx
 Add A Custom Link: Name, Link Definition (URL template), Contact Fields Chooser (insert placeholders), Save/Cancel — deep links to a CRM.
### 6.16 Xero to Xero — /Settings/Xero2Xero/
 Explains sending invoices (enter customer's Xero Network Key on their contact) and receiving bills (give suppliers your key);
 shows this org's Xero Network Key with Copy.
 Gap: closed network (Xero-to-Xero only) — no Peppol / open e-invoicing standard.
### 6.17 Connected apps — redirects to apps.xero.com (separate domain, not inspected).

## 7. ADD-ON MODULES (all plan-locked here)
### 7.1 Projects — /app/!vHDB1/projects/ -> /projects/get-started
 Marketing page: quote, invoice and monitor job profitability; time tracking (stop-start timer, location-based on mobile), 1-click job invoicing,
 profitability at a glance; video 2:01; Request Projects / Try in demo ("You must be the subscriber… to add Projects").
### 7.2 Expenses — /app/!vHDB1/expenses -> /expenses/subscribe
 Submit expense & mileage claims (Xero Me app, receipt OCR, map mileage), 1-click approval, pay per active claimant; Request Expenses / Try in demo;
 video 1:59.
### 7.3 Hubdoc — /app/!vHDB1/connect-hubdoc
 Document collection + extraction syncing to Xero with source docs attached. "Hubdoc is included in Xero Starter, Standard and Premium plans…
 not included in Xero Cashbook and Xero Ledger plans" -> payment info required here, terms checkbox, Set up Hubdoc (not done).
 Inference: together with the locked approval/bank-feed/reminder features, REFINED is on a Ledger/Cashbook-type compliance plan.
 Gap (product strategy): core accounting capabilities (approving invoices, bank feeds, credit notes) are split across tiers and add-ons;
 the "upgrade" messages never say which plan unlocks what.

## 8. GLOBAL SEARCH & AI
### 8.1 Search panel (magnifier icon)
 Side panel "Search contacts and transactions", filter ▾ (All, Contacts, Bills, Invoices, Quotes, Purchase orders, Bank transactions).
 Test: "petty" -> No results; "Ontario" -> No results.
 Gaps: search does NOT cover manual journals (the only transactions in this org), accounts, settings pages, reports or navigation.
### 8.2 JAX (AI assistant, Beta) — sparkle icon
 Side panel: history menu, new chat, expand, close. Starters: Research, Analyse this client, Find, Get help. "+" attachments.
 Disclaimer: "JAX is AI and can make mistakes. Outputs are not financial, tax or legal advice."
 Test question: "What is the current balance of the Petty Cash account and which transactions make it up?" — answered correctly in ~25s:
 −$994.17 CAD as at 2026-10-26 (accrual), with a running-balance table (2026-06-03 Journal 1 MANJOURNAL Ontario Corporation 417.22 Cr;
 2026-06-15 Journal 2 Las Vegas Trade Show 576.95 Cr) and a note that a negative asset balance means more was paid out than funded.
 Observation: the AI can read journals that the normal search can't find — capability is inconsistent across features.
 Gaps: it flagged the symptom but not the fixes (missing ITCs, journal-based entry, no lock date); no one-click "create the correcting entry" draft.

## 9. REPORTING — reporting.xero.com/!vHDB1/...
### 9.1 Reports home — /!vHDB1/home
 Tabs: Home | Custom | Adviser | Drafts | Published | Archived. "Find a report" search. Favourites (star): Account Transactions, Balance Sheet, Profit and Loss.
 "All reports" with Show descriptions toggle; each report has ☆ favourite and ⋮ menu. Report IDs in URLs: /v1/Run/<id> (legacy runner) and /v2/Run/New/<id>.
 Catalogue (report id in brackets):
 - Financial performance: Budget Manager (/Reports/EditBudget.aspx), Budget Summary [1079], Budget Variance [1019], Cash Summary [1039],
   Executive Summary [1077], Tracking Summary [1048]
 - Financial statements: Balance Sheet [1017], Blank Report [1010], Depreciation Schedule [1020], Disposal Schedule [1021],
   Fixed Asset Reconciliation [1035], Management Report [1011], Movements in Equity [1018], Profit and Loss [1016],
   Statement of Cash Flows – Direct Method [1060]
 - Payables and receivables: Aged Payables Detail [1003] / Summary [1000], Aged Receivables Detail [1002] / Summary [1001],
   Contact Transactions – Summary [1037], Customer Invoice Activity [1031], Expense Claim Detail [1004], Income and Expenses by Contact [1006],
   Supplier Bill Activity [1032]
 - Reconciliations: Account Summary [1012], Bank Reconciliation [1066], Bank Summary [1065], Cash Validation Customer Report [1038],
   Inventory Item List [1223], Open Backorders [1225], Reconciliation Reports [1015], Uncoded Statement Lines
 - Taxes and balances: General Ledger Detail [1071], General Ledger Exceptions [1072], General Ledger Summary [1070], Journal Report [1098],
   Trial Balance [1005], Trial Balance by Date Range [1027]
 - Transactions: Account Transactions [1009], Backorder History [1226], Duplicate Statement Lines [1090], Inventory Item Details [1222],
   Inventory Item Summary [1224], Sales By Item (new, v2 GUID id)
 Gaps (accountant):
 - "Taxes and balances" contains NO sales-tax report: no GST/HST return, no Sales Tax Report, no tax-by-rate detail visible on this plan —
   for a GST registrant that is the most-used report.
 - No indirect-method cash-flow statement (direct only); no comparative statement of retained earnings beyond "Movements in Equity".
 - No AR/AP control-account vs sub-ledger reconciliation report.
 - Two report engines (v1 / v2) with different URLs — same report reachable both ways.

### 9.2 Profit and Loss runner — /!vHDB1/v2/Run/New/1016 (redirected to /v1/Run/1016)
 Left panel (Minimise): "Xero standard report: Profit and Loss"; Common formats: Budget Variance, Current and previous 3 months,
 Current financial year by month, Current financial year by month – actual and budget, Month to date comparison, Year to date comparison;
 Learn how to create a custom report.
 Toolbar: Date range (preset "This month", 1 Oct 2026 – 31 Oct 2026, ▾ presets), Compare with (None ▾), ⋮ More (options), Update. ★ favourite.
 Output: title "Profit and Loss", subtitle line, "For the month ended 31 October 2026", column Oct 2026, Gross Profit –, Net Profit –.
 Footer bar: Edit layout, Insert content ▾, Compact view (toggle), Save as ▾, Export ▾.
 Gaps:
 - The report's organisation line prints "1001633222" (a number stored as the legal name / contact details) instead of the company name —
   the same number appears on the cheque style and invoice theme. Data-quality issue that flows onto every statement.
 - Empty sections print "–" with no "no activity in this period" hint; the June expenses only appear if the user changes the range.
 Date-range presets: This month, This quarter, This financial year, Last month, Last quarter, Last financial year, Month to date,
 Quarter to date, Year to date, custom. Compare with: None, 1–4 years / periods, "Enter a different number"; Previous: Month / Quarter / Year.
 Run for This financial year: Operating Expenses — Advertising & Promotions 117.22, Business Fees & Licenses 300.00, Travel 576.95;
 Total 994.17; Net Profit (994.17). No revenue at all.
 Gap: titled "For the year ended 31 December 2026" on 26 Oct — a future period end with no "year-to-date / unaudited" label.

### 9.3 Balance Sheet — /v1/Run/1017
 Defaults to "End of last financial year" (31 Dec 2025) — so a first-time user sees an empty sheet.
 Date presets: Today, End of this month, End of last month, End of last quarter, End of last financial year, Custom date.
 Compare with: None, 1–4 days/periods, different number; Period: Day / Month / Quarter / Year.
 More: Accounting basis (Accrual / Cash), Include accounts with zero balance or activity, Show accounting basis / account codes / decimals.
 Common formats: Monthly / Quarterly / Yearly comparison.
 Footer: Edit layout, Insert content (Text block, Footer, Enable Add note — hover a cell to annotate), Compact view, Save as (Draft, Published, Custom),
 Export (PDF, Styled PDF, Excel, Google Sheets).
 Edit layout (/v2/EditLayout/1017): full-page editor with toolbar (text, table, footer, … PDF preview), Cancel / Update layout — lists every
 account row. Not saved (discarded on exit).
 Run as at Today: Assets – Current Assets – Petty Cash (994.17); Total Assets (994.17); Net Assets (994.17); Equity – Current Year Earnings (994.17).
 ACCOUNTANT FINDINGS / GAPS:
 - Negative cash shown as a negative ASSET; no automatic reclassification to a liability (overdraft / due to shareholder) as GAAP presentation requires.
 - No Liabilities section printed at all when empty — statement doesn't show the standard A = L + E structure.
 - Layout editor lists contra accounts alphabetically and with inconsistent naming ("Accum Amort." vs "Accum. Amort"), separated from their assets.

### 9.4 Trial Balance — /v1/Run/1005 (related: Trial Balance by Date Range)
 Controls: Date (defaults to end of last FY), Columns (Account, Account Class, Account Code, Account Type, Credit – Month, Credit – YTD,
 Debit – Month, Debit – YTD; 5 selected by default), Compare with (default "1 year"), Grouping/Summarising (Group by / Summarise by:
 None, Account Class, Account Type), More, Update, Reorder columns.
 Run as at 26 Oct 2026: 5515 Advertising & Promotions Dr 117.22; 5590 Business Fees & Licenses Dr 300.00; 5920 Travel Dr 576.95;
 1000 Petty Cash Cr 994.17; Total 994.17 / 994.17.
 Gaps: rows not sorted by account code (expenses print before assets); YTD-only columns hide opening balances; no "adjusted TB" with
 proposed-adjustment columns for year-end work.

### 9.5 Journal Report — /v1/Run/1098
 Header buttons: Go to manual journals, Add new journal. Controls: Date range (presets as P&L), Columns (8 selected), Order by (Journal ID),
 Filter (modal: search filters; Columns — Account (multi-select list with Select all), Account Code, Credit, Debit, Description, Journal ID, …; Cancel/Apply).
 Run for 2026: Journal 2 "Las Vegas Trade Show" 15 Jun 2026 — Dr 5920 Travel 576.95 / Cr 1000 Petty Cash 576.95, posted 15 Jun by Tarik Dugmag;
 Journal 1 "Ontario Corporation" 3 Jun 2026 — Dr 5590 300.00, Dr 5515 26.99 / 89.10 / 1.13, Cr 1000 417.22, posted 15 Jun by Tarik Dugmag.
 Total 994.17 / 994.17. (Both journals now VERIFIED line by line.)
 Gap: "Order by Journal ID" outputs 2 before 1 (descending) with no direction control.

### 9.6 General Ledger Exceptions — /v1/Run/1072
 Controls: Date range, Columns (Account Code, Contact, Credit, Date, Debit, Description, Invoice Number, Reason, Reference, Source…; 9 selected),
 Grouping (Group by Account), Filter, More, Update.
 Run for 2026: "Nothing to show here".
 ACCOUNTANT FINDING / GAP: the exceptions report flagged NOTHING even though this ledger has a negative cash account, expense journals with no
 contact, every line tax-exempt, and journals posted 12 days after their date. Its rule set is too narrow to be a real review tool.

### 9.7 Executive Summary — /v1/Run/1077
 Controls: Date range, Compare with (1 month), Filter, More. Sections: Cash (received, spent, surplus, closing bank balance), Profitability
 (income, direct costs, gross profit, other income, expenses, profit), Balance Sheet (debtors, creditors, net assets), Sales (# invoices,
 average value), Performance (GP %, NP %, ROI p.a.), Position (debtor days, creditor days, short-term cash forecast, current ratio, term ratio).
 Oct 2026 vs Sep 2026: everything "–" except Net assets (994.17).
 Gaps: "Closing bank balance" ignores Petty Cash (only bank-type accounts count as cash); hidden column header "Variance for Variance" leaks into
 the page text (accessibility label bug).

### 9.8 Report search & tabs
 "Find a report" for "tax" returns only General Ledger Detail – Account transactions with tax rates, and the group "Taxes and balances"
 whose description says "Review sales tax…" — yet the group contains no sales-tax report. CONFIRMED: no GST/HST return or tax report on this plan.
 Adviser tab: "All adviser reports" — practice templates: Liberty Tax Kingston; Company – Compilation Engagement Report; Company – NTR;
 Company – Review; Compilation Engagement Report, Notes, RE; Partnership – NTR / Review; Sole Proprietor – NTR; Trust – NTR / Review.
 (Canadian engagement types: NTR = Notice to Reader, Review, Compilation — CSRS 4200.)
 Custom tab: "No Reports". Drafts / Published / Archived hold saved report versions.

============================================================================================================
## 10. CONSOLIDATED GAP LIST & BUILD RECOMMENDATIONS (accountant's view)
============================================================================================================
A. ISSUES FOUND IN THIS ORGANISATION'S BOOKS (REFINED)
 1. Petty Cash (1000) is −994.17 — impossible for cash on hand. Cause: two manual journals (3 Jun Ontario Corporation 417.22;
    15 Jun Las Vegas Trade Show 576.95) crediting Petty Cash with no float ever funded.
 2. Expenses entered by manual journal instead of bills/spend money: no supplier, no receipt, no AP, no audit trail of payment.
 3. Every account defaults to Tax Exempt (142 accounts) and the journal lines are all exempt; a 1.13 line looks like tax expensed — ITCs likely missed.
 4. No GST/HST BN in Financial settings; system removed "GST Type" on 5 Jan 2026.
 5. No lock dates set; no opening/conversion balances (no share capital, no shareholder loan, no retained earnings).
 6. 0 of 139 accounts mapped to GIFI — T2 can't be prepared from the ledger as is.
 7. CoA typing errors: 1500 Inventory typed Current Asset (blocks inventory), intangibles typed Fixed Asset, single Sales Tax control account.
 8. Subscriber hasn't logged in for 4 months but keeps user-management rights.
 9. Balance Sheet presents Petty Cash (994.17) as a negative asset; net assets negative; Current Year Earnings (994.17) with no capital behind it.
 10. Every statement header shows "1001633222" instead of the company's name.
 Suggested correcting entry (for the client's accountant to confirm): Dr 1000 Petty Cash 994.17 / Cr 2900 Shareholder Loan 994.17
 (if the owner paid personally), recode recoverable GST/HST on Canadian purchases to ITCs, set a lock date at 30 Jun 2026.

B. PRODUCT GAPS IN XERO (opportunities for your version)
 Tax / compliance (biggest differentiator for a regional product)
  - Auto tax-code selection from customer/supplier province (place of supply), with effective-dated rates instead of "pre-2019" duplicates.
  - Separate zero-rated vs exempt, partial ITC % (e.g. 50% meals), separate GST/HST payable vs ITC receivable accounts out of the box.
  - Default GIFI / statutory mapping shipped with the chart; CCA classes for fixed assets.
  - Localised labels everywhere (Province/Postal code, GST/HST, vacation pay — no "VAT", "State/ZIP", NZ sample data).
  - For a MENA build: VAT (JO sales tax, KSA ZATCA e-invoicing, UAE FTA) and Arabic RTL documents would be equivalent must-haves.
 Controls
  - Warn/block negative cash & bank balances; require contact + attachment on expense journals; journal approval step.
  - Assurance checks on journals (backdating, round amounts, weekend postings, same creator/approver).
  - Per-module lock dates; dormant-user alerts; custom roles with approval limits.
 Workflow / UX
  - One UI generation: Xero mixes legacy .aspx and new React pages (different grids for bill vs invoice editors, different date formats).
  - Filter account/tax pickers by context (sales vs purchase); stop silent redirects (credit note, import) and the root-URL 404.
  - Global search across journals, accounts, settings and reports.
  - PO receiving (partial receipts, GRN) and 3-way match; invoice-level and early-payment discounts; before-due reminders + WhatsApp/SMS.
  - Inventory: units, categories, locations, costing method, batch/serial, BOM.
  - Contacts: stable-ID import matching, non-destructive updates, roles set explicitly (customer/supplier), currency per contact.
  - Exports: generic full-ledger CSV/JSON; open e-invoicing standards instead of a closed Xero-to-Xero network.
  - Clear plan/feature matrix inside the app instead of generic "upgrade" banners.
 Reporting
  - A real sales-tax return/report on every plan; indirect-method cash flow; adjusted TB with proposed-adjustment columns.
  - An exceptions engine that actually catches negative cash, missing contacts, unusual tax codes, late postings and journals to cash accounts.
  - Correct GAAP presentation (negative cash reclassified to liabilities, always-printed L section) and the org name on statements.
 Features worth matching (Xero does these well)
  - Per-org inbound email for bills + AI extraction; duplicate-bill review; bank rules with fixed + % allocations; find & recode with audit
    report; assurance heatmaps; report layout editor with notes, Save as Draft/Published and Excel/Google Sheets export; adviser report templates (NTR/Review/Compilation); keyboard shortcuts on the "+" menu; column chooser & saved views on lists; AI assistant that can query the ledger.

C. BUILD NOTE
 This file is a functional specification. Build original screens, naming and branding rather than reproducing Xero's UI or text,
 to avoid IP issues.
