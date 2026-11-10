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
