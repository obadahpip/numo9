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

## Commands

```bash
pnpm --filter @numo9/ui run build-storybook && pnpm --filter @numo9/ui run test:e2e
pnpm --filter @numo9/frontend run build && pnpm --filter @numo9/frontend run test:e2e
```
