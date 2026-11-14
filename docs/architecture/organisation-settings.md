# Organisation settings and lock dates (A-05)

| | |
|---|---|
| **Deliverable** | A-05 · Org settings, fiscal year, per-module lock dates, Phase 0 (component A — Platform Core) |
| **Branch** | `feature/A-05-org-settings-locks` |
| **Code** | `backend/numo9/orgsettings/` (models, validators, service) |
| **Depends on** | A-01 (tenancy: `OrgOwnedModel`), A-03 (roles: advisers), A-04 (audit: `AuditedModel`) |
| **Used by** | C-02 posting engine (lock dates), documents (numbering, default terms), G-01 tax codes (home province), U-05 trial (time zone), K-09 exceptions (missing BN, missing lock date) |
| **Gaps** | gap-03 (settings deep links), gap-39 (Province / Postal code, one Tax Registrations page), gap-44 (per-module locks, attribution), gap-55 (numeric legal name) |

What Xero ships (xero_teardown §6.1, §6.8): a Canadian organisation's address form asks for
"State" and "ZIP Code" with no province picker; the Business Number lives in Financial settings
while the branding editor shows "No BN" — information split over three pages; there are only two
lock dates (both empty in the teardown organisation) and no per-module lock; the system removed
"GST Type" with no user attribution; a statement header printed a number as the legal name.

## Organisation settings (A-05-T01)

`OrganisationSettings` is the one settings row of an organisation (`orgsettings_one_per_org`):

| Group | Fields |
|---|---|
| Who | `legal_name` (as registered, printed on statements and tax forms), `display_name` (required), `industry`, `structure` (sole proprietorship, partnership, corporation, non-profit, registered charity, co-operative, trust, other) |
| Where | Mailing address and physical address, each `attention`, `line1`, `line2`, `city`, `province`, `postal_code`, `country` (CA by default); `physical_same_as_mailing` (true by default: the physical address follows the mailing one) |
| Contact | `phone`, `email`, `website` |
| Accounting | `fye_month` / `fye_day` (31 December by default; 29 February means the last day of February), `base_currency` (**CAD, locked**: not editable, the model puts CAD back and the database refuses anything else — `orgsettings_base_currency_cad`), `time_zone` (IANA name), `time_format` (12 h / 24 h on the organisation's documents and emails — each person still sees their own preference in the app) |
| Default terms | `sales_terms_type` / `sales_terms_days`, `purchase_terms_type` / `purchase_terms_days` — *n* days after the document date, *n* days after the end of the document month, the *n*th of the following month, the *n*th of the current month (30 days after the document date by default; 0–365 days, or a day 1–31) |

Rules:

- **Read it with `get_settings()`** (`numo9.orgsettings.service`): the row is created on first use
  from the organisation (display name, time zone; the name becomes the legal name only when it has
  letters — an imported "1001633222" is not a legal name, gap-55).
- **Display name and time zone are mirrored** onto `tenancy.Organisation` (`name`, `time_zone`) in
  the same transaction: the directory, the org switcher, the audit log and scheduled jobs read the
  organisation; the settings page is the one place to change them.
- **Every change is audited** (`AuditedModel`): `orgsettings.organisationsettings.created` /
  `.updated` with old → new values, attributed to the person or to `System: <job>` (gap-44).
- `printed_name` — the legal name, else the display name; `address("mailing" | "physical")`.
