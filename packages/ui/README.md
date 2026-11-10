# @numo9/ui

Numo9 design system (deliverable A-10). Every screen is built from this package.

| Path                         | What it is                                                                                       |
| ---------------------------- | ------------------------------------------------------------------------------------------------ |
| `tokens/tokens.json`         | Brand tokens, W3C DTCG format — the single source (also imported into Figma)                     |
| `tokens/contrast-pairs.json` | Allowed text/background pairs, each ≥ 4.5:1                                                      |
| `scripts/build-tokens.mjs`   | Generates `src/styles/tokens.css` (CSS variables) and `src/styles/theme.css` (Tailwind v4 theme) |
| `src/styles/index.css`       | Package stylesheet: tokens, theme and base styles                                                |
| `.storybook/`                | Storybook 8 (React + Vite, Tailwind, a11y addon)                                                 |

```bash
pnpm --filter @numo9/ui run tokens          # regenerate CSS after editing tokens.json
pnpm --filter @numo9/ui run tokens:check    # CI: generated CSS matches tokens.json
pnpm --filter @numo9/ui run contrast        # CI: every contrast pair ≥ 4.5:1 (--markdown for docs)
pnpm --filter @numo9/ui run test            # Vitest
pnpm --filter @numo9/ui run storybook       # http://localhost:6006
pnpm --filter @numo9/ui run build-storybook # static Storybook (CI)
pnpm --filter @numo9/ui run test:e2e        # Playwright on the built Storybook (DataGrid 10k rows at 60 fps)
```

Using it in an app stylesheet (Tailwind v4):

```css
@import "tailwindcss";
@import "@numo9/ui/styles.css";
@source "../../../packages/ui/src";
```

Utilities come from the tokens only (Tailwind's default palette is removed): `bg-surface`,
`bg-surface-inverse`, `bg-surface-accent`, `text-fg`, `text-fg-muted`, `text-fg-on-accent`,
`border-border`, `shadow-elevation-2`, `rounded-md`, `text-sm`, `p-4` (4 px grid).
Docs: `docs/design/brand-tokens.md`.

## Components

| Area                               | Exports                                                                                                                                                                                               | Task     |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Layout (`src/shell/`)              | `AppShell`, `Breadcrumbs`                                                                                                                                                                             | A-10-T05 |
| Org switcher (`src/org-switcher/`) | `OrgSwitcher`, `searchOrganisations`, `recentOrganisations`                                                                                                                                           | A-01-T14 |
| Primitives (`src/primitives/`)     | `Button`, `IconButton`, `Input`, `Select`, `Combobox`, `Checkbox`, `RadioGroup`, `Switch`, `Dialog`, `Drawer`, `Tooltip`, `ToastProvider`/`useToast` (Undo), `Tabs`, `Badge`, `StatusBadge`           | A-10-T06 |
| Forms (`src/forms/`)               | `Form` (RHF + Zod), `Field`, `TextField`, `SelectField`, `CheckboxField`, `ErrorSummary`, `StickySaveBar`, `useUnsavedChangesGuard`                                                                   | A-10-T07 |
| Formatting (`src/format/`)         | `formatMoney`, `formatDate`, `formatTime` (12/24 h), `formatDateTime`, `formatNumber`, `parseMoney`, `parseDate` (forgiving), calendar-date helpers (`addDays`, `addMonths`, `endOfMonth`, `todayIn`) | A-10-T08 |
| Pickers (`src/pickers/`)           | `DatePicker` (calendar + shortcuts), `ProvincePicker`, `PostalCodeInput`, `CurrencyInput`, `AccountPicker` (type/side filter), `ContactPicker` (role, server search, create)                          | A-10-T09 |
| Data grid (`src/data-grid/`)       | `DataGrid` (TanStack Table + Virtual: sort, search, filter chips, column chooser, density, selection + bulk bar, sticky header, states), `useSavedViews`, `localSavedViewsStore`                      | A-10-T10 |

Components hold no user-visible text of their own: labels arrive through props (i18n messages).
Component tests run axe-core (`src/test/axe.ts`, WCAG 2.1 A/AA); Storybook's a11y panel runs it
on every story.
