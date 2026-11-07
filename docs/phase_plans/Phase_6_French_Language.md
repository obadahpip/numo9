# NUMO9 — Phase 6 Implementation Plan: French Language (fr-CA)

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 6 — French Language |
| **Weeks** | Week 9 (runs alongside Hypercare 1) |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1.6 #16, §1.7 (Language), §1.8 #10, §3 Component X, §4 Gaps #42, #43, #61, §5.2, §5.3 rule 5, §6.1 (Localisation) · Project_Phases.md (Phase 6) · Quotation GMA-PFX-2026-003 §4 "French Language" · Agreement GMA-PFX-2026-003-A §06, 9.1(e) · xero_teardown.md §6.5, §6.6–6.7, §10.B · AI Coding Agent — Mandatory Engineering Workflow |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE, applied to the phase, to every deliverable branch and to every atomic task |

---

## 0. How to use this file

- One Git branch per deliverable (`feature/X-01-i18n-infrastructure`, `feature/X-02-french-ui-documents`, `feature/X-03-bilingual-website-portal`). X-02 is large and is delivered as stacked sub-branches per screen group (`feature/X-02a-…`) merged into its deliverable branch.
- Every atomic task (`X-0n-Tnn`) is worked UNDERSTAND → PLAN → BUILD → TEST → IMPROVE on its own; dependent tasks never start before their prerequisite's acceptance is observed.
- Since Phase 0 every screen ships with EN and FR keys (Plan §5.3 rule 5); this phase fills, reviews and verifies the French values, completes locale formatting, and makes every document and email bilingual.
- Nothing is complete until its acceptance criteria are observed on staging and the client's French glossary reviewer has signed off (Agreement 9.1(e)).

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

| Area | State at start of Phase 6 |
|---|---|
| Frontend (Next.js 15) | Every screen built from the A-10 design system; all strings referenced by ICU message keys in `frontend/locales/en-CA/*.json`; `fr-CA` catalogue exists with keys only (values empty or copied EN marked `⚠`). A-10 lint rule rejects hard-coded strings. |
| Backend (Django 5 / DRF) | API error messages, validation messages, enum labels and email subjects use `gettext_lazy`; `backend/locale/fr_CA/LC_MESSAGES/django.po` generated but untranslated. |
| Users/organisations | `User.locale` and `Organisation.default_locale` fields may exist from A-02/A-05 as nullable; not yet applied to formatting everywhere. |
| Contacts | B-01 contact model; `Contact.document_language` either absent or not wired to documents. |
| Documents | WeasyPrint/Chromium PDF templates (invoice + revision stamp D-03b, credit note D-06, statement B-02/D-07, quote D-02, PO E-01, remittance advice E-06, pay stub N-05, T4/T4A/T5 cover N-08, PD7A-style remittance summary N-07, GST/HST & QST worksheets G-03/G-04, tax reports G-05, loan schedules FN-02/FN-05, two-book statements K-08) in English only. |
| Emails | A-07 branded templates with EN variants; FR variants stubbed. |
| Website | Q-01…Q-04 English pages on Next.js ISR + Django CMS; no hreflang. |
| Portal | O-05 client portal English only. |
| Mobile | Y-01 in progress (Phase 7) consumes the same catalogues — Phase 6 output is its input. |
| CI | S-01 i18n extraction job runs; missing-key gate is in "report-only" mode. |

### 1.2 Problem definition — the seven questions

1. **Who uses this?** French-speaking accountants (Quebec, New Brunswick, Ontario francophone practices), French-speaking organisation owners/users and employees, Quebec customers/suppliers who receive documents, public website visitors, the client's French glossary reviewer, the Platform Owner (CMS FR content).
2. **Desired outcome:** any user can work fully in French; any document or email is produced in the recipient contact's language regardless of the sender's UI language; the website and portal are bilingual with correct SEO; formats follow fr-CA (`1 234,56 $`, `2026-11-07`, `7 novembre 2026`, 24-h time `16 h 33`).
3. **Inputs:** EN catalogues (frontend, backend, emails, PDFs, CMS), CRA/Revenu Québec official French terminology, client glossary decisions, user/org/contact locale settings, CMS FR page content.
4. **Outputs:** complete `fr-CA` catalogues (0 missing keys), locale-aware formatting library, French PDFs/emails/SMS, bilingual website with hreflang/sitemaps, portal language per user, approved glossary (`docs/i18n/glossary_fr-CA.md` + machine-readable TBX/CSV), missing-key and pseudo-localisation reports.
5. **Business rules:** locale precedence for UI = user setting → organisation default → browser `Accept-Language` → `en-CA`; for documents/emails to a contact = contact `document_language` → organisation default document language → `en-CA`; legal/statutory labels use CRA/RQ French terms exactly (TPS/TVH, TVQ, CTI/RTI, numéro d'entreprise, RPC/RRQ, AE, RQAP, T4/Relevé 1, état de compte, note de crédit, bon de commande); amounts stored once (no translation of data), only labels and formats change; the revision number (101-1) is never localised; a document's language is frozen at issue and recorded on the document/revision (re-printing reproduces the same language unless explicitly regenerated); missing FR key at runtime falls back to EN and is logged, never shows a raw key; Quebec Charter of the French Language (Bill 96) expectations: documents for Quebec contacts default to French.
6. **What could go wrong:** truncated buttons/table headers (+30 % length); wrong number parsing (comma decimal entered by FR user posting 1 000x amounts); concatenated strings that break grammar/gender; pluralisation errors ("1 factures"); mixed-language PDFs; wrong CRA term (e.g. "taxe de vente harmonisée" vs "TVH" usage); date ambiguity (`07/11/2026`); email subject in EN with FR body; SEO duplicate content without hreflang; translators editing keys directly in code; regression of EN while editing; ICU syntax errors crashing render; currency symbol placement (`$` after amount in fr-CA); sorting/collation of accented names (É vs E); PDF fonts missing glyphs (é, à, ç, «»); non-breaking spaces lost in PDFs/emails.
7. **Smallest useful implementation:** formatting library + locale resolution + French invoice PDF/email for a Quebec contact sent by an EN-UI user. That slice (X-01-T01…T10 + X-02 invoice tasks) is built and verified first.

### 1.3 Restated objective

- **Currently:** Numo9 is English-only at runtime; FR keys exist but are empty; documents and emails print only in English; the website has no French pages.
- **Change:** complete i18n infrastructure, fr-CA formatting, French translations of every screen, email, notification, SMS and PDF with CRA/RQ terminology, per-contact document language, bilingual website (hreflang, localised slugs, sitemaps) and portal language per user.
- **Why:** Canada is bilingual; Quebec clients expect French documents (and the law expects it); Xero offers no per-contact language and no bilingual templates (teardown §6.5, §6.7) — this is a direct differentiator for Profitex in Quebec and francophone markets.
- **Done means:** `fr-CA` missing-key report = 0 on backend, frontend, emails, PDFs, website and mobile catalogues; pseudo-localised (+30 %) visual suite passes with no clipping; a Quebec contact with language FR receives a French invoice (and revision stamp) from an EN-UI user; client glossary approved in writing; Lighthouse SEO ≥ 90 on both locales.

### 1.4 Assumptions & interpretations

1. Locale codes: `en-CA` and `fr-CA` only in this scope; architecture keeps `ar` (RTL) possible later (Gap #61) — logical CSS properties used, no new locale delivered.
2. Initial French values are produced by GMA (professional draft assisted by machine translation + glossary) and reviewed by the client's glossary reviewer; the client's reviewer has final say on terminology.
3. URL strategy for the website: sub-path `/fr/…` with localised slugs (`/fr/tarifs`, `/fr/comptables`); app URLs are not localised (stable deep links).
4. Data entered by users (item names, descriptions, contact names) is not translated; optional bilingual item descriptions (`Item.description_fr`) are included as a refinement of H-01 so FR invoices can print a French line description [EXTRA].
5. Statutory XML (T4, T4A, T5) is language-neutral; only the human-readable cover/summary PDFs are localised. RL-1 is French by nature (Revenu Québec) and printed with FR labels in both locales.
6. Machine translation is used for drafting only, never auto-published.

**Open questions for the client (non-blocking; defaults applied):** preferred terms for "organisation" (default: *organisation*), "package" (default: *forfait*), "founding offer" (default: *offre fondatrice*), "demo" (default: *démo*); whether Quebec contacts default to FR automatically (default: yes).

### 1.5 Client inputs required

| Input | Due | Used by |
|---|---|---|
| Named French glossary reviewer (Agreement 9.1(e)) | Start of week 9 | X-02-T03, T40 |
| Glossary decisions on the open questions above | Day 2 of week 9 | X-02-T02 |
| French website copy approval (or approval of GMA draft) | Day 4 of week 9 | X-03 |
| Sign-off of glossary and translated documents | End of week 9 (5 business days review, Agreement 7.2) | Phase exit |

---

## 2. BETTER THAN XERO — gap analysis for this phase

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 does instead | Observable proof |
|---|---|---|---|---|
| 42 | §6.5 | Emails sent from Xero's domain; 8 standard templates, no per-contact language (no French/Arabic) | Every email template has EN and FR variants; language chosen per recipient contact; sent from the organisation's verified domain (A-07) | `gap-42`: QC contact FR receives FR subject + body from verified domain, DMARC pass |
| 43 | §6.6–6.7 | Three template systems; US Letter with cm margins; NZ sample customer in preview; no bilingual/RTL layout; no custom fields | One PDF template system with locale-aware labels; Letter with inch margins; Canadian sample data (Montréal FR / Toronto EN preview); bilingual layout option (EN/FR side by side) [EXTRA]; custom fields printed with FR labels | `gap-43`: snapshot of FR invoice; preview shows Canadian sample contact |
| 31 / 38 | §5.6, §6 | UK/AU terms ("Value added tax", "annual leave"), spelling flips | Single terminology standard per locale enforced by glossary lint (EN: GST/HST, vacation pay; FR: TPS/TVH, indemnité de vacances) | `gap-31`, `gap-38`: glossary lint passes on both catalogues |
| 44 | §6.8 | "16:33PM" timestamp bug | Locale time formatting via ICU (`16 h 33` fr-CA, `4:33 p.m.` en-CA) | `gap-44-time`: formatter unit tests |
| 61 | §10.B | No clear localisation; MENA/Arabic noted | Complete fr-CA; logical CSS + direction-agnostic layout so a future `ar` locale needs no layout rewrite | pseudo-RTL smoke test passes (report-only) |
| 17 | §2.9 | Quote date format differs from invoice editor | One date formatter per locale across every screen and document | `gap-17-date`: visual regression of both editors in FR and EN |

**Beyond-Xero additions in this phase**
- Per-contact document language with automatic FR default for Quebec addresses.
- Bilingual document option (both languages on one PDF) for federal-government or bilingual customers [EXTRA].
- Language frozen per issued document/revision with "Regenerate in other language" action [EXTRA].
- French pay stubs, T4/T4A/T5 covers, remittance summaries, GST/HST (FPZ-34 equivalent wording) and QST (FPZ-500) worksheets in official terminology.
- Bilingual website with localised slugs, hreflang, FR sitemap and FR structured data.
- In-app language switcher available on every screen (header and user menu), not buried in settings.

**Xero strengths matched conceptually (original design)**
- Live document preview in the template editor — Numo9 adds a language toggle on the preview.

**[EXTRA] refinements inside scope**
- Translator workbench: an internal admin screen listing missing/changed keys with EN source, screenshot context and glossary hints (exported/imported as XLIFF).
- "Changed source" detection: when an EN string changes after its FR translation, the FR value is flagged *needs review*.
- Accent-insensitive search and collation (`Élise` found by `elise`) in global search (A-09) and contact lists.
- French spell-check of user-entered PDF notes using the browser `lang="fr-CA"` attribute.

---

## 3. UI/UX DESIGN PLAN

### 3.1 UX principles applied

1. **Language is a first-class, one-click choice** — switcher in the top bar (`EN | FR`), persists to the user profile, no page reload loss (form drafts kept).
2. **The sender's UI language never decides the recipient's document language** — the contact's language is shown as a chip (`FR`) beside the contact in every document editor, with the effective document language visible before sending.
3. **No surprise mixed languages** — a document is entirely in one language (or explicitly bilingual); untranslated custom fields show a warning before send.
4. **Design for +30 % text** — buttons use min-width and wrap-safe labels; table headers truncate with tooltip, never clip; icons paired with labels; no fixed-width text containers.
5. **Locale-correct input** — amount fields accept `1 234,56` and `1234.56` in fr-CA (parse both, display fr-CA); date pickers show localised month names; placeholders demonstrate the format.
6. **Typography** — Inter/Noto Sans with full Latin-1 + French punctuation; non-breaking spaces before `:`, `;`, `!`, `?`, `»` and inside `« »` and between number and `$` in fr-CA.
7. **Accessibility** — `lang` attribute on `<html>` and on any mixed-language fragment; screen readers pronounce French correctly; WCAG 2.1 AA in both locales.
8. **Consistency** — one glossary drives every surface (app, PDF, email, SMS, website, mobile).
9. **Fallback is invisible to users but visible to us** — missing key renders EN text (never a raw key) and is logged to Sentry with key name.

### 3.2 Information architecture / navigation added

- Top bar: language switcher (`EN / FR`) next to notifications.
- User menu → Profile → *Language and region* (UI language, date format preview, number format preview).
- Organisation settings → *Documents and language*: default UI language for new users, default document language, "Quebec contacts default to French" toggle, bilingual documents toggle.
- Contact editor → *Communication* section: document language (EN / FR / Bilingual), email language.
- Platform console (U-06) → *Translations*: translator workbench, missing-key report, glossary.
- Website: language toggle in header and footer; `/fr/…` routes.
- Portal: language switcher in portal header; per-portal-user preference.

### 3.3 Screen inventory

| Screen | Primary user | Purpose | Key components | States | Keyboard |
|---|---|---|---|---|---|
| Top-bar language switcher | All users | Switch UI language | SegmentedControl, Toast | default / saving / error (revert + toast) | `Alt+L` toggles |
| Profile › Language and region | All users | Persistent preference + format preview | Select, FormatPreview card | loaded / saved / validation | Tab order standard |
| Org settings › Documents and language | Org Admin, Accountant | Defaults for docs and users | RadioGroup, Toggle, LivePreview (PDF thumbnail) | read-only (no permission) / gated (n/a — free) / saved | `Ctrl+S` save |
| Contact editor › Communication | Sales/AP users | Contact's document + email language | Select with flag-free labels ("Français (Canada)") | auto-suggested FR for QC address (dismissible hint) | — |
| Document editors (invoice/quote/PO/credit note/bill) header | All doc users | Show effective document language | LanguageChip, Popover "Change for this document" | warning when custom fields untranslated | `Alt+Shift+L` opens popover |
| Document preview modal | All doc users | Preview PDF in EN/FR | PDFViewer, Toggle | loading skeleton / render error with retry | `←/→` toggle language |
| Email compose dialog | All doc users | Subject/body in recipient language | TemplatePicker, RichText (lang attr) | template missing FR → warn + fall back offer | `Ctrl+Enter` send |
| Platform console › Translations workbench | Platform Owner / GMA translators | Missing/changed keys, edit, import/export XLIFF | DataGrid (virtualised), Diff view, screenshot context | empty ("0 missing keys 🎉" text without emoji) / filtered / conflict | `J/K` next/prev key, `Ctrl+Enter` save |
| Glossary page | Reviewer | Approve terms | DataGrid, status chips (proposed/approved/rejected) | read-only for non-reviewers | — |
| Website header/footer | Public | Switch site language | LinkToggle with hreflang alternate | missing translation page → FR page with notice "Cette page est offerte en anglais seulement" | — |
| Portal header | Client users | Switch portal language | SegmentedControl | — | `Alt+L` |
| Pseudo-locale dev toggle | Developers/QA | `en-XA` pseudo-locale (+30 %, accents, brackets) | Dev-only menu | hidden in prod | — |

### 3.4 Key user flows

1. **EN user invoices a Quebec customer (target ≤ 0 extra clicks):** open New invoice → select contact "Boulangerie Laval" → chip shows `FR` → add lines → Approve & email → email dialog pre-filled in French (subject "Facture 101 de …") → Send. PDF attached in French. Total extra effort vs English: 0 clicks.
2. **User switches UI to French (1 click):** click `FR` in top bar → screen re-renders in < 300 ms, unsaved form preserved, preference saved.
3. **Revise an issued FR invoice:** edit invoice 101 → save creates 101-1 → PDF stamp "Révision 1 de la facture 101 — remplace la version émise le 3 novembre 2026" → email in FR.
4. **Regenerate document in another language (3 clicks):** invoice ⋮ → "Générer dans une autre langue" → choose English → new PDF stored with language recorded; original kept.
5. **Translator fixes missing keys:** console › Translations → filter "missing" → edit inline with EN source + screenshot → save → CI catalogue PR created (or export XLIFF → import).
6. **Visitor lands on `/fr`:** browser `Accept-Language: fr-CA` on `/` → suggestion banner (not forced redirect) "Voir ce site en français ?" → persists choice cookie.
7. **Employee views French pay stub:** employee self-service (M-06) in FR → stub PDF "Talon de paie" with RPC, AE, impôt fédéral/provincial labels.

### 3.5 Microcopy & error-message rules

- Plain language, second person *vous*, sentence case (French typographic rules: no title case), infinitive for buttons (*Enregistrer*, *Envoyer*, *Approuver*).
- Every error names the cause and the fix: EN "This date is before the GL lock date (30 June 2026). Choose a later date or ask an adviser to unlock the period." → FR « Cette date est antérieure à la date de verrouillage du grand livre (30 juin 2026). Choisissez une date ultérieure ou demandez à un conseiller de déverrouiller la période. »
- Amounts in messages use the formatter (`1 017,00 $`), never string concatenation.
- ICU plurals: `{count, plural, one {# facture en retard} other {# factures en retard}}`.
- Gendered agreement handled by full-sentence keys, never by fragments.
- No anglicisms where an OQLF term exists (*courriel*, *téléverser*, *nuage* avoided in favour of context terms; *infonuagique* where needed).
- Statutory labels exact: *TPS/TVH*, *TVQ*, *CTI* (crédit de taxe sur les intrants), *RTI* (remboursement de la taxe sur les intrants), *Numéro d'entreprise (NE)*, *RPC / RPC2*, *RRQ*, *AE*, *RQAP*, *Relevé 1*, *Feuillet T4*, *Sommaire*, *DPA* (déduction pour amortissement) for CCA, *FNACC* for UCC, *Période de déclaration*.

### 3.6 Accessibility & usability test plan

| Usability task (FR participants, n ≥ 5 incl. client staff) | Success metric |
|---|---|
| Switch UI to French and back | 100 % success, < 10 s |
| Create and email a French invoice to a QC contact while UI in English | ≥ 90 % success without help, no mixed-language output |
| Find the GST/HST worksheet in French ("déclaration de TPS/TVH") via global search | ≥ 90 % success, < 20 s |
| Read a French pay stub and identify net pay and RPC deduction | 100 % correct |
| Change a contact's document language | ≥ 90 %, < 30 s |
| Screen reader (NVDA FR voice) reads invoice editor labels in French | 0 pronunciation-language errors on audited screens |
| axe-core in fr-CA on all routes | 0 serious/critical violations |

---

## 4. TOOLS & TECHNOLOGY FOR THIS PHASE

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Frontend i18n | `next-intl` (ICU MessageFormat) | Message lookup, plurals, select, rich text in Next.js App Router | MIT; already chosen in Plan §5.1 (ICU) |
| Frontend formatting | `Intl.NumberFormat`, `Intl.DateTimeFormat`, `Intl.RelativeTimeFormat`, `Intl.Collator`, `Intl.PluralRules` | fr-CA formats, collation | Native; polyfill via `@formatjs/intl-*` for old Safari |
| Number input parsing | Custom `parseLocaleNumber()` + `@internationalized/number` (Adobe) | Accept `1 234,56` and `1234.56` | Apache-2.0 |
| Date pickers | `react-day-picker` with `date-fns/locale/fr-CA` | Localised calendars | MIT |
| Backend i18n | Django `gettext` / `gettext_lazy`, `LocaleMiddleware`, `django-modeltranslation` (CMS/package names only) | API messages, enum labels, translatable platform data | BSD |
| Backend formatting | `babel` (Python) `format_currency`, `format_decimal`, `format_date` | PDFs and emails in fr-CA | BSD |
| ICU on backend | `pyicu` or `babel` MessageFormat via `messageformat`-compatible lib | Same ICU syntax for emails/PDF strings | Shared catalogue format |
| Catalogue format | JSON (ICU) for frontend/mobile, `.po` for Django, XLIFF 2.0 for exchange | Translator interchange | — |
| Extraction | `@formatjs/cli extract`, `django-admin makemessages`, custom script `scripts/i18n/sync_catalogues.py` | CI extraction | — |
| Lint | `eslint-plugin-i18next` / `eslint-plugin-formatjs` (no literal strings, valid ICU), custom `glossary-lint` | Hard-coded strings, ICU validity, term consistency | — |
| Translation management | **Weblate** (self-hosted, GPL) or **Tolgee** (self-hosted) — chosen in X-01-T02 ADR | Translator UI, TM, glossary, screenshots | Self-hosted on GMA infra to keep cost zero; alternative: Crowdin (paid, client cost) |
| Machine draft | DeepL API (client-paid optional) / LLM with glossary prompt | Draft translations only | Never auto-published |
| Terminology sources | CRA French publications, Revenu Québec forms (FPZ-500, RL-1), TERMIUM Plus, OQLF Grand dictionnaire terminologique | Glossary authority | Public |
| Spelling/grammar | LanguageTool (self-hosted server) | QA pass on FR catalogue | LGPL |
| PDF | WeasyPrint (+ Chromium for complex), Jinja2 i18n extension, `hyphens: auto` with `lang="fr"` | French PDFs, hyphenation | Fonts: Inter + Noto Sans (OFL) embedded |
| Email | MJML templates compiled per locale, `django-anymail` | Bilingual emails | — |
| SMS/WhatsApp | Provider templates (Twilio/Meta) in FR | Reminder channel FR variants | Provider fees client-paid |
| Website SEO | Next.js `alternates.languages` (hreflang), `next-sitemap` with locale entries, schema.org JSON-LD `inLanguage` | Bilingual SEO | — |
| Testing | Playwright (locale contexts `fr-CA`), Chromatic/Storybook visual regression with `en-XA` pseudo-locale, Vitest for formatters, pytest + Hypothesis for parse/format round-trip, `pdfplumber` for PDF text assertions, axe-core, Lighthouse CI (both locales) | Verification | — |
| Pseudo-localisation | `@formatjs/cli` pseudo-locale `en-XA` / custom +30 % expander | Layout stress | — |
| Mobile | `i18n-js` / `expo-localization` consuming same JSON catalogues | Phase 7 reuse | — |
| Observability | Sentry tag `missing_i18n_key` | Runtime fallback alerts | — |
| Docs | MkDocs page "Localisation guide", ADR-005 i18n architecture | Handover | — |
| Internal tools to build | `manage.py i18n_report` (missing/stale keys per surface), `manage.py render_all_documents --locale fr-CA` (snapshot every PDF), `scripts/i18n/screenshot_context.ts` (Playwright captures per key for translators), translator workbench in U-06 console, glossary lint, `seed_fr_demo` (FR demo organisation in Montréal) | Phase productivity | — |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 objective
A fully bilingual Numo9 (en-CA / fr-CA): interface, notifications, emails, SMS, PDFs, website and portal, with documents in each recipient's language and 0 missing keys.

### 5.2 Level 2 components

| Component | Deliverables | Purpose |
|---|---|---|
| X — i18n infrastructure | X-01 | Locale model, resolution, formatting, catalogues, CI gates, pseudo-localisation, translator workflow |
| X — French content | X-02 | Glossary; translation of every app screen group, API messages, emails, PDFs; per-contact language |
| X — Public surfaces | X-03 | Bilingual website (Q) and portal (O-05) with SEO |

### 5.3 Dependency graph and execution order

```
X-01 (infra: locale model → resolution → formatters → catalogues → CI gates → pseudo-loc → workbench)
   ├── X-02 glossary (T01–T04) ──► X-02 screen groups (T05–T22, parallel) ──► X-02 documents/emails (T23–T40)
   └── X-03 website (T01–T10) / portal (T11–T13)   [parallel with X-02 after glossary]
Exit demo ◄── all
```

Execution order: 1) X-01-T01…T08; 2) X-02-T01…T04 (glossary) in parallel with X-01-T09…T16; 3) X-02 screen groups and X-03 in parallel; 4) X-02 documents and emails; 5) X-02 review/sign-off; 6) phase test & exit demo.

---

## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

### X-01 · i18n infrastructure

- **Branch:** `feature/X-01-i18n-infrastructure`
- **Objective:** a complete, enforced localisation platform so that every surface resolves a locale, formats values in that locale and never ships a missing key.
- **Current behaviour:** EN catalogues and empty FR keys; locale not resolved consistently; formatting partly hard-coded to en-CA; missing-key gate report-only.
- **Expected behaviour:** locale per user and per organisation with documented precedence; fr-CA formats (`1 234,56 $`, `7 novembre 2026`, `16 h 33`); ICU plurals; extraction in CI; missing-key report blocking merges; layouts hold with +30 % strings; runtime fallback logged.
- **Gap #s closed:** 44 (time format), 61 (i18n ready), 38 (single terminology standard).
- **Business rules:** UI locale precedence user → org default → `Accept-Language` → `en-CA`; document locale precedence contact → org default doc language → `en-CA`; stored amounts and dates are locale-neutral (ISO/decimal); revision numbers, codes, SKUs never localised.
- **Edge cases:** comma-decimal paste from Excel (`1 234,56`), negative amounts (`-1 234,56 $` vs `(1 234,56 $)` in reports), thin vs normal non-breaking space differences between browsers and ICU versions, timezone at period end, ICU syntax errors, sorting `É`.
- **UI/UX notes:** switcher in top bar; profile format preview; pseudo-locale toggle for QA.
- **Dependencies:** A-02 (users), A-05 (org settings), A-10 (design system), S-01 (CI).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| X-01-T01 | Write ADR-005 "i18n architecture": locales, catalogue formats (ICU JSON / .po / XLIFF), precedence rules, URL strategy, fallback policy, RTL-readiness | DOC | — | ADR merged and approved by project lead | Review |
| X-01-T02 | Select and deploy translation management system (Weblate or Tolgee self-hosted) via Docker; connect to repo with bot account | OPS | T01 | TMS reachable on staging subdomain; repo sync PR created by bot | Manual smoke |
| X-01-T03 | Add/confirm `User.locale`, `Organisation.default_ui_locale`, `Organisation.default_document_locale`, `Organisation.qc_contacts_default_fr` fields + migration (choices `en-CA`,`fr-CA`) | DB | T01 | Migration applies forward/backward on fixture DB | pytest migration test |
| X-01-T04 | `LocaleResolver` service (backend) implementing UI precedence; DRF middleware sets `request.locale` and activates Django translation | BE | T03 | Unit matrix of 8 precedence cases passes | pytest parametrised |
| X-01-T05 | `DocumentLocaleResolver` (contact → org → en-CA; bilingual flag) returning `{primary, secondary?}` | BE | T03 | QC contact with no explicit language + toggle on → `fr-CA` | pytest |
| X-01-T06 | Backend formatting module `numo9.i18n.fmt` (Babel): money, decimal, percent, date (short/long), time, datetime with tz, account-style negatives | BE | T04 | `fmt.money(1234.56,'fr-CA') == '1 234,56 $'` (NBSP), `fmt.time(16:33,'fr-CA') == '16 h 33'`; en-CA `4:33 p.m.` | pytest + Hypothesis round-trip |
| X-01-T07 | Frontend formatting package `@numo9/i18n-format` wrapping `Intl.*` with identical outputs to backend for shared cases | FE | T06 | Shared fixture file `i18n_format_cases.json` passes in Vitest and pytest | Vitest + pytest cross-check |
| X-01-T08 | Locale-aware amount input parser (`1 234,56`, `1234,56`, `1,234.56`, `1234.56`) with ambiguity rule and inline hint; integrated in design-system `AmountInput` | FE | T07 | 40 parse cases pass; ambiguous `1,234` in fr-CA shows hint, never silently ×1000 | Vitest property test |
| X-01-T09 | Localised `DatePicker`/`DateInput` (month names, first day Sunday per CA convention, ISO entry accepted) | FE | T07 | fr-CA picker shows "novembre"; typed `2026-11-07` accepted | Vitest + Playwright |
| X-01-T10 | `next-intl` provider wiring: locale from profile/cookie, server components load catalogue per route segment (code-split) | FE | T04 | Switching locale re-renders without full reload; bundle per locale < 60 KB gz per route | Playwright + bundle analyser |
| X-01-T11 | Top-bar language switcher component + `PATCH /api/v1/me {locale}`; keeps unsaved form state; `Alt+L` shortcut | FE/API | T10 | Toggle in < 300 ms; draft invoice fields preserved after switch | Playwright |
| X-01-T12 | Profile › Language and region page with live format preview | FE/UX | T11 | Preview updates instantly; saved preference persists across sessions | Playwright |
| X-01-T13 | Catalogue sync script `scripts/i18n/sync_catalogues.py`: extract (formatjs + makemessages), merge, mark stale FR when EN source changed (hash), emit XLIFF | OPS | T02 | Changing an EN string marks its FR entry `needs_review` | pytest on script |
| X-01-T14 | CI missing-key gate switched from report-only to blocking for `fr-CA` on release branches; report artefact per surface (backend, frontend, emails, PDFs, CMS, mobile) | OPS | T13 | CI fails when a key lacks FR on `release/*`; report artefact downloadable | CI run evidence |
| X-01-T15 | ICU validity lint (`eslint-plugin-formatjs`) + Python ICU validator for `.po`/JSON; reject concatenation patterns (`t('a') + x`) | QA | T13 | Invalid plural syntax fails CI with file/line | CI negative test |
| X-01-T16 | Glossary lint `scripts/i18n/glossary_lint.py`: forbidden terms per locale (EN: "VAT", "annual leave", "Organization", "Check(s)"; FR: "taxe à valeur ajoutée", "chèque" misspellings, "courriel" rules) | QA | X-02-T02 | Lint flags seeded forbidden term in fixture | pytest |
| X-01-T17 | Pseudo-locale `en-XA` (+30 % length, accented chars, bracket markers) selectable in dev/staging | FE | T10 | Every screen renders in `en-XA`; untranslated hard-coded text visible without brackets | Manual + Playwright |
| X-01-T18 | Visual regression suite in `en-XA` and `fr-CA` for all design-system components and top 40 screens (Storybook + Chromatic/Playwright screenshots) | QA | T17 | 0 clipped/overflowing elements; baseline approved | Visual regression |
| X-01-T19 | Runtime fallback: missing FR key renders EN value, never raw key; Sentry event `missing_i18n_key` with key + route (rate-limited) | FE/BE | T10 | Forced missing key shows EN text and one Sentry event | Vitest + pytest |
| X-01-T20 | Accent-insensitive search & collation: Postgres `unaccent` + ICU collation `fr-CA-x-icu` for sorting names in lists and A-09 search | DB/BE | T04 | Search `elise` finds `Élise`; sort places `École` with `E` | pytest + EXPLAIN check (index used) |
| X-01-T21 | `<html lang>` and fragment `lang` attributes; direction-agnostic CSS audit (logical properties `margin-inline-start`) | FE | T10 | axe "html-has-lang" passes; CSS lint `stylelint-use-logical` 0 errors | axe + stylelint |
| X-01-T22 | `manage.py i18n_report` command: per-surface counts (total, missing, needs_review, approved) in JSON/Markdown | BE | T13 | Report lists 6 surfaces with counts; used in phase exit | pytest |
| X-01-T23 | Translator workbench in platform console (U-06): list keys by status, EN source, FR edit, screenshot context, glossary hints; writes via TMS API | FE/BE | T02, T22 | Platform Owner edits a key; change appears in TMS and next sync PR | Playwright |
| X-01-T24 | Screenshot-context capture script (Playwright walks routes in `en-XA`, maps keys → screenshots, uploads to TMS) | QA/OPS | T17, T02 | ≥ 90 % of keys have a screenshot in TMS | Script run log |
| X-01-T25 | Mobile catalogue export (same JSON → `mobile/locales/`) and `expo-localization` contract for Phase 7 | OPS | T13 | Mobile build reads fr-CA keys; missing-key gate covers mobile | CI |
| X-01-T26 | Documentation: "Localisation guide" (how to add a key, ICU rules, glossary, review flow) | DOC | T01–T25 | Page in MkDocs; linked from CONTRIBUTING | Review |

- **Deliverable acceptance:** 0 missing `fr-CA` keys at release on every surface (i18n_report); layouts hold with +30 % strings (visual suite green in `en-XA`); fr-CA formats `1 234,56 $` verified by shared fixtures; pluralisation via ICU; extraction in CI; missing-key report produced.
- **Testing approach:** unit (formatters, parser, resolvers), property-based round-trip format/parse, integration (middleware + API), visual regression (pseudo-locale), security (locale param injection — only whitelisted values accepted), performance (catalogue bundle size).
- **Risks & mitigations:** ICU/Babel output divergence (NBSP vs narrow NBSP) → shared fixture file and normalisation in tests; TMS downtime → catalogues remain in Git as source of truth; parser ambiguity → explicit hint UI and never auto-guess thousands separators.

---

### X-02 · French UI, emails and documents

- **Branch:** `feature/X-02-french-ui-documents` (sub-branches `feature/X-02a-glossary`, `X-02b-core-screens`, `X-02c-accounting-screens`, `X-02d-people-screens`, `X-02e-documents`, `X-02f-emails-notifications`)
- **Objective:** every screen, notification, email, SMS and PDF available in French with CRA/Revenu Québec terminology, and documents produced in each contact's language.
- **Current behaviour:** FR values empty; documents and emails English only; no per-contact language.
- **Expected behaviour:** complete French app; per-contact document language (EN / FR / Bilingual) with QC default FR; language frozen per issued document/revision; "Regenerate in other language"; glossary approved by the client.
- **Gap #s closed:** 42, 43, 31, 38, 17.
- **Business rules:** see §1.2 rule 5; revision stamp text localised but number unchanged; statutory forms use official FR names (FPZ-34-style GST/HST worksheet labels, FPZ-500 QST, Relevé 1); custom-field labels have EN/FR values — sending a FR document with a field lacking FR label warns.
- **Edge cases:** contact language changed after invoice issued (keeps issue language; reminder emails use current contact language — documented choice: reminders follow contact's current language, attached PDF re-rendered in same language as reminder) ; bilingual PDF exceeding one page; long FR item descriptions; email subject length limits; SMS 160-char limit with accents (UCS-2 = 70 chars) → FR SMS templates kept ≤ 70 chars or split.
- **UI/UX notes:** LanguageChip in all document editors; email dialog shows language; preview toggle EN/FR; template editor shows both languages side by side.
- **Dependencies:** X-01 (T04–T10, T13–T16); D-03a/D-03b, D-02, D-06, D-07, B-02, E-01, E-06, N-05, N-07, N-08, G-03/G-04/G-05, FN-02/FN-05, K-08, A-07.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| X-02-T01 | Collect terminology sources (CRA FR guides RC4022/RC4110, T4127 FR, RQ FPZ-500, RL-1 guide, TERMIUM, OQLF) into `docs/i18n/sources.md` | DOC | — | Source list with links/edition dates | Review |
| X-02-T02 | Draft glossary `docs/i18n/glossary_fr-CA.csv` (≥ 300 terms: accounting, tax, payroll, inventory, finance, SaaS) with EN term, FR term, definition, source, status | DOC | T01 | CSV loads into TMS glossary; all open questions (§1.4) listed | Script validation |
| X-02-T03 | Glossary review session #1 with client reviewer; record decisions | DOC | T02 | Decisions recorded; status `approved` on ≥ 90 % terms | Sign-off note |
| X-02-T04 | Load approved glossary into TMS and glossary lint (X-01-T16) | OPS | T03, X-01-T16 | Lint enforces approved terms on CI | CI |
| X-02-T05 | Translate shell & navigation (top bar, menus, quick-create, global search labels, notifications centre, shortcuts help) | FE/i18n | T04 | 0 missing keys in `shell/*`; visual check in fr-CA | i18n_report + visual |
| X-02-T06 | Translate auth & onboarding (sign-up, verification, 2FA, invitations, password reset) incl. backend validation messages | FE/BE/i18n | T04 | Full sign-up in FR without EN text | Playwright FR flow |
| X-02-T07 | Translate SaaS screens (packages, plan/feature matrix, trial banners, founding badge, billing, dunning notices, demo watermark) | FE/i18n | T04 | 0 missing in `billing/*`, `packages/*`; 402 gating messages FR | Playwright |
| X-02-T08 | Translate accountant workspace (directory, filters, groups, tags, bulk actions, cross-org dashboards, staff management) | FE/i18n | T04 | 0 missing in `workspace/*`; plural strings correct ("1 organisation" / "2 organisations") | Vitest plural cases |
| X-02-T09 | Translate contacts (editor, roles, terms master, statements, import wizard incl. column-mapping labels and dry-run report) | FE/BE/i18n | T04 | 0 missing in `contacts/*`; dry-run report FR | Playwright |
| X-02-T10 | Translate ledger (CoA, account types, GIFI editor, journals, journal types, approvals, period close, conversion balances, find & recode) | FE/BE/i18n | T04 | 0 missing in `ledger/*`; account-type enum labels FR via API | pytest enum labels + visual |
| X-02-T11 | Translate sales (overview, quotes, invoices, revisions panel, recurring, payments, credit notes, reminders settings) | FE/i18n | T04 | 0 missing in `sales/*`; revision history panel FR | Visual |
| X-02-T12 | Translate purchases (POs, GRN, 3-way match, bills, duplicate review, expense claims, batch payments, cheque register) | FE/i18n | T04 | 0 missing in `purchases/*` | Visual |
| X-02-T13 | Translate banking (accounts, types, import mapping, rules builder conditions, reconciliation, transfers, negative-balance warnings) | FE/i18n | T04 | Rule-builder sentences grammatical in FR ("La description contient …") | Visual + reviewer check |
| X-02-T14 | Translate tax (codes, place-of-supply hints, GST/HST and QST worksheets UI with official line names, filing-cycle engine, stop/restart, tax settings, tax payments) | FE/i18n | T04 | Line labels match CRA/RQ FR wording per glossary | Reviewer checklist |
| X-02-T15 | Translate reporting (report engine controls, statement names, two-book selector, book reconciliation, exceptions-engine rule names and explanations, dashboard widgets, adviser templates NTR/Review/Compilation FR wording) | FE/BE/i18n | T04 | Report titles FR ("État des résultats", "Bilan", "Balance de vérification"); exception messages FR | Visual + pdf text |
| X-02-T16 | Translate inventory & analytics (items, UoM, locations, movements, costing, reorder, BOM, SKU rankings, EOQ, margin/price optimisation, KPIs) | FE/i18n | T04 | 0 missing in `inventory/*` | Visual |
| X-02-T17 | Translate fixed assets & CCA (register, SL/DB, CCA classes (catégories de DPA), UCC (FNACC), half-year rule, full-CCA-as-loss option, disposals, templates importer) | FE/i18n | T04 | CCA terms per glossary | Reviewer check |
| X-02-T18 | Translate finance module (loan register, amortisation schedule, early repayment, credit-terms interest, finance KPIs) | FE/i18n | T04 | 0 missing in `finance/*` | Visual |
| X-02-T19 | Translate projects & time, Sheets (menus, function names kept in EN syntax `=GL()` with FR help text), budgets, multi-currency | FE/i18n | T04 | Sheets help FR; formula names unchanged | Visual |
| X-02-T20 | Translate HR & payroll screens (employee master, TD1 labels, leave, onboarding, pay runs, benefits with T4 box labels, worker-classification factors, remittances, year-end slips, ROE) | FE/i18n | T04 | Payroll labels match T4127/RQ FR terms | Reviewer check |
| X-02-T21 | Translate practice management & settings (service catalogue, engagements, document requests, deadline calendar, task board, all settings pages incl. lock dates) | FE/i18n | T04 | 0 missing in `practice/*`, `settings/*` | Visual |
| X-02-T22 | Translate backend API error catalogue and enum labels (`numo9/errors.py`, choices) + DRF validation messages | BE/i18n | T04 | `Accept-Language: fr-CA` returns FR `detail` for 100 % of error codes | pytest over error registry |
| X-02-T23 | `Contact.document_language` (`en-CA`/`fr-CA`/`bilingual`) + `email_language`, QC-address default rule, migration, API, contact editor field with auto-suggest hint | DB/BE/FE | X-01-T05 | New QC contact defaults FR when org toggle on; field editable; audit logged | pytest + Playwright |
| X-02-T24 | `IssuedDocument.language` frozen on issue for invoices, revisions, quotes, credit notes, POs, statements; "Regenerate in other language" action storing a new rendition | DB/BE/FE | T23 | Re-print returns same language; regenerate adds rendition, original kept | pytest |
| X-02-T25 | LanguageChip + "Change for this document" popover in all document editors (shared design-system component) | FE/UX | T23 | Chip visible in invoice, quote, PO, credit note, bill editors | Playwright |
| X-02-T26 | PDF template i18n framework: Jinja2 i18n extension, `lang` attribute, babel filters (`money`, `date_long`), embedded fonts with French glyphs, hyphenation | BE | X-01-T06 | Sample PDF renders accents, «», NBSP correctly (pdfplumber text check) | pytest pdf text |
| X-02-T27 | French invoice PDF (headings, terms, tax breakdown TPS/TVH/TVQ with registration numbers, payment instructions, pay-link label) | BE/DOC | T26 | Snapshot matches approved FR fixture | Snapshot test |
| X-02-T28 | French revision stamp ("Révision n de la facture N — remplace la version émise le …") and superseded watermark | BE | T27 | 101-1 PDF shows FR stamp with correct date format | Snapshot |
| X-02-T29 | French credit note PDF ("Note de crédit") | BE | T26 | Snapshot | Snapshot |
| X-02-T30 | French customer & supplier statements ("État de compte", activity/outstanding) | BE | T26 | Snapshot; totals formatted fr-CA | Snapshot |
| X-02-T31 | French quote PDF ("Soumission"/"Devis" per glossary) incl. optional lines, deposit, e-signature block | BE | T26 | Snapshot | Snapshot |
| X-02-T32 | French purchase order and remittance advice PDFs ("Bon de commande", "Avis de paiement") | BE | T26 | Snapshot | Snapshot |
| X-02-T33 | French pay stub ("Talon de paie": RPC/RPC2 or RRQ/RRQ2, AE, RQAP, impôt fédéral/provincial, avantages imposables, cumul annuel) | BE | T26 | Snapshot; labels match glossary | Snapshot + reviewer |
| X-02-T34 | French T4 / T4A / T5 cover letters and summaries (human-readable PDFs; XML untouched) + RL-1 summary labels | BE | T26 | Snapshot; XML byte-identical regardless of locale | pytest XML compare |
| X-02-T35 | French remittance summary (PD7A-style "Sommaire des retenues à la source") | BE | T26 | Snapshot | Snapshot |
| X-02-T36 | French tax reports: GST/HST worksheet (official line names), QST worksheet (FPZ-500 wording), tax by code/document, ITC/ITR detail, tax-to-GL tie-out | BE | T26 | Snapshot; line numbers unchanged | Snapshot |
| X-02-T37 | French loan reports [v2.1]: amortisation schedule ("Tableau d'amortissement"), loan continuity, interest summary (YTD/total) | BE | T26 | Snapshot | Snapshot |
| X-02-T38 | French financial statements & two-book side-by-side (K-02, K-08), management pack and adviser templates (Avis au lecteur / Mission de compilation NCSC 4200 / Mission d'examen) | BE | T26 | Snapshot; client reviewer approves NCSC wording | Snapshot + reviewer |
| X-02-T39 | Bilingual PDF layout option (two-column EN/FR labels) for invoice, quote, credit note, statement [EXTRA] | BE/UX | T27–T31 | Bilingual invoice fits Letter with inch margins on 20-line fixture | Snapshot |
| X-02-T40 | Email templates FR (MJML): invoice, revision, quote, credit note, statement, reminders before/after due, receipt, PO, remittance, payment failed, trial 7/3/1, dunning 3/5/7, invitations, 2FA, password reset, tax-payment confirmation, payroll ready | BE/DOC | T22 | Every template has FR variant; subject + preheader FR; i18n_report emails = 0 missing | pytest renders all |
| X-02-T41 | Email language selection wiring: send path uses `DocumentLocaleResolver`; compose dialog shows/overrides language; sent-email log stores language | BE/FE | T40, T23 | EN-UI user sends to FR contact → FR email logged with `language=fr-CA` | Integration test |
| X-02-T42 | SMS/WhatsApp reminder templates FR within 70-char UCS-2 budget or multipart rule | BE | T40 | Length check test passes for all FR SMS templates | pytest |
| X-02-T43 | In-app notifications and push payload FR (notification registry) | BE | T22 | Notification centre FR for FR user | pytest + Playwright |
| X-02-T44 | Custom fields EN/FR labels (B-01) + send-time warning when FR label missing | BE/FE | T23 | Warning dialog lists missing labels; send allowed after confirm | Playwright |
| X-02-T45 | Template editor: side-by-side EN/FR preview with Canadian sample data (Montréal FR contact, Toronto EN contact) | FE/UX | T27 | Preview never shows non-Canadian sample data | Visual |
| X-02-T46 | FR demo organisation seed (`seed_fr_demo`: Montréal, QST registered, FR contacts, FR revised invoice) for demo/UAT | BE | T27, T40 | Demo created in < 10 s; all docs FR | pytest |
| X-02-T47 | Full catalogue QA pass: LanguageTool on FR catalogue, typography (NBSP rules), consistency vs glossary; fix list | QA | T05–T22 | 0 LanguageTool errors of category grammar/typography (excluding whitelisted terms) | Report |
| X-02-T48 | Glossary & documents review session #2 with client reviewer (all PDFs + top 40 screens); apply corrections | DOC | T27–T47 | Written sign-off of glossary and document set | Sign-off |
| X-02-T49 | Gap-closure tests `gap-42`, `gap-43`, `gap-31`, `gap-38`, `gap-17-date` | QA | T41, T45 | All tagged tests green | Playwright + pytest |

- **Deliverable acceptance:** a Quebec contact with language FR receives a French invoice (PDF + email, incl. revision stamp on 101-1) from an English-UI user; all listed PDFs and emails render in FR; glossary approved by the client; 0 missing keys in app, emails, PDFs.
- **Testing approach:** functional E2E in `fr-CA` browser context for top 15 flows; snapshot tests for every PDF in both locales (`render_all_documents`); integration on email send path; regression full suite in EN (no EN regressions); data validation — amounts identical across languages (text-extracted totals compared); security — template injection checks on translated strings (no raw HTML from catalogue unless whitelisted tags).
- **Risks & mitigations:** reviewer availability → review in two batches, 5-business-day windows; legal wording of NCSC 4200 templates → reviewer approval mandatory; FR text overflow on PDFs → snapshot with long-string fixture; email clients mangling NBSP → use `&nbsp;`/`&#8239;` entities in MJML.

---

### X-03 · Bilingual website and portal

- **Branch:** `feature/X-03-bilingual-website-portal`
- **Objective:** Numo9 public website and client portal fully bilingual with correct SEO and per-user portal language.
- **Current behaviour:** English website on Next.js ISR + Django CMS; portal English only; no hreflang.
- **Expected behaviour:** `/fr/…` pages with localised slugs, hreflang alternates, FR sitemap, FR structured data, FR pricing (live from U-02 with fr-CA formats), FR founding counter, FR sign-up funnels; portal language switcher per portal user; non-forced language suggestion on first visit.
- **Gap #s closed:** 42 (portal/email language), 61 (localisation ready).
- **Business rules:** CMS page has EN and FR versions linked as translations; publishing FR requires FR content (no auto-copy); prices identical, only formatting differs; legal pages in both languages (Quebec requirement).
- **Edge cases:** page exists in EN only → FR route shows notice and EN content with `lang="en"`, excluded from FR sitemap; slug collisions; cached ISR pages per locale; cookie vs `Accept-Language` conflict (cookie wins).
- **UI/UX notes:** header/footer toggle keeping current page; suggestion banner, never forced redirect; FR CTAs ("Essai gratuit de 30 jours", "Créer un compte comptable gratuit").
- **Dependencies:** X-01, X-02-T04 (glossary), Q-01…Q-04, O-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| X-03-T01 | CMS translation model: `Page.locale`, `translation_group`, localised slug, status per locale (django-modeltranslation or explicit model) + migration | DB/BE | X-01-T03 | EN and FR pages linked; FR publish blocked without FR body | pytest |
| X-03-T02 | Next.js `[locale]` routing for site (`/` EN, `/fr/…`), localised slug map, 301 rules for legacy paths | FE | T01 | `/fr/tarifs` resolves; `/fr/pricing` 301 → `/fr/tarifs` | Playwright |
| X-03-T03 | hreflang alternates (`en-CA`, `fr-CA`, `x-default`) and canonical tags on every page | FE | T02 | Validator (hreflang checker) 0 errors | Lighthouse + custom check |
| X-03-T04 | Locale-aware sitemaps (`next-sitemap`) and robots; EN-only pages excluded from FR sitemap | FE/OPS | T03 | Both sitemaps valid XML; submitted in Search Console (client account) | XML schema check |
| X-03-T05 | FR structured data JSON-LD (`Organization`, `SoftwareApplication`, `Offer` with `priceCurrency CAD`, `inLanguage fr-CA`) | FE | T02 | Rich-results test passes for FR home and pricing | Google Rich Results test |
| X-03-T06 | FR copy for Home, Products (Comptabilité, Taxes, Paie, Inventaire, Finance), Forfaits et tarifs, Offre fondatrice, Pour les comptables, Démo, Essai gratuit, Ressources, À propos, Contact | DOC | X-02-T04 | Client approves FR copy | Reviewer sign-off |
| X-03-T07 | FR legal pages (conditions d'utilisation, politique de confidentialité PIPEDA/Loi 25 notice, cookies) — client-supplied/approved text | DOC | T06 | Pages published in both languages | Review |
| X-03-T08 | Live pricing and founding counter in fr-CA formatting ("Il reste 734 places sur 1 000") | FE | X-01-T07 | Price `49,00 $ / mois` format; counter plural correct | Vitest + Playwright |
| X-03-T09 | Language toggle in site header/footer preserving current page; first-visit suggestion banner by `Accept-Language`; cookie persistence | FE/UX | T02 | Toggle lands on translated equivalent; banner dismissible, no forced redirect | Playwright |
| X-03-T10 | FR sign-up funnels (accountant + organisation trial + demo request) passing `locale=fr-CA` to account creation | FE/BE | T09, X-01-T04 | New user created from FR funnel has `locale=fr-CA`; first app screen in FR in < 2 min | Playwright timed |
| X-03-T11 | Portal language switcher + `PortalUser.locale`; portal emails follow portal user language | FE/BE | X-01-T11 | Portal user switches to FR; next email FR | Playwright |
| X-03-T12 | Portal content FR: dashboard, messaging, approvals, e-signature, subscription/package view, loan and tax-payment views, revision badges ("Révisée") | FE/i18n | T11 | 0 missing in `portal/*` | i18n_report |
| X-03-T13 | E-signature page and consent text FR (legal wording reviewed) | FE/DOC | T12 | Signed FR quote stores consent text version + language | pytest |
| X-03-T14 | Lighthouse CI on both locales (home, pricing, sign-up, blog post) with budgets SEO ≥ 90, a11y ≥ 90, perf ≥ 90 | QA | T03–T10 | All budgets met for both locales | Lighthouse CI |
| X-03-T15 | Analytics locale dimension (site + app) and funnel by language | OPS | T10 | Dashboards show EN vs FR sign-ups | Manual check |

- **Deliverable acceptance:** FR pages with hreflang; portal language per user; Lighthouse SEO ≥ 90 on both locales.
- **Testing approach:** functional E2E per locale; SEO validators; accessibility axe; performance Lighthouse; regression on EN site.
- **Risks & mitigations:** client copy delays → GMA draft copy approved in one pass; duplicate-content SEO → hreflang + canonical; ISR cache serving wrong locale → cache key includes locale (tested).

---

## 7. TEST — phase test plan (Rules 5–6)

| Category | Scope | Tooling | Target |
|---|---|---|---|
| Unit | Formatters, parser, resolvers, plural rules, glossary lint, SMS length | pytest, Hypothesis, Vitest | ≥ 90 % on `numo9.i18n` |
| Integration | Middleware/API locale, email send path language, PDF rendering service, TMS sync | pytest + DRF client, mailpit | Every endpoint returns FR errors with `Accept-Language: fr-CA` |
| Functional | 15 top flows in fr-CA (sign-up, invoice to QC contact, revise invoice, quote accept, bill, spend money, GST worksheet, pay run & stub, T4 cover, portal approval, tax payment) | Playwright locale context | 100 % pass |
| Regression | Full EN suite unchanged | CI | 0 regressions |
| Data validation | Totals extracted from EN and FR PDFs identical | pdfplumber script | 100 % identical |
| Security | Locale param whitelist; no HTML injection via catalogue; XSS in FR strings | pytest, ZAP | No high findings |
| Localisation | Missing-key gate, pseudo-localisation visual, LanguageTool, glossary lint | CI | 0 missing; 0 clipped; 0 glossary violations |
| Accessibility | axe in fr-CA on all routes, NVDA FR spot checks | axe-core, manual | 0 serious/critical |
| Performance | Catalogue bundle size, locale switch latency | Bundle analyser, Playwright trace | < 60 KB gz per route; switch < 300 ms |
| Gap closure | gap-42, gap-43, gap-31, gap-38, gap-17-date, gap-44-time | tagged tests | All green |

**Exit demonstration script (staging)**
1. Run `manage.py i18n_report` → expected: 0 missing `fr-CA` on backend, frontend, emails, PDFs, CMS, mobile.
2. Switch staging to `en-XA` pseudo-locale and open 10 random screens → no clipped text.
3. Log in as EN-UI user in Ontario organisation; open contact "Boulangerie Laval" (Québec) → chip `FR`.
4. Create invoice 101 for 1,130.00 → Approve & email → email received in mailpit with FR subject and body; PDF "Facture 101", amounts `1 130,00 $`, TPS/TVQ lines.
5. Edit invoice to 1,017.00 → 101-1 → FR email and PDF stamp "Révision 1 de la facture 101 — remplace la version émise le …".
6. Switch UI to FR (one click) → invoice screen in French; form state preserved.
7. Open French pay stub and T4 cover for a QC employee → FR labels per glossary.
8. Open `/fr/tarifs` → FR prices, hreflang present; Lighthouse SEO ≥ 90 on `/` and `/fr`.
9. Portal user switches to FR → portal and next notification in FR.
10. Show client glossary sign-off record.

**Failure handling:** stop dependent tasks, identify exact failing key/template, classify (code, data, config, assumption), one focused fix, rerun affected tests then full suite; never mark a key "approved" to pass the gate.

---

## 8. IMPROVE — post-verification checklist

- Remove dead keys (unused after extraction) — keep catalogue lean.
- Merge near-duplicate keys with identical meaning (reduce translator load) without changing EN output.
- Review long FR strings causing tooltips; shorten with reviewer where possible.
- Measure catalogue bundle size per route; split namespaces if > budget.
- Confirm Sentry `missing_i18n_key` = 0 events over 48 h on staging.
- Re-run full regression and visual suites after improvements.
- **Performance budgets:** locale switch < 300 ms; PDF render FR ≤ EN time + 10 %; site LCP < 2.5 s both locales.

---

## 9. Git branch plan (Rule 7)

| Branch | Base | Deliverable | Merge order |
|---|---|---|---|
| `feature/X-01-i18n-infrastructure` | `main` | X-01 | 1 |
| `feature/X-02a-glossary` | `feature/X-02-french-ui-documents` | X-02 T01–T04 | 2 |
| `feature/X-02b-core-screens` | X-02 | T05–T09, T22 | 3 |
| `feature/X-02c-accounting-screens` | X-02 | T10–T19, T21 | 3 (parallel) |
| `feature/X-02d-people-screens` | X-02 | T20 | 3 (parallel) |
| `feature/X-02e-documents` | X-02 | T23–T39, T44–T46 | 4 |
| `feature/X-02f-emails-notifications` | X-02 | T40–T43 | 4 (parallel) |
| `feature/X-02-french-ui-documents` | `main` | X-02 (T47–T49) | 5 |
| `feature/X-03-bilingual-website-portal` | `main` | X-03 | 5 (parallel) |

**Before branch:** `git status` clean, pull `main`, restate objective + acceptance in PR description, confirm X-01 merged for dependants. **Before complete:** acceptance observed, CI green incl. missing-key gate and visual suite, no unrelated changes, no debug code/secrets, docs updated, second-engineer review, project-lead authorisation for merge.

---

## 10. Phase risks register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Client reviewer unavailable in week 9 | Medium | High | Book two review slots at kickoff of week 9; deemed-acceptance rules (Agreement 7.4) |
| 2 | Terminology disputes (CRA vs OQLF vs firm usage) | Medium | Medium | Glossary with sources; client decision final; lint enforces |
| 3 | Layout breaks with FR length | Medium | Medium | Pseudo-locale suite from day 1 of phase |
| 4 | Number-parsing errors in fr-CA causing wrong postings | Low | Critical | Property tests; ambiguity hint; posting preview shows formatted amount |
| 5 | Mixed-language documents sent to customers | Medium | High | Frozen document language; send-time warnings; snapshot tests |
| 6 | Hypercare 1 load competes with Phase 6 work | High | Medium | Separate on-call engineer for hypercare (see Hypercare plan) |
| 7 | TMS/self-hosting overhead | Low | Low | Git remains source of truth; TMS optional for edits |
| 8 | SEO regressions on EN site | Low | Medium | Canonical/hreflang validation in CI; Lighthouse budgets |

---

## 11. Phase completion checklist (Rule 11) & reporting template (Rule 10)

**UNDERSTAND** — [ ] existing catalogues and templates inventoried · [ ] users and outcomes identified · [ ] inputs/outputs defined · [ ] precedence and terminology rules identified · [ ] edge cases (parsing, NBSP, SMS length) considered · [ ] objective restated.
**PLAN** — [ ] X-01/X-02/X-03 decomposed into atomic tasks · [ ] dependencies mapped · [ ] order defined · [ ] acceptance criteria per task · [ ] test procedures defined.
**BUILD** — [ ] smallest slice (FR invoice to QC contact) first · [ ] design-system components reused · [ ] no unrelated changes · [ ] EN behaviour preserved · [ ] feature keys untouched / i18n keys declared.
**TEST** — [ ] behaviour verified in both locales · [ ] edge cases tested · [ ] failures resolved · [ ] regressions checked · [ ] tenant-isolation sweep re-run (locale endpoints) · [ ] unverified conditions recorded.
**IMPROVE** — [ ] dead keys removed · [ ] temporary pseudo-locale artefacts hidden in prod · [ ] readability reviewed · [ ] behaviour re-verified.
**COMPLETE** — [ ] final diff reviewed · [ ] Localisation guide + ADR-005 updated · [ ] results reported · [ ] acceptance confirmed (0 missing keys, FR invoice demo, glossary sign-off, Lighthouse ≥ 90 both locales) · [ ] final status reported.

**Reporting template**
- *Before implementation:* 1. Problem understanding (objective, existing, expected). 2. Task breakdown (components, atomic tasks, dependencies). 3. Implementation plan (order, acceptance, tests).
- *After implementation:* 1. Changes made (tasks, files/components, decisions). 2. Testing results (executed / passed / failed / not executed and why). 3. Remaining issues (limitations, bugs, risks). 4. Final status — Complete / Partially complete / Blocked.

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| X-01 | 26 | 39 |
| X-02 | 49 | 73.5 |
| X-03 | 15 | 22.5 |
| **Total** | **90** | **135** |
