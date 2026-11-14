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

## Organisation settings (`orgsettings`)

Design: [Organisation settings and lock dates](../architecture/organisation-settings.md).

### `orgsettings_organisationsettings` — Organisation settings {#orgsettings-organisationsettings}

The one settings row of an organisation (A-05-T01). Business record: `OrgOwnedModel` and
`AuditedModel`. Read with `numo9.orgsettings.service.get_settings()` (creates it on first use).

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel`; `organisation_id` is **unique** (`orgsettings_one_per_org`) |
| `legal_name` | varchar(200) | no | As registered; empty until known; must contain letters (numeric-only refused, gap-55); printed on statements and tax forms |
| `display_name` | varchar(200) | no | Required; mirrored to `tenancy_organisation.name` |
| `industry` | varchar(100) | no | Free text (empty when none) |
| `structure` | varchar(32) | no | `sole_proprietorship`, `partnership`, `corporation` (default), `non_profit`, `charity`, `cooperative`, `trust`, `other` (`orgsettings_structure_valid`) |
| `mailing_attention`, `mailing_line1`, `mailing_line2`, `mailing_city` | varchar | no | Mailing address (empty when none) |
| `mailing_province` | varchar(50) | no | Canada: a province or territory code (`AB` … `YT`); elsewhere free text |
| `mailing_postal_code` | varchar(16) | no | Canada: `A1A 1A1`, first letter in the province; elsewhere free text |
| `mailing_country` | varchar(2) | no | ISO 3166-1 code; `CA` by default |
| `physical_same_as_mailing` | boolean | no | True by default: the physical address follows the mailing one |
| `physical_*` | varchar | no | Physical address, same parts as the mailing address |
| `phone` | varchar(32) | no | Valid telephone number stored as E.164 (`+14165550123`) |
| `email` | varchar(254) | no | Email address |
| `website` | varchar(200) | no | Website URL |
| `fye_month`, `fye_day` | smallint | no | Fiscal year end; 12/31 by default; month 1–12, day 1–31 (`orgsettings_fye_month_valid`, `orgsettings_fye_day_valid`) and a day the month has (model) |
| `base_currency` | varchar(3) | no | Always `CAD` (`orgsettings_base_currency_cad`); not editable |
| `time_zone` | varchar(64) | no | IANA time zone; mirrored to `tenancy_organisation.time_zone` |
| `time_format` | varchar(3) | no | `12h` (default) or `24h` for the organisation's documents and emails |
| `sales_terms_type`, `purchase_terms_type` | varchar(32) | no | `days_after_document` (default), `days_after_month_end`, `day_of_following_month`, `day_of_current_month` |
| `sales_terms_days`, `purchase_terms_days` | smallint | no | Days (0–365, default 30), or the day of the month (1–31) for the `day_of_*` types |

Audit actions: `orgsettings.organisationsettings.created`, `.updated`.
