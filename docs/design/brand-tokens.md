# Brand tokens

A-10-T01 · Deliverable A-10 (design system & localisation baseline).

The Numo9 brand is a **black wordmark on yellow** with the tagline "Numbers build a brighter
tomorrow". These tokens turn that brand into the colour, type, spacing, radius and elevation values
used by Figma and by the code (`@numo9/ui`).

| File | What it holds |
|---|---|
| `packages/ui/tokens/tokens.json` | Every token, W3C Design Tokens (DTCG) format — the single source of truth |
| `packages/ui/tokens/contrast-pairs.json` | The foreground/background pairs screens may combine, each checked ≥ 4.5:1 (A-10-T04) |

!!! note "Provisional brand values"
    The client has not yet supplied the exact logo colour values or a typography preference
    (Phase 0 plan §1.4 open questions). `color.brand.yellow` (`#FFD100`), `color.brand.black`
    (`#111111`) and the Inter type family are provisional. When the client supplies the values, change
    them in `tokens.json` only — Figma (re-import) and the code (regenerated CSS) follow.

## Using the tokens in Figma

The file is plain DTCG JSON, so it loads into Figma as variables:

1. Figma → **Local variables** → **Import** (DTCG JSON), or the *Tokens Studio for Figma* plugin →
   *Load from file*.
2. Pick `packages/ui/tokens/tokens.json`. Groups become collections: `color` (primitives),
   `semantic` (role aliases that reference the primitives), `font`, `space`, `radius`, `elevation`.
3. Designers bind fills and strokes to **semantic** variables only; primitives are not used on
   screens.

Re-import after every change to `tokens.json`; never edit values in Figma without changing the file.

## Colour

### Brand and primitives

| Token | Value | Notes |
|---|---|---|
| `color.brand.yellow` | `#FFD100` | Logo background; accent on black or white surfaces |
| `color.brand.black` | `#111111` | Logo wordmark; top navigation |
| `color.yellow.50 … 900` | `#FFFBE6` … `#4D3A00` | 400 = brand yellow; 800 (`#7A5C00`) is the darkest text-safe yellow |
| `color.neutral.0 … 950` | `#FFFFFF` … `#111111` | 950 = brand black |
| `color.red / green / amber / blue` | 50, 100, 600–800 | Feedback colours (danger, success, warning, info) |

### Semantic roles (what screens use)

| Role | Token → value | Used for |
|---|---|---|
| Page / card | `semantic.surface.default` → `#FFFFFF` | Page and card background |
| Side navigation | `semantic.surface.subtle` → `#FAFAFB` | Side navigation, table header |
| Well / hover | `semantic.surface.muted` → `#F5F6F8` | Hovered rows, read-only fields |
| Top navigation | `semantic.surface.inverse` → `#111111` | Top bar |
| Top-bar hover | `semantic.surface.inverseHover` → `#2B3038` | Hovered control on the top bar |
| Accent | `semantic.surface.accent` → `#FFD100` | Primary button, brand mark, active indicator |
| Selected | `semantic.surface.accentSubtle` → `#FFFBE6` | Selected row, highlighted notice |
| Body text | `semantic.text.default` → `#111111` | Text and headings |
| Secondary text | `semantic.text.muted` → `#5B6472` | Help text |
| Caption | `semantic.text.subtle` → `#6B7280` | Placeholders, captions |
| Text on yellow | `semantic.text.onAccent` → `#111111` | Primary button label |
| Yellow on black | `semantic.text.inverseAccent` → `#FFD100` | Active top-navigation item |
| Dark yellow | `semantic.text.accentStrong` → `#7A5C00` | Yellow-hued text on white |
| Link | `semantic.text.link` → `#1D4ED8` | Links |
| Feedback | `semantic.text.{danger,success,warning,info}` | Error, success, warning, information text |
| Focus ring | `semantic.border.focus` → `#111111`, `semantic.border.focusInverse` → `#FFD100` | 2 px ring, 2 px offset |

### Accessible yellow/black pairs

The yellow brand is used for **accents on black or white**, never as text on white
(Phase 0 UX principle 11):

| Pair | Ratio | Allowed |
|---|---|---|
| Black `#111111` on yellow `#FFD100` | 12.9 : 1 | Yes — primary button, brand mark |
| Yellow `#FFD100` on black `#111111` | 12.9 : 1 | Yes — active navigation item, focus ring on the top bar |
| Dark yellow `#7A5C00` on white | 6.3 : 1 | Yes — when a yellow hue is needed for text |
| Yellow `#FFD100` on white | 1.5 : 1 | **No** — not in `contrast-pairs.json`; fails WCAG AA |

Every allowed pair is listed in `contrast-pairs.json` and checked in CI (A-10-T04).

## Contrast check

`pnpm --filter @numo9/ui run contrast` (A-10-T04) checks every pair in `contrast-pairs.json` with the
WCAG 2.1 formula and fails CI when a pair is below **4.5 : 1**. It also fails when a pair names an
unknown, non-colour or translucent token. Current result (`--markdown` output):

| Foreground | Background | Colours | Ratio | Use |
|---|---|---|---|---|
| `text.default` | `surface.default` | `#111111` on `#FFFFFF` | 18.88:1 | Body text |
| `text.default` | `surface.subtle` | `#111111` on `#FAFAFB` | 18.10:1 | Body text |
| `text.default` | `surface.muted` | `#111111` on `#F5F6F8` | 17.46:1 | Body text |
| `text.default` | `surface.accentSubtle` | `#111111` on `#FFFBE6` | 18.16:1 | Body text |
| `text.default` | `surface.dangerSubtle` | `#111111` on `#FEF3F2` | 17.37:1 | Body text |
| `text.default` | `surface.successSubtle` | `#111111` on `#ECFDF3` | 17.90:1 | Body text |
| `text.default` | `surface.warningSubtle` | `#111111` on `#FFFAEB` | 18.10:1 | Body text |
| `text.default` | `surface.infoSubtle` | `#111111` on `#EFF8FF` | 17.57:1 | Body text |
| `text.muted` | `surface.default` | `#5B6472` on `#FFFFFF` | 5.98:1 | Secondary and help text |
| `text.muted` | `surface.subtle` | `#5B6472` on `#FAFAFB` | 5.73:1 | Secondary and help text |
| `text.muted` | `surface.muted` | `#5B6472` on `#F5F6F8` | 5.53:1 | Secondary and help text |
| `text.muted` | `surface.accentSubtle` | `#5B6472` on `#FFFBE6` | 5.75:1 | Secondary and help text |
| `text.subtle` | `surface.default` | `#6B7280` on `#FFFFFF` | 4.83:1 | Placeholders, captions |
| `text.subtle` | `surface.subtle` | `#6B7280` on `#FAFAFB` | 4.63:1 | Placeholders, captions |
| `text.inverse` | `surface.inverse` | `#FFFFFF` on `#111111` | 18.88:1 | Top navigation text |
| `text.inverseMuted` | `surface.inverse` | `#D0D5DD` on `#111111` | 12.81:1 | Secondary text in the top navigation |
| `text.inverseAccent` | `surface.inverse` | `#FFD100` on `#111111` | 12.92:1 | Active navigation item: yellow on black |
| `text.inverse` | `surface.inverseHover` | `#FFFFFF` on `#2B3038` | 13.27:1 | Hovered top-navigation control |
| `text.inverseAccent` | `surface.inverseHover` | `#FFD100` on `#2B3038` | 9.08:1 | Hovered active navigation item |
| `text.onAccent` | `surface.accent` | `#111111` on `#FFD100` | 12.92:1 | Primary button: black on yellow |
| `text.onAccent` | `surface.accentHover` | `#111111` on `#FFDB33` | 13.88:1 | Primary button: black on yellow |
| `text.accentStrong` | `surface.default` | `#7A5C00` on `#FFFFFF` | 6.25:1 | Dark-yellow text on light surfaces |
| `text.accentStrong` | `surface.accentSubtle` | `#7A5C00` on `#FFFBE6` | 6.01:1 | Dark-yellow text on light surfaces |
| `text.link` | `surface.default` | `#1D4ED8` on `#FFFFFF` | 6.70:1 | Links |
| `text.link` | `surface.subtle` | `#1D4ED8` on `#FAFAFB` | 6.42:1 | Links |
| `text.danger` | `surface.default` | `#B42318` on `#FFFFFF` | 6.57:1 | Error text |
| `text.danger` | `surface.dangerSubtle` | `#B42318` on `#FEF3F2` | 6.05:1 | Error text |
| `text.success` | `surface.default` | `#067647` on `#FFFFFF` | 5.69:1 | Success text |
| `text.success` | `surface.successSubtle` | `#067647` on `#ECFDF3` | 5.40:1 | Success text |
| `text.warning` | `surface.default` | `#93370D` on `#FFFFFF` | 7.52:1 | Warning text |
| `text.warning` | `surface.warningSubtle` | `#93370D` on `#FFFAEB` | 7.21:1 | Warning text |
| `text.info` | `surface.default` | `#175CD3` on `#FFFFFF` | 5.99:1 | Information text |
| `text.info` | `surface.infoSubtle` | `#175CD3` on `#EFF8FF` | 5.57:1 | Information text |
| `border.focus` | `surface.default` | `#111111` on `#FFFFFF` | 18.88:1 | Focus ring on light and yellow surfaces |
| `border.focus` | `surface.subtle` | `#111111` on `#FAFAFB` | 18.10:1 | Focus ring on light and yellow surfaces |
| `border.focus` | `surface.muted` | `#111111` on `#F5F6F8` | 17.46:1 | Focus ring on light and yellow surfaces |
| `border.focus` | `surface.accent` | `#111111` on `#FFD100` | 12.92:1 | Focus ring on light and yellow surfaces |
| `border.focusInverse` | `surface.inverse` | `#FFD100` on `#111111` | 12.92:1 | Focus ring on the top navigation |

## Type

| Token | Value |
|---|---|
| `font.family.sans` | Inter, then the system UI stack |
| `font.family.mono` | JetBrains Mono, then the system monospace stack |
| `font.weight` | regular 400 · medium 500 · semibold 600 · bold 700 |

| Step | Size / line height | Typical use |
|---|---|---|
| `xs` | 12 / 16 px | Badges, captions |
| `sm` | 14 / 20 px | Grids, forms (default UI text) |
| `base` | 16 / 24 px | Body copy |
| `lg` | 18 / 28 px | Section titles |
| `xl` | 20 / 28 px | Card titles |
| `2xl` | 24 / 32 px | Page titles |
| `3xl` | 30 / 36 px | Dashboard figures |
| `4xl` | 36 / 40 px | Marketing headings |

Amounts use tabular figures (`font-variant-numeric: tabular-nums`) so columns of money align.

## Spacing, radius, elevation, sizes

| Group | Values |
|---|---|
| `space` (4 px grid) | 0, 2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64 px |
| `radius` | none 0 · sm 4 · md 6 · lg 8 · xl 12 · full 9999 px |
| `elevation` | 1 cards · 2 menus and popovers · 3 drawers · 4 dialogs |
| `size` | touch target 44 px · top nav 56 px · side nav 240 px · grid row 44 px (comfortable) / 32 px (compact) |
| `breakpoint` | 360 · 768 · 1024 · 1440 px |
| `motion` | 100 / 200 / 300 ms, standard easing `cubic-bezier(0.2, 0, 0, 1)`; reduced-motion disables transitions |

## Rules

1. Screens use **semantic** tokens only; primitives exist to build the semantic layer.
2. Only the pairs in `contrast-pairs.json` combine text and background; a new pair is added there
   first and must pass the contrast check.
3. Yellow is never text on white.
4. The tokens are dark-mode-ready (a dark theme overrides the `semantic` group only); no dark theme
   ships in Phase 0.
