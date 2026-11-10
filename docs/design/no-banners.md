# No banners in work screens

A-10-T17 · Deliverable A-10 · gap-12 · Phase 0 UX principle 15.

Xero stacks promotional banners above its invoice editor and pushes the form below the fold.
Numo9 work screens — editors, lists, settings and dashboards — carry **no promotional or
announcement banners**.

| Message | Where it goes |
|---|---|
| System notices (maintenance, trial reminders, job results, failed imports) | Notification centre — the bell in the app shell (A-07) |
| Commercial messages (packages, upgrades, offers) | Settings → Subscription |
| Platform-owner announcements | The owner-controlled, dismissible announcement slot on Home |

## Component policy

- `@numo9/ui` has no banner component and the app shell has no banner slot. The only `banner`
  landmark on a page is the shell's top bar.
- Feedback about the user's own action uses a `Toast` (with Undo where safe) or an inline
  message next to the field; it never takes the place of the screen's content.
- Only two locations may render commercial messages, listed in `BANNER_ALLOWED_FILES`
  (`frontend/eslint/no-work-screen-banners.mjs`):
  `src/app/o/[org]/settings/subscription/**` and
  `src/components/announcements/HomeAnnouncementSlot.tsx`. Adding a location is a plan change.

## Lint rule `numo9/no-work-screen-banners`

Part of `frontend/eslint.config.mjs` (CI `eslint` step). Outside the allowed files it reports:

| Pattern | Example |
|---|---|
| A component named `…Banner`, or `Promo…`, `Promotion…`, `Upsell…`, `Marketing…`, `Ad…`, `Advert…`, `Announcement…` | `<UpgradeBanner />`, `<PromoCard />`, `<Marketing.Hero />` |
| `role="banner"` | `<div role="banner">` |
| A `banner`, `promo`, `upsell` or `marquee` class | `className="promo-card"` |
| A `data-banner` / `data-promo` attribute | `<aside data-promo="payroll">` |

## gap-12 checks (CI)

| Check | File |
|---|---|
| Rule rejects each pattern, allows the two locations, and finds nothing in `frontend/src` or `packages/ui/src` | `frontend/src/lint/no-work-screen-banners.test.ts` (Vitest) |
| Every Phase 0 organisation route at 1280 × 800: one `banner` landmark (the shell), no banner/promo element, page heading within the first 200 px of the main region | `frontend/e2e/gap-12.spec.ts` (Playwright) |
