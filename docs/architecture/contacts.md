# Contacts (B-01)

| | |
|---|---|
| **Deliverable** | B-01 · Contact model, Phase 0 (component B — Contacts) |
| **Branch** | `feature/B-01-contact-model` |
| **Code** | `backend/numo9/contacts/` (models, validators, fields, tax, custom_fields, duplicates, exemptions, tasks); `frontend/src/contacts/` (API client, live duplicate panel) |
| **Depends on** | A-01 (tenancy: `OrgOwnedModel`, row-level security), A-04 (audit: `AuditedModel`), A-05 (numbering, address validators), A-06 (certificate files), A-08 (reminder job) |
| **Used by** | D sales and E purchases (customer/supplier, defaults, credit check), G-02 tax engine (province tax hint), B-02 statements, B-03 import/export, M payroll (employee role), R-01 currencies |
| **Gaps** | gap-19 (explicit roles, titled lists), gap-20 (currency, terms master, withholding flag, exemption certificate, duplicate warning, credit warn/block), gap-39 (Province / Postal code), gap-43 (custom fields) |
| **Wireframes** | [Phase 0 wireframes §11–13](../design/wireframes.md#11-contacts-list-with-role-tabs-b-01-t01) |

What Xero ships (xero_teardown §3.1, §3.2): the Customers and Suppliers pages are the same generic
"Contacts" page; the role is inferred from transactions, so a new contact is in neither list. The
contact has no currency, no payment-terms master, no withholding/T4A flag, no exemption
certificate, no duplicate warning and only "block" for the credit limit.

## Contact (B-01-T02)

`Contact` is one model for everyone the organisation deals with. It is an organisation record
(`OrgOwnedModel`: scoped to the active organisation, public UUID) with every change audited
(`AuditedModel`), and its table has PostgreSQL row-level security (`EnableOrgRLS`, A-01-T12).

| Field | Type | Rule |
|---|---|---|
| `number` | text ≤ 20 | Unique per organisation, case-insensitive (`contacts_contact_number_unique_per_org`). Empty → the next number of the organisation's `contact` sequence (`C-0001`, A-05-T08); a number already typed by hand is skipped |
| `display_name` | text ≤ 200 | Required; spaces tidied |
| `legal_name` | text ≤ 200 | Printed on statements and slips (`printed_name` falls back to the display name); never digits only (`orgsettings.legal_name.numeric`, gap-55) |
| `roles` | array of text | At least one of `customer`, `supplier`, `employee`, `contractor`, `government_agency`; each once, stored in that order. A customer that is also a supplier has both |
| `bn` | 9 digits | CRA Business Number with its check digit; `123 456 782` and a program account `123456782 RT 0001` are stored as `123456782` |
| `tax_id` | text ≤ 40 | Any other tax number printed on documents (a foreign registration number…) |
| `currency` | ISO 4217 | `CAD` by default (gap-20); typed in any case |
| `credit_limit` | decimal(18, 2) | Empty = no limit; never negative |
| `credit_mode` | `warn` · `block` | `warn` by default; `block` needs an override approval (B-01-T13) |
| `t4a_flag` | boolean | Payments are reported on T4A slips (withholding flag) |
| `portal_enabled` | boolean | Client portal access |
| `statement_pref` | `none` · `email` · `post` · `portal` | `email` by default |
| `language` | `en-ca` · `fr-ca` | Language of the contact's documents and emails |
| `status` | `active` · `archived` | Archiving is the contact's "delete": history kept, restorable (`archive()` / `unarchive()`). `deleted_at` is reserved for merged contacts (B-01-T12) |

`save()` tidies the input, then reports **every** problem at once as a `ValidationError` keyed by
field with stable codes:

| Code | When |
|---|---|
| `contacts.roles.required` | No role |
| `contacts.roles.invalid` | A role outside the list (the message names it) |
| `contacts.number.taken` | The number is used by another contact of the organisation |
| `contacts.bn.format` / `contacts.bn.check_digit` | Not 9 digits / wrong check digit |
| `contacts.currency.invalid` | Not an active ISO 4217 code |

The database repeats the rules that matter: number unique and not empty, display name not empty,
roles valid (`contacts_contact_roles_valid`, array operators — PostgreSQL only), currency three
capital letters, credit limit ≥ 0, valid choices. The roles column is a PostgreSQL array
(`PortableArrayField`); a throw-away SQLite database (the security-header CI job) creates it as
text and skips the array constraint, as the audit and packages migrations do.

Lists filter by role in the database: `Contact.objects.filter(roles__contains=["customer"])`.

## People (B-01-T03)

`ContactPerson` — the people at a contact (`contact.people`), as many as needed: there is no limit
(Xero's add-contact form stops at a few). Business record (`OrgOwnedModel`, `AuditedModel`); the
table has row-level security because it holds email addresses and telephone numbers.

| Field | Rule |
|---|---|
| `first_name`, `last_name`, `job_title` | Spaces tidied; a person needs a name or an email (`contacts.person.name_or_email`, also a database check) |
| `email` | Valid address, stored in lower case |
| `phone` | Parsed as Canadian unless it starts with `+`, stored as E.164 (`orgsettings.phone.invalid` — the A-05-T02 rule) |
| `is_primary` | Exactly one primary person per contact with people (database: at most one, `contacts_person_one_primary`) |
| `include_in_emails` | On by default: the person is copied on emails of invoices, statements and other documents |

Primary person rules, applied under a row lock on the contact so two people can't race:

- the first person of a contact becomes primary (also when saved with `is_primary=False`);
- saving a person with `is_primary=True` (or `make_primary()`) unmarks the previous primary person
  in the same transaction;
- removing (`soft_delete()`) or unmarking the primary person promotes the earliest remaining
  person;
- every flag change is an audit event of the person it changes.

A person always belongs to the contact's organisation (`contacts.person.contact`).

## Addresses (B-01-T04)

`Address` — a contact's billing and shipping address (`contact.addresses`), at most one of each
among addresses not removed (`contacts_address_one_per_kind`). Business record, audited, with
row-level security. The words are Canadian everywhere — Province, Postal code — never "State" and
"ZIP" (gap-39).

| Field | Canada (`country="CA"`, default) | Other countries |
|---|---|---|
| `kind` | `billing` · `shipping` | same |
| `attention`, `line1`, `line2`, `city` | Spaces tidied | same |
| `province` | One of the 13 two-letter codes AB, BC, MB, NB, NL, NS, NT, NU, ON, PE, QC, SK, YT (`orgsettings.province.invalid`; database check `contacts_address_province_valid`) | Must stay empty (`contacts.address.province_outside_canada`) |
| `region` | Emptied | Free text (region, county…) |
| `postal_code` | Canada Post `A1A 1A1`: `m5v2t6`, ` M5V  2T6 `, `m5v-2t6` → `M5V 2T6`; `12345` refused (`orgsettings.postal_code.invalid`); first letter must belong to the province (`orgsettings.postal_code.province_mismatch`) | Free text (`10118`) |
| `country` | `CA` | ISO 3166-1 alpha-2, any case (`orgsettings.country.invalid`) |

The Canadian validators are the organisation-settings ones (A-05-T02,
`numo9.orgsettings.validators`), so a postal code is checked the same way everywhere. Province and
postal code may be empty (a partial address is allowed; the tax engine flags a missing province,
G-02-T03). `lines()` gives the printed form — `Toronto ON M5V 2T6`, and the country code on a
foreign address. An address always belongs to its contact's organisation
(`contacts.address.contact`); a second address of the same kind is refused
(`contacts.address.kind_taken`).

## Province tax hint (B-01-T07)

A contact's default tax follows its province (`TAX_DEFAULT_BASIS = "province"`):
`numo9.contacts.tax` names the sales-tax regime of the province, and the tax engine (G-02) resolves
it to the organisation's tax codes and applies place-of-supply rules (ship-to province, services,
exports). The hint is derived, never stored: changing the address changes it at once.

```python
province_tax_hint("QC").code   # "GST+QST"
province_tax_hint("ON").code   # "HST13"
contact.province_tax_hint      # from the billing address, else the shipping address
contact_tax_hint(contact, on=date(2026, 11, 14))
```

| Province / territory | Code | Taxes (general rates) | Combined |
|---|---|---|---|
| AB, NT, NU, YT | `GST` | GST 5 % | 5 % |
| ON | `HST13` | HST 13 % | 13 % |
| NS | `HST14` (from 1 April 2025; `HST15` before) | HST 14 % | 14 % |
| NB, NL, PE | `HST15` | HST 15 % | 15 % |
| BC | `GST+PST` | GST 5 % + PST 7 % | 12 % |
| SK | `GST+PST` | GST 5 % + PST 6 % | 11 % |
| MB | `GST+RST` | GST 5 % + RST 7 % | 12 % |
| QC | `GST+QST` | GST 5 % + QST 9.975 % | 14.975 % |

`ProvinceTaxHint` carries `province`, `regime` (`gst`, `hst`, `gst_pst`, `gst_qst`), `code`,
`components` (name, rate, authority), `effective_from`, `combined_rate` and `label`
(`GST 5 % + QST 9.975 %`, shown next to the address). Each row has the date it took effect; a rate
change is a new row (Nova Scotia's HST: 15 % → 14 % on 1 April 2025), so a document dated before
the change gets the old regime. An unknown code, a date before the table, a foreign address or a
Canadian address without a province give `None` (G-02 flags `missing_province` or applies export
rules). Rates checked against the CRA GST/HST rates table and the provincial authorities
(October 2026).

## Custom fields (B-01-T09)

An organisation adds its own fields to contacts (gap-43): `CustomFieldDefinition` (Settings →
Custom fields, `/o/:org/settings/custom-fields`) and one JSONB column on the record,
`Contact.custom_fields` (`{"industry": "construction", "employees": "12"}`), checked against the
definitions on every save (`numo9.contacts.custom_fields.clean_custom_values`).

**Definitions** — business records (`OrgOwnedModel`, audited):

| Field | Rule |
|---|---|
| `record_type` | `contact` (later modules add theirs) |
| `key` | Lower-case letters, digits, `_`, starting with a letter, ≤ 40 (`contacts.custom_field.key_format`); unique per organisation and record type, also after removal (`contacts.custom_field.key_taken`); never changes (`contacts.custom_field.key_locked`) |
| `label_i18n` | `{"en-ca": …, "fr-ca": …}`; English required (`contacts.custom_field.label_required`), ≤ 100 characters; French falls back to English until Phase 6 (X-02-T44 warns at send time) |
| `field_type` | `text`, `number`, `date`, `select`; locked once a record has a value (`contacts.custom_field.type_locked`) |
| `options` | Choice list only: 1–100 choices `{"value", "labels": {"en-ca", "fr-ca"}}`, values unique; emptied for other types |
| `required`, `position` | Required on new records; order on the form |

At most **30** fields per record type among fields not removed (`contacts.custom_field.limit`).
Removing a field is a soft delete.

**Values** — errors are keyed `custom_fields.<key>` and name the field:

| Type | Accepted | Stored as | Refused (`contacts.custom_field.type_mismatch`) |
|---|---|---|---|
| `text` | text ≤ 500 characters (`.too_long` beyond) | spaces tidied | numbers, lists, objects |
| `number` | number or numeric text (`1,250.50`) up to 18 digits | exact decimal string `"1250.50"` (no binary rounding) | `"twelve"`, `true`, lists |
| `date` | `YYYY-MM-DD` or a date | ISO string | `2026-02-30`, `14/11/2026`, numbers |
| `select` | one of the choice values | the value | anything else |

- An unknown key is refused (`contacts.custom_field.unknown`); an empty value removes the key.
- A required field must be filled on a new record and can't be emptied later
  (`contacts.custom_field.required`); a required field added later doesn't block older records.
- Only changed values are checked: a value kept as it was stays valid after its choice was removed
  or its field deleted (settings changes never rewrite history); a removed field takes no new value
  (`contacts.custom_field.removed`).
- Value changes are in the contact's audit diff (`custom_fields: [old, new]`).

## Duplicate detection (B-01-T10)

`numo9.contacts.duplicates.find_duplicates(name=, email=, bn=, tax_id=, exclude=, limit=10)`
returns the possible duplicates of what is being typed, in the active organisation, as
`DuplicateMatch(contact, reasons, similarity)`. The contact form's live panel (B-01-T16) and the
`/duplicates?q=` API (B-01-T11) call it.

| Reason | Matches when |
|---|---|
| `name` | Trigram similarity (`pg_trgm`) of the **name keys** ≥ 0.6. Names under 3 characters are not compared |
| `email` | A person of the contact (not removed) has the address, any case |
| `bn` | Same Business Number (`123 456 782` = `123456782 RT 0001`) |
| `tax_id` | Same tax ID ignoring case, spaces, hyphens, dots and slashes |

The **name key** (`Contact.name_key`, set on every save, not audited) is the display name in lower
case, without accents (`Érable` = `erable`), punctuation, a leading "The" or trailing company forms
(Ltd., Limited, Inc., Corp., Co., LLC, LLP, LP, PLC, Ltée, Limitée, Enr., S.E.N.C., S.R.L.,
Cie): `Maple Supply Ltd.` → `maple supply`, so "Maple Suply" (0.79) finds it. The search uses
pg_trgm's `%` operator on the GIN index `contacts_contact_name_trgm_idx` and keeps similarity ≥ 0.6.

- **A warning, never a block**: two contacts with the same name in different provinces are both
  allowed; the match carries the contact, so the panel shows its province and number.
- Merged contacts (`deleted_at`) are never listed; archived ones are (`contact.is_archived`).
- `exclude` leaves out the contact being edited.
- Order: exact matches first (more exact reasons first), then name similarity; reasons are listed
  BN, tax ID, email, name.

## Live duplicate panel (B-01-T16)

`frontend/src/contacts/DuplicatePanel.tsx` — the "Possible duplicates" panel of the contact form
(wireframe 13, marker 4). `LiveDuplicatePanel({org, query: {name, email, bn, taxId, exclude},
onMerge})` is what the contact form (B-01-T15) mounts next to the Details section.

- **Debounced** (`useDuplicateCheck`, 250 ms after the last keystroke): one request per pause with
  the latest text; an answer that arrives late for older text is dropped; the previous results
  stay on screen while the next check runs. The panel appears within 300 ms after typing stops
  (unit test with real timers).
- Nothing is asked for a name under 3 characters, an incomplete email, a BN under 9 digits or a
  tax ID under 3 characters (`isCheckable`); the panel clears.
- Each row: name, contact number, province ("No province" when none), Archived badge, the reasons
  (Business Number matches · Tax ID matches · Email address matches · Name 79% similar) and
  **Open** (`/o/:org/contacts/:id`), **Merge…** (shown once the merge dialog, B-01-T17, passes
  `onMerge`), **Ignore** (hides that contact for this form).
- A warning, never a block; a failed check shows nothing and the form stays usable.
- Accessibility: a `section` labelled by its heading; the count is announced once through a polite
  `role="status"` that changes only when the count changes; links and buttons carry the contact's
  name in their accessible names ("Open Maple Supply Ltd."); axe: no violations.

API contract (served by B-01-T11):
`GET /api/v1/o/<org>/contacts/duplicates?q=<name>&email=&bn=&tax_id=&exclude=<contact id>` →
`{"results": [{"contact": {"id", "number", "display_name", "province", "roles", "archived"},
"reasons": ["bn", "name"], "similarity": 0.79}]}`.

## Payment terms master (B-01-T05)

`PaymentTerm` — the organisation's list of payment terms (gap-20: Xero has no terms master, terms
are typed per contact). Contacts (B-01-T06), invoices and bills pick a term from the list.
Business record (`OrgOwnedModel`, audited).

| Field | Rule |
|---|---|
| `name_i18n` | Name per language; English required (`contacts.payment_term.name_required`), unique in the organisation (`contacts.payment_term.name_taken`) |
| `terms_type`, `days` | The organisation-settings term types (A-05): *n* days after the document date, *n* days after the end of the document month, the *n*th of the following month, the *n*th of the current month. 0–365 days (`contacts.payment_term.days`), or a day 1–31 for the "of the month" types (`contacts.payment_term.day`) |
| `discount_pct`, `discount_days` | Early-payment discount (applied by E-07): 0–99.99 % (`.discount_range`); with a discount, a window ≥ 1 day (`.discount_days_required`) that ends before a days-after-document term is due (`.discount_window`); without one, the window is cleared |
| `late_interest_pct` | Annual late interest 0–100 % (`.interest_range`); FN-04 adds how it is charged |
| `code` | Stable key of a seeded term (`net_30`), unique per organisation; empty for terms people add |
| `status`, `position` | Active or archived (terms are archived, never deleted); order in pickers |

The database repeats the ranges (`contacts_payment_term_*` checks).

**Defaults** — every new organisation gets them (a `post_save` receiver on `Organisation`;
migration `contacts.0005` seeds organisations created before it); `seed_payment_terms(org)` adds
only the missing codes, so it is safe to run again. The seed is one platform bulk insert without
audit events (part of creating the organisation); later changes are audited.

| Code | Name | Rule |
|---|---|---|
| `due_on_receipt` | Due on receipt | 0 days after the document date |
| `net_15` / `net_30` / `net_60` | Net 15 / Net 30 / Net 60 | 15 / 30 / 60 days after |
| `2_10_net_30` | 2/10 net 30 | 30 days after; 2 % discount within 10 days |
| `eom` | End of month (EOM) | 0 days after the end of the document month |

## Exemption certificates (B-01-T08)

`ExemptionCertificate` — a sales-tax exemption certificate a contact gave the organisation (gap-20:
Xero keeps none on the contact; a PST or QST exemption is a tax rate and the paper lives elsewhere).
Business record (`OrgOwnedModel`, audited); a contact may hold several (one per number).

| Field | Rule |
|---|---|
| `contact` | The contact of this organisation that holds it (`contacts.exemption.contact`) |
| `number` | Required (`contacts.exemption.number_required`); spaces collapsed; unique on the contact, case-insensitive, among certificates not removed (`contacts.exemption.number_taken`, constraint `contacts_exemption_number_unique`) |
| `document` | The scanned certificate — a document of the organisation's file store (A-06): never another organisation's (`contacts.exemption.document`), a deleted one (`.document_deleted`) or a quarantined one (`.document_quarantined`). A document with a certificate can't be hard-deleted (`PROTECT`) |
| `issued_on`, `expires_on` | Optional; empty `expires_on` = no expiry date. The expiry is never before the issue date (`contacts.exemption.expiry_before_issue`, check `contacts_exemption_dates_valid`) |
| `notes` | Free text, 500 characters |
| `reminded_state`, `reminded_for` | Bookkeeping of the reminder job (not editable, not audited) |

**State** — `certificate.state(on)` is `valid`, `expiring` (expiry date within 30 days,
`EXEMPTION_REMINDER_DAYS`) or `expired`: a certificate is valid through its expiry date and
**flagged expired from the next day**, in the organisation's time zone (`organisation_today(org)`),
not the server's. `is_expired()` and `days_left()` (negative once expired) read the same date. The
tax engine (G-02) stops applying an expired certificate; the contact form (B-01-T15) shows the flag.

**Expiry reminder hook** — the daily platform job `numo9.contacts.exemption_reminders`
(`contacts/tasks.py`, beat 11:23 UTC) calls `numo9.contacts.exemptions.send_reminders()`:

- every certificate not removed (nor its contact) whose expiry date is 30 days away or past gets a
  reminder: `expiring` 30 days before, then `expired` once it has expired — each **once** per
  expiry date (running the job again the same day sends nothing). A certificate entered already
  expired gets only the `expired` reminder;
- the hook is `settings.NUMO9_EXEMPTION_REMINDER_HOOK` — `hook(certificate, state, days_left)`,
  called inside the certificate's organisation context. Until notifications ship (A-07) the
  default (`exemptions.log_reminder`) writes the structured log line `contacts.exemption.reminder`
  with ids only (no names);
- renewing a certificate (a new expiry date, or none) clears the bookkeeping, so the reminders
  start again for the new date.

## Credit limit check (B-01-T13, gap-20)

`numo9/contacts/credit.py` — Xero only has "Block new invoices when credit limit is reached" and
no way past it but clearing the box. Numo9's documents (D sales invoices, E sales orders) call

```python
check = assert_credit(contact, total, user=request.user, document_type="invoice",
                      document_ref=str(invoice.public_id))   # in the saving transaction
```

| Contact | Exposure + document total | Result |
|---|---|---|
| no limit | any | `no_limit` — saved |
| any mode | ≤ limit | `within` — saved |
| `warn` | > limit | `warn` — saved; `check.message` is the warning the screen shows ("This takes Maple Leaf Supplies to $5,200.00, $200.00 over its credit limit of $5,000.00.") |
| `block` | > limit, approved override for this document and amount | `override` — saved; the override is marked **used** |
| `block` | > limit, no approved override | `CreditLimitBlocked`: `409 contact.credit_limit_blocked`, body `amount`, `exposure`, `limit`, `over_by`, `approvers` |

- **Exposure** (what the contact owes) is the sum of the sources modules register with
  `register_exposure(key, source)` — `source(contact, *, exclude)` returns the open amount in the
  contact's currency, leaving out `exclude` (the document being revised, so it is not counted
  twice). Phase 0 has no source yet: D-01 (invoices) and E-02 (sales orders) add theirs.
- **Override** (`CreditOverride`): `request_override(contact, amount, user=…, reason=…,
  document_type=…, document_ref=…)` — a reason is required (`contact.credit_override_reason`);
  refused when nobody can approve (`contact.credit_override_no_approver`); everyone who can is
  notified (`contacts.credit_override_requested`, category *Approvals*).
- **Approver**: holds `contacts.credit_limit.override` (risk *critical*: owners, admins and
  practice admins by default; a custom role can grant it) and is **never the requester**
  (`approval.self_approval`, A-03-T08). `approve_override` / `reject_override` (note optional)
  tell the requester (`contacts.credit_override_approved` / `_rejected`). A decided request
  can't be decided again (`contact.credit_override_decided`).
- An approval covers **one document type and document, up to the amount asked**, and is used
  once. A request or an unused approval **expires after 7 days** (`CREDIT_OVERRIDE_DAYS`;
  `contact.credit_override_expired`).
- Every override is audited (`AuditedModel`); amounts are `Decimal` (a float or a negative amount
  is a programming error).

## Gap tests (B-01-T19)

`tests/test_contacts_gaps.py`, marked `@pytest.mark.gap(...)` (CI job `gap-tests`):

| Gap | Observed |
|---|---|
| gap-19 | A new contact is in its role's list before any transaction; roles are set on the contact and a contact can have several (customer + supplier); no role is refused; archived contacts leave the role lists. The titled list tabs are B-01-T14's Playwright check |
| gap-20 | Contact currency (CAD default, USD…); payment-terms master (B-01-T05); T4A withholding flag; credit limit warn or block; duplicates found while typing by name, BN and tax ID; Quebec contact → GST + QST; exemption certificate on the contact (number, file, expiry), flagged the day after it expires (B-01-T08). The credit override approval is `test_contacts_credit.py::test_block_mode_requires_an_approver` (B-01-T13) |

Fixture `tests/fixtures/contacts_ca/contacts.json`: one customer per province and territory with
its billing address and the tax hint it defaults to (as of 14 November 2026) — the Quebec
customer, Érable Distribution inc., defaults to GST + QST (deliverable acceptance).

## Tests

| Task | Tests |
|---|---|
| T02 | `tests/test_contacts_model.py` |
| T03 | `tests/test_contacts_people.py` |
| T04 | `tests/test_contacts_address.py` |
| T05 | `tests/test_contacts_payment_terms.py` |
| T07 | `tests/test_contacts_tax_hint.py` |
| T08 | `tests/test_contacts_exemptions.py` |
| T09 | `tests/test_contacts_custom_fields.py` |
| T10 | `tests/test_contacts_duplicates.py` |
| T13 | `tests/test_contacts_credit.py` |
| T16 | `frontend/src/contacts/DuplicatePanel.test.tsx` |
| T19 | `tests/test_contacts_gaps.py` (+ `tests/fixtures/contacts_ca/contacts.json`) |

## Statements — the PDF (B-02-T05)

`numo9.contacts.statements` — `StatementDocument` is what the statement engine (B-02-T04)
produces: issuer and contact (`Party`), kind, issue date, *as at* (or the period end), the lines
with running balances, the aging buckets and the amount due, in the **contact's currency**.
`render_statement_pdf(document, locale=…)` renders `contacts/statement.html` on the A-10 document
baseline (`documents/base.html`): Letter 8.5 × 11 in, 1 in margins, brand header with the issuer,
page counter; English or French (`en-ca` / `fr-ca` keys in the backend catalogues).

| Kind | Shows |
|---|---|
| `outstanding` | the open items as at a date: date, document, due date, amount, running balance; aging buckets Current / 1–30 / 31–60 / 61–90 / over 90 days past due (`aging_of`: days past due at the as-at date; no due date = current); amount due |
| `activity` | a period: opening balance, then every document and payment with its description and running balance; closing balance = amount due |

`sample_statement(kind)` is the Canadian fixture in the engine's shape. Tests:
`backend/tests/test_contacts_statement_pdf.py` — text snapshots of the four renderings
(`tests/snapshots/statements/<kind>.<locale>.txt`, `NUMO9_UPDATE_SNAPSHOTS=1` to rewrite), Letter
page with content inside the margins, aging totals = amount due, activity opening + lines = closing.

## Statements — sending and history (B-02-T06)

`statements.send_statement(contact, document, to=None, language=None, user=None)`:

1. recipients — `to`, or the contact's people marked *include in emails* that have an address
   (primary first); nobody → `StatementError`;
2. the PDF is rendered in the contact's language (or `language`) and stored in the
   organisation's object storage (A-06 key `org/<id>/…/statement-<number>-<date>.pdf`);
3. one email per recipient through the A-07 message log (`queue_email`, kind
   `contacts.statement`, template `email/statement` EN/FR) with the PDF as an **attachment** —
   `EmailMessage.attachments` holds `{"key", "filename", "content_type"}` and the worker reads
   the file when it sends; a key outside the message's organisation is a permanent failure,
   never sent;
4. `contacts.StatementSend` — the history row: kind, as-at / period start, amount due, currency,
   language, recipients, subject, the stored file, the email messages' ids, who and when;
5. audit `contacts.statement.sent`, and the signal `statement_sent(send=row)` — the activity
   timeline (B-02-T02) records the statement from it.

All in the caller's transaction: the emails leave only when it commits.
`backend/tests/test_contacts_statement_send.py`.
