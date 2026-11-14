# Accessibility suite

A-10-T19 · Deliverable A-10 · gap-60 · Phase 0 plan §3.6 "Automated a11y".

Acceptance: **0 serious or critical axe violations** on every Storybook story and every Phase 0
route, and no leaked hidden labels.

| Suite | Scope | File |
|---|---|---|
| Component tests (jsdom) | Each component's states, keyboard paths (A-10-T06 onward) | `packages/ui/src/**/*.test.tsx` via `src/test/axe.ts` |
| Stories (browser) | Every story in the built Storybook's `index.json` | `packages/ui/e2e/a11y.spec.ts` |
| Pages (browser) | `/`, every Phase 0 organisation route, the 404 page — 1280 px and 360 px — plus the open navigation drawer and the skip link | `frontend/e2e/a11y.spec.ts` |

The browser suites run axe-core (the repository's pinned version, loaded as a private instance so
Storybook's own a11y addon does not interfere) with the WCAG 2.0/2.1 A + AA and best-practice
rules, **including colour contrast**, which jsdom cannot compute. Stories switch off the landmark
and page-heading rules (a story is one component on its own); pages run every rule. Serious and
critical findings fail the build; minor and moderate findings are attached to the test report.

## Hidden-label audit (gap-60)

Xero's Executive Summary prints its hidden column header as "Variance for Variance".
`auditLabels` (`packages/ui/e2e/a11y.ts`) checks every screen for:

| Rule | Fails when |
|---|---|
| `visible-sr-only` | `.sr-only` text is visible (the skip link is allowed while focused) |
| `repeated-name` | An accessible name repeats itself — "Variance for Variance", "Amount Amount" |
| `header-repeats-hidden-text` | A header's screen-reader-only text repeats its visible text |
| `empty-name` | A column/row header or an `aria-label` has no name |

A self-test feeds the audit a page with each fault and expects all four rules to fire.

## Fixed in this task

The app shell's brand mark ("N9") and account initials were text inside links/buttons whose
accessible names are "Numo9 home" and "Account menu: …" (WCAG 2.5.3 label in name). Both are now
decorative generated content (`data-mark` / `data-initials` with `content: attr(…)`), so the
accessible name is the only name; the rendering is unchanged.

## Contacts review (B-01-T18)

Review of the B-01 contact pieces built so far (the contact list and form screens, B-01-T14/T15,
join the page suite when they land):

| Piece | Check | Result |
|---|---|---|
| Live duplicate panel (`frontend/src/contacts/DuplicatePanel.tsx`) | axe (jsdom, `frontend/src/contacts/DuplicatePanel.test.tsx` via `packages/ui/src/test/axe.ts`) | 0 violations |
| | Region labelled by its heading; result count announced once through a polite `role="status"` (changes only when the count changes, never on every keystroke) | Pass |
| | Label in name (WCAG 2.5.3): visible "Open" / "Merge…" / "Ignore" start the accessible names "Open Maple Supply Ltd." …; each row's links/buttons are distinguishable | Pass |
| | Colour never the only cue: reasons are written out ("Business Number matches · Name 79% similar"), Archived is a text badge | Pass |
| Wording (backend catalogues, frontend messages) | Glossary lint (`backend/tools/check_glossary.py`): Province / Postal code, never State / ZIP; no VAT | 0 banned terms (two help texts reworded: "State, county or region…" → "Region or county…", "foreign VAT or EIN" → "foreign registration number") |
| Messages | `lint:i18n` (no hard-coded text), FormatJS extract + en-CA/fr-CA catalogues complete, Django `makemessages` en_CA/fr_CA complete | Pass (fr-CA keeps English placeholders until Phase 6) |

## Commands

```bash
pnpm --filter @numo9/ui run build-storybook && pnpm --filter @numo9/ui run test:e2e
pnpm --filter @numo9/frontend run build && pnpm --filter @numo9/frontend run test:e2e
```
