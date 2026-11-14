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

### `orgsettings_taxregistration` — Tax registration {#orgsettings-taxregistration}

One statutory registration of an organisation and its period (A-05-T03): BN, RT, RP, RC, QST, BC
PST, Saskatchewan PST, Manitoba RST. Business record: `OrgOwnedModel` and `AuditedModel`.

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel` |
| `type` | varchar(16) | no | `bn`, `rt`, `rp`, `rc`, `qst`, `pst_bc`, `pst_sk`, `rst_mb` (`orgsettings_registration_type_valid`) |
| `number` | varchar(20) | no | Canonical form per type (`123456782`, `123456782RT0001`, `1234567890TQ0001`, `PST-1234-5678`, digits); BN check digit verified; program accounts carry the organisation's BN |
| `effective_from`, `effective_to` | date | yes | Period; open when empty; end ≥ start (`orgsettings_registration_period_valid`); no overlap for the BN or for the same number |
| `status` | varchar(16) | no | `pending`, `active` (default), `closed` (`orgsettings_registration_status_valid`) |
| `cra_approval_ref` | varchar(100) | no | Reference of the CRA / Revenu Québec approval (empty when none) |

Indexes: `(organisation, type)` (`orgsettings_reg_type_idx`).
Audit actions: `orgsettings.taxregistration.created`, `.updated`, `.deleted`, `.restored`.

### `orgsettings_lockdate` — Lock date {#orgsettings-lockdate}

A lock date of one module at one level (A-05-T04). Business record: `OrgOwnedModel` and
`AuditedModel` (its history is the audit log).

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel` |
| `module` | varchar(16) | no | `gl`, `ar`, `ap`, `bank`, `payroll`, `tax` (`orgsettings_lock_module_valid`); never changes |
| `level` | varchar(16) | no | `advisers_only`, `everyone` (`orgsettings_lock_level_valid`); never changes |
| `date` | date | yes | Changes dated on or before it are refused; empty = not locked; the `everyone` date ≤ the `advisers_only` date of the module |
| `reason` | text | no | Why the lock was set or moved (≤ 500 characters); required when the date moves back or is removed |

Unique: `(organisation, module, level)` among rows not deleted (`orgsettings_lock_one_per_module_level`).
Audit actions: `orgsettings.lockdate.created`, `.updated`, `.deleted`, `.restored`.

### `orgsettings_numberingsequence` — Numbering sequence {#orgsettings-numberingsequence}

The next number of one document type (A-05-T08). Business record: `OrgOwnedModel` and
`AuditedModel` (people's changes; allocations update `next_number` without an event).

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel` |
| `doc_type` | varchar(32) | no | `invoice`, `credit_note`, `quote`, `purchase_order`, `contact` (B-01) (`orgsettings_numbering_doc_type_valid`) |
| `prefix` | varchar(10) | no | Letters, digits, `- / _ . #`; defaults `INV-`, `CN-`, `QU-`, `PO-`, `C-` |
| `next_number` | bigint | no | ≥ 1 (`orgsettings_numbering_next_positive`); moved on by `allocate_number()` under `SELECT … FOR UPDATE` |
| `padding` | smallint | no | Minimum digits, 1–10, default 4 (`orgsettings_numbering_padding_valid`) |

Unique: `(organisation, doc_type)` among rows not deleted (`orgsettings_numbering_one_per_doc_type`).
Audit actions: `orgsettings.numberingsequence.created`, `.updated`.

## Contacts (`contacts`)

### `contacts_contact` — Contact {#contacts-contact}

A customer, supplier, employee, contractor or government agency of an organisation (B-01-T02).
Business record: `OrgOwnedModel` and `AuditedModel`; row-level security (`org_isolation`).
Design: [Contacts](../architecture/contacts.md).

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at` | — | — | As every `OrgOwnedModel` |
| `number` | varchar(20) | no | Contact number; **unique per organisation without case** (`contacts_contact_number_unique_per_org`); not empty (`contacts_contact_number_required`); from the `contact` numbering sequence when not typed |
| `display_name` | varchar(200) | no | Name shown everywhere; not empty (`contacts_contact_name_required`) |
| `legal_name` | varchar(200) | no | As registered (empty when none); never digits only |
| `roles` | varchar(32)[] | no | At least one of `customer`, `supplier`, `employee`, `contractor`, `government_agency`, each once (`contacts_contact_roles_valid`, PostgreSQL) |
| `bn` | varchar(9) | no | CRA Business Number (9 digits, check digit) or empty |
| `tax_id` | varchar(40) | no | Other tax number printed on documents, or empty |
| `currency` | varchar(3) | no | ISO 4217, default `CAD` (`contacts_contact_currency_format`) |
| `credit_limit` | numeric(18,2) | yes | Empty = no limit; ≥ 0 (`contacts_contact_credit_limit_positive`) |
| `credit_mode` | varchar(8) | no | `warn` (default) or `block` |
| `t4a_flag` | boolean | no | Payments reported on T4A slips |
| `portal_enabled` | boolean | no | Client portal access |
| `statement_pref` | varchar(8) | no | `none`, `email` (default), `post`, `portal` |
| `language` | varchar(5) | no | `en-ca` (default) or `fr-ca` |
| `status` | varchar(10) | no | `active` or `archived` |
| `archived_at` | timestamptz | yes | Set when archived (not in the audit diff: `status` is) |
| `name_key` | varchar(200) | no | Display name without case, accents, punctuation and company forms; set on save; trigram GIN index `contacts_contact_name_trgm_idx` (duplicate detection, B-01-T10) |
| `custom_fields` | jsonb | no | Values of the organisation's custom fields by key (B-01-T09); canonical forms, checked against `contacts_customfielddefinition` |
| `deleted_at` | timestamptz | yes | Set only on a contact merged into another (B-01-T12) |

Indexes: `(organisation, status, display_name)`, `(organisation, bn)`, `name_key` (GIN, `gin_trgm_ops`), the unique index above.
Audit actions: `contacts.contact.created`, `.updated`.

### `contacts_contactperson` — Contact person {#contacts-contactperson}

A person at a contact (B-01-T03); unlimited per contact. Business record: `OrgOwnedModel` and
`AuditedModel`; row-level security (`org_isolation`).

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at` | — | — | As every `OrgOwnedModel` |
| `contact_id` | bigint → `contacts_contact` | no | The contact; same organisation; `PROTECT` |
| `first_name`, `last_name` | varchar(100) | no | Name parts (empty when not known) |
| `email` | varchar(254) | no | Lower case; name or email required (`contacts_person_name_or_email`) |
| `phone` | varchar(32) | no | E.164 or empty |
| `job_title` | varchar(100) | no | Optional |
| `is_primary` | boolean | no | One primary per contact among people not removed (`contacts_person_one_primary`) |
| `include_in_emails` | boolean | no | Copied on document emails; default true |
| `deleted_at` | timestamptz | yes | Person removed (soft delete) |

Indexes: `(organisation, contact)`, `(organisation, email)`, the unique index above.
Audit actions: `contacts.contactperson.created`, `.updated`, `.deleted`, `.restored`.

### `contacts_address` — Address {#contacts-address}

A contact's billing or shipping address (B-01-T04). Business record: `OrgOwnedModel` and
`AuditedModel`; row-level security (`org_isolation`).

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at` | — | — | As every `OrgOwnedModel` |
| `contact_id` | bigint → `contacts_contact` | no | The contact; same organisation; `PROTECT` |
| `kind` | varchar(10) | no | `billing` or `shipping`; one of each per contact among rows not deleted (`contacts_address_one_per_kind`) |
| `attention`, `line1`, `line2`, `city` | varchar | no | Address lines (empty when not given) |
| `province` | varchar(2) | no | Canadian province/territory code, or empty; only with `country = 'CA'` (`contacts_address_province_valid`) |
| `region` | varchar(100) | no | Region outside Canada, or empty |
| `postal_code` | varchar(16) | no | `A1A 1A1` for Canada (first letter matches the province); free text elsewhere |
| `country` | varchar(2) | no | ISO 3166-1 alpha-2, default `CA` (`contacts_address_country_format`) |
| `deleted_at` | timestamptz | yes | Address removed (soft delete) |

Indexes: `(organisation, contact)`, the unique index above.
Audit actions: `contacts.address.created`, `.updated`, `.deleted`, `.restored`.

### `contacts_customfielddefinition` — Custom field {#contacts-customfielddefinition}

A custom field of an organisation (B-01-T09, gap-43). Business record: `OrgOwnedModel` and
`AuditedModel`.

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at` | — | — | As every `OrgOwnedModel` |
| `record_type` | varchar(16) | no | `contact` (`contacts_custom_field_record_type_valid`) |
| `key` | varchar(40) | no | `^[a-z][a-z0-9_]{0,39}$` (`contacts_custom_field_key_format`); unique per organisation and record type (`contacts_custom_field_key_unique`); immutable |
| `label_i18n` | jsonb | no | Label per language; English required |
| `field_type` | varchar(8) | no | `text`, `number`, `date`, `select` (`contacts_custom_field_type_valid`); locked once used |
| `options` | jsonb | no | Choices of a `select` field (`[{"value", "labels"}]`, 1–100); `[]` otherwise |
| `required` | boolean | no | Required on new records |
| `position` | smallint | no | Order on the form |
| `deleted_at` | timestamptz | yes | Field removed (values kept); at most 30 not removed per record type |

Audit actions: `contacts.customfielddefinition.created`, `.updated`, `.deleted`, `.restored`.

### `contacts_paymentterm` — Payment term {#contacts-paymentterm}

A payment term of the organisation's master list (B-01-T05). Business record: `OrgOwnedModel` and
`AuditedModel`.

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel` |
| `code` | varchar(32) | no | Seed key (`net_30`…) or empty; unique per organisation when set (`contacts_payment_term_code_unique`) |
| `name_i18n` | jsonb | no | Name per language; English required and unique in the organisation |
| `terms_type` | varchar(32) | no | `days_after_document`, `days_after_month_end`, `day_of_following_month`, `day_of_current_month` (`contacts_payment_term_type_valid`) |
| `days` | smallint | no | 0–365, or a day 1–31 for the day-of-month types (`contacts_payment_term_days_valid`) |
| `discount_pct` | numeric(5,2) | no | Early-payment discount, 0 ≤ x < 100 (`contacts_payment_term_discount_valid`) |
| `discount_days` | smallint | no | Discount window in days (0 without a discount) |
| `late_interest_pct` | numeric(6,3) | no | Annual late interest, 0–100 (`contacts_payment_term_interest_valid`) |
| `status` | varchar(10) | no | `active` or `archived` |
| `position` | smallint | no | Order in pickers |

Seeded rows: `due_on_receipt`, `net_15`, `net_30`, `net_60`, `2_10_net_30`, `eom` (no audit event).
Audit actions: `contacts.paymentterm.created`, `.updated`.


## Documents and files (`files`) {#files}

Tables of the documents store (A-06, [architecture](../architecture/files.md)).

### `files_document` — Document {#files-document}

One stored file of the organisation: uploaded, or an attachment of an email received at the
inbox address. Business record: `OrgOwnedModel` and `AuditedModel`; row-level security.

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel` (`created_by` = the uploader) |
| `file_key` | varchar(512) | no | Object key in the files bucket, always under `org/<organisation public id>/` (`files_document_key_required`) |
| `name` | varchar(255) | no | File name as shown |
| `mime` | varchar(127) | no | Type detected by libmagic at finalize |
| `size` | bigint | no | Bytes, 0–25 MB (`files_document_size_limit`) |
| `sha256` | varchar(64) | no | Content hash; duplicates are detected on (organisation, sha256) (`files_document_sha_idx`) |
| `status` | varchar | no | `uploading`, `scanning`, `clean`, `infected` (`files_document_status_valid`) |
| `source` | varchar | no | `upload` or `email` (`files_document_source_valid`) |
| `sender` | varchar(254) | no | Email sender (empty for uploads) |
| `sender_known` | boolean | no | The sender is a member or a contact person of the organisation |
| `inbound_message_id` | bigint | yes | → `files_inboundmessage` (email documents) |
| `period` | varchar(7) | no | `YYYY-MM` or empty (`files_document_period_format`) |
| `tax_year` | smallint | yes | 1990–2100 (`files_document_tax_year_range`) |
| `tags` | text[] | no | Up to 20 tags of ≤ 40 characters, each once (case-insensitive) |
| `folder` | varchar | no | `inbox` or `archived` (`files_document_folder_valid`); list index `files_document_inbox_idx` |
| `scan_result` | varchar(200) | no | `OK` or the virus signature |
| `scanned_at` | timestamptz | yes | When the scan finished |
| `preview_status` | varchar | no | `pending`, `ready`, `unsupported`, `password`, `failed` |
| `preview_key`, `thumbnail_key` | varchar(512) | no | Keys of the JPEG preview and thumbnail (`…/derived/`) |
| `password_protected` | boolean | no | A password-protected PDF (no preview) |

Audit actions: `files.document.created`, `.updated`, `.deleted`, `.duplicate_received`,
`.quarantined`, `.downloaded`.

### `files_attachment` — Attachment {#files-attachment}

A document linked to a record of the organisation. Business record: `OrgOwnedModel` and
`AuditedModel`; row-level security.

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel`; detach = soft delete |
| `document_id` | bigint | no | → `files_document` |
| `content_type_id` | integer | no | The record's model (`record_type`, e.g. `contacts.Contact`) |
| `object_public_id` | uuid | no | The record's public id; one live link per (document, record) (`files_attachment_once_per_record`); index `files_attachment_record_idx` |

Audit actions: `files.attachment.created`, `.deleted`.

### `files_inboundmessage` — Inbound email {#files-inboundmessage}

One email received at the organisation's inbox address. `OrgOwnedModel`; row-level security.

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel` |
| `message_id` | varchar(998) | no | `Message-ID` header; once per organisation (`files_inbound_message_once`) |
| `sender` | varchar(254) | no | `From` address |
| `subject` | varchar(300) | no | Subject |
| `recipient` | varchar(254) | no | The inbox address it was sent to |
| `raw_key` | varchar(512) | no | Key of the raw RFC 822 message in the files bucket |
| `attachment_count` | smallint | no | Documents made from it |
| `rejected` | jsonb | no | Attachments refused: `[{name, code}]` |
| `received_at` | timestamptz | no | When the webhook received it |
| `processed_at` | timestamptz | yes | When its attachments were stored |

Audit action: `files.inbound.processed`.

### `files_inboundaddress` — Inbound address {#files-inboundaddress}

The organisation's inbox address token (`docs+<token>@<domain>`). `OrgOwnedModel` and
`AuditedModel`; **no** row-level security (mail is routed by token before an organisation is
known).

| Column | Type | Null | Rules / meaning |
|---|---|---|---|
| `id`, `public_id`, `organisation_id`, `created_by_id`, `created_at`, `updated_at`, `deleted_at` | — | — | As every `OrgOwnedModel` |
| `token` | varchar(32) | no | 12 characters without look-alikes, unique across Numo9, never reused (`files_inbound_token_format`) |
| `status` | varchar(8) | no | `active` or `retired`; one active per organisation (`files_inbound_one_active_per_org`, `files_inbound_status_valid`) |
| `retired_at` | timestamptz | yes | Rotation time; mail is still accepted for 7 days after it |

Audit actions: `files.inboundaddress.created`, `.updated`.
