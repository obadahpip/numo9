# Data dictionary

One entry per table: what a row is, each column, its rules and who writes it. Entries are added
with the deliverable that creates the table (T-04 assembles the complete dictionary for go-live).

## General ledger (`ledger`)

### `ledger_account` — Account {#ledger-account}

An account of an organisation's chart (C-01). Business record: `OrgOwnedModel` (scoped to the
active organisation, soft delete, public UUID) and `AuditedModel` (every change in the audit log).
Design: [Chart of accounts](../architecture/chart-of-accounts.md).

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id` | bigint | no | Primary key (never shown; references use it) |
| `public_id` | uuid | no | Id in URLs and APIs; unique |
| `organisation_id` | bigint → `tenancy_organisation` | no | Owning organisation; `PROTECT` |
| `code` | varchar(10) | no | 1–10 letters, digits, `.`, `-`; **unique per organisation without case** (`ledger_account_code_unique_per_org`); renumbered by `renumber_account` only |
| `name_i18n` | jsonb | no | Name per language `{"en-ca": …, "fr-ca": …}`; English required, ≤ 150 characters each; read in the active language with English fallback |
| `description` | text | no | Optional longer description (empty string when none) |
| `type` | varchar(16) | no | `asset`, `liability`, `equity`, `revenue`, `expense`; follows the sub-type |
| `subtype` | varchar(32) | no | One of 24 sub-types; must belong to `type` (`ledger_account_subtype_in_type`) |
| `parent_id` | bigint → `ledger_account` | yes | Parent for sub-accounts: same organisation and type, depth ≤ 4, parent not a system, archived or posted-to account; `PROTECT`; never itself (`ledger_account_not_own_parent`) |
| `system_role` | varchar(32) | no | Empty, or the role the engine posts to (`ar`, `ap`, `gst_hst_payable`, `itc_receivable`, `pst_payable`, `qst_payable`, `qst_itr`, `retained_earnings`, `current_year_earnings`, `rounding`, `suspense_conversion`, `unpaid_expense_claims`, `wages_payable`, `cpp_payable`, `qpp_payable`, `ei_payable`, `qpip_payable`, `income_tax_withheld`, `vacation_payable`, `workers_comp_payable`, `eht_payable`, `inventory`, `fx_gain_loss`); one account per role per organisation (`ledger_account_one_per_system_role`); immutable once set |
| `is_bank` | boolean | no | True for every `bank` sub-type (`ledger_account_bank_subtype_is_bank`); allowed only on `bank`, `current_liability`, `non_current_liability` (`ledger_account_is_bank_subtype`) |
| `gifi_code` | varchar(4) → `ledger_gificode.code` | yes | CRA GIFI code; must exist, not be a total line, and fit the type's sections; `PROTECT` |
| `require_contact` | boolean | no | Journal lines on the account must name a contact (enforced by C-03) |
| `require_tracking` | boolean | no | Journal lines must carry a tracking category (C-03) |
| `require_attachment` | boolean | no | Journals hitting the account need an attachment (C-03) |
| `default_tax_key` | varchar(60) | no | Default tax code key: `purchase.<PROV>.standard`, `purchase.<PROV>.standard.itc50`, `sales.<PROV>.standard`, `purchase.exempt`, `sales.exempt`, or empty; resolved to a G-01 tax code in Phase 1 |
| `status` | varchar(16) | no | `active` or `archived` (system accounts: never archived) |
| `archived_at` | timestamptz | yes | Set when archived, cleared when reactivated (not in the audit diff: `status` is) |
| `template_ref` | varchar(40) | no | Template row the account came from (`ca_v1:1100`); survives renumbering; empty for user-created accounts |
| `created_by_id` | bigint → `accounts_user` | yes | Who created it (empty for system processes) |
| `created_at`, `updated_at` | timestamptz | no | Set automatically |
| `deleted_at` | timestamptz | yes | Soft delete; refused for system accounts and accounts with transactions |

Indexes: `(organisation, parent)`, `(organisation, type, code)`, the unique indexes above.
Audit actions: `ledger.account.created`, `.updated`, `.deleted`, `.restored`, `.renumbered`; a
template load is one batch (`audit.batch`, meta: template, version, province).

### `ledger_gificode` — GIFI code {#ledger-gificode}

One line of the CRA General Index of Financial Information (C-01-T04). Platform data (the same for
every organisation; allow-listed in `tenancy.checks.PLATFORM_MODELS`), seeded by migration.

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id` | bigint | no | Primary key |
| `code` | varchar(4) | no | Unique; exactly 4 digits (`ledger_gifi_code_4_digits`) |
| `description` | varchar(200) | no | CRA description (English; French with Phase 6) |
| `section` | varchar(40) | no | `current_assets`, `tangible_capital_assets`, `intangible_capital_assets`, `long_term_assets`, `current_liabilities`, `long_term_liabilities`, `shareholder_equity`, `partners_capital`, `retained_earnings`, `other_comprehensive_income`, `revenue`, `cost_of_sales`, `operating_expenses`, `farm_revenue`, `farm_expenses`, `extraordinary_items_and_taxes` |
| `is_summary` | boolean | no | Total or computed line (e.g. 1599, 3620, 9367); never mapped to an account |
| `list_version` | varchar(40) | no | CRA list the row comes from: `RC4088(E) Rev. 23` |
| `published_on` | date | no | Publication date of that list: 2023-08-23 |
| `retired_in` | varchar(40) | no | Empty, or the list version that dropped the code (kept for history) |
