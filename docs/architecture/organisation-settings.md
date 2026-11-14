# Organisation settings and lock dates (A-05)

| | |
|---|---|
| **Deliverable** | A-05 · Org settings, fiscal year, per-module lock dates, Phase 0 (component A — Platform Core) |
| **Branch** | `feature/A-05-org-settings-locks` |
| **Code** | `backend/numo9/orgsettings/` (models, validators, service) |
| **Libraries** | `phonenumbers` (telephone numbers, A-05-T02) |
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

## Validation (A-05-T02)

`save()` tidies the input (surrounding spaces, upper-case province, country and postal code, the
locked currency) and then reports **every** problem at once as a `ValidationError` keyed by field,
each with a stable code — the settings form shows them inline (A-05-T11).

| Field | Rule | Code |
|---|---|---|
| `legal_name` | Must contain letters: "1001633222", "123-456" or "#1" are refused, "1001633222 Ontario Inc." is fine (gap-55) | `orgsettings.legal_name.numeric` |
| `*_province` (Canada) | One of AB, BC, MB, NB, NL, NS, NT, NU, ON, PE, QC, SK, YT (`validators.Province`) | `orgsettings.province.invalid` |
| `*_postal_code` (Canada) | Canada Post format `A1A 1A1` (no D, F, I, O, Q, U; no W or Z first); typed in any case, with or without the space; stored as `M5X 1A9` | `orgsettings.postal_code.invalid` |
| `*_postal_code` + `*_province` | [EXTRA] The first letter belongs to the province: A NL · B NS · C PE · E NB · G H J QC · K L M N P ON · R MB · S SK · T AB · V BC · X NT/NU · Y YT | `orgsettings.postal_code.province_mismatch` |
| `*_country` | Two-letter ISO code; an address outside Canada keeps its own region and postal code (no Canadian rules) | `orgsettings.country.invalid` |
| `phone` | Parsed by `phonenumbers` as Canadian unless it starts with `+`; must be a valid number; stored as E.164 (`+14165550123`) | `orgsettings.phone.invalid` |
| `fye_day` | A day the month has | `orgsettings.fye_day_invalid` |
| `*_terms_days` | 0–365 days, or a day 1–31 for the "of the month" terms | `orgsettings.terms_day_invalid` |

The physical address is checked only when it is separate (`physical_same_as_mailing` false).

## Tax registrations (A-05-T03)

Every statutory number lives in one place — `TaxRegistration`, shown on the one Tax Registrations
page (A-05-T12) — instead of Xero's split across organisation details, financial settings and the
GST/HST settings (gap-39). One row per registration and period:

| `type` | What | Stored as | Shown as | Check |
|---|---|---|---|---|
| `bn` | Business Number | `123456782` | `123456782` | 9 digits, [EXTRA] Luhn check digit (not `000000000`) |
| `rt` | GST/HST program account | `123456782RT0001` | `123456782 RT 0001` | A valid BN + the type's own letters + a reference 0001–9999 |
| `rp` | Payroll program account | `123456782RP0001` | `123456782 RP 0001` | as RT |
| `rc` | Corporate income tax program account | `123456782RC0001` | `123456782 RC 0001` | as RT |
| `qst` | Quebec QST number | `1234567890TQ0001` | `1234567890 TQ 0001` | 10 digits + TQ + a reference 0001–9999 |
| `pst_bc` | British Columbia PST | `PST-1234-5678` | `PST-1234-5678` | 8 digits (the `PST` prefix is optional when typed) |
| `pst_sk` | Saskatchewan PST | digits | digits | 6–10 digits (no published check digit) |
| `rst_mb` | Manitoba RST | digits | digits | 6–10 digits (no published check digit) |

Input is forgiving (spaces, dashes, lower case). Other fields: `effective_from` / `effective_to`
(either may be open; the end is never before the start — also a database check),
`status` (`pending` "Applied for", `active` "Registered", `closed` "Closed") and
`cra_approval_ref` (the reference of the CRA or Revenu Québec approval letter).

Rules (`TaxRegistration.clean`, codes `orgsettings.registration.*`):

- **One BN at a time**: Business Number periods may not overlap; the same program account (same
  number) may not be registered twice for overlapping dates — several RT accounts (RT0001, RT0002
  for a branch that files separately) are fine (`overlap`).
- **Program accounts carry the organisation's BN**: an RT/RP/RC number must start with the BN
  registered for the same dates, and a BN must match the program accounts already there
  (`bn_mismatch`).
- A soft-deleted registration no longer blocks anything.
- **Attribution**: every change is in the audit log (`orgsettings.taxregistration.*`) with old →
  new values and the person or `System: <job>` who made it — no silent "GST Type – removed"
  (gap-44).
- Not here yet: "a Quebec organisation needs a QST number" is a prompt on the registrations page
  (A-05-T12) and an exceptions-engine rule (K-09), not a save rule.

## Lock dates (A-05-T04)

Xero has two lock dates for the whole file (both empty in the teardown organisation). Numo9 has
**one lock per module and level** — `LockDate(module, level, date, reason)`, one row per
organisation, module and level (`orgsettings_lock_one_per_module_level`):

| Module (`module`) | Covers |
|---|---|
| `gl` General ledger | Manual journals and every posting to the ledger |
| `ar` Sales and accounts receivable | Invoices, credit notes, customer payments |
| `ap` Purchases and accounts payable | Bills, supplier credits, supplier payments |
| `bank` Bank | Bank transactions, transfers, reconciliation |
| `payroll` Payroll | Pay runs and payroll journals |
| `tax` Sales tax | GST/HST, QST and PST returns (set when a return is filed, G-03-T07) |

| Level (`level`) | Stops |
|---|---|
| `advisers_only` "Everyone except advisers" | Everyone but the advisers — accountants of an assigned practice (A-03) |
| `everyone` "Everyone" | Advisers too |

So "AP locked, GL open" or "locked for the client at 30 June, for the accountant at 31 March" are
both one row each. Rules (codes `orgsettings.lock.*`):

- `date` empty = not locked at that level. Changes dated **on or before** the date are refused —
  the lock service (A-05-T05) applies it in the organisation's time zone.
- **Moving a lock back needs a reason** (`reason_required`): an earlier date, or removing it,
  reopens closed periods. `set_lock(date, reason)` sets both for one change.
- **Levels in order** (`levels_out_of_order`): the everyone date is never later than the
  advisers-only date of the same module — an adviser is never locked out of more than the client.
- Module and level of a row never change (`immutable`): set another lock instead.
- **History via audit**: every change is an `orgsettings.lockdate.created` / `.updated` event with
  old → new `date` and `reason` and its author or `System: <job>`; the record history drawer
  (A-04-T10) reads it (`object_type = orgsettings.LockDate`, `object_id` = the lock's public id).
