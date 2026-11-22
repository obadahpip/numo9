# LineGrid — the shared document line editor (A-10-T11)

`LineGrid` (`packages/ui/src/line-grid/`) is the one line editor of every document: the journal
now (C-02 / C-04), and in Phase 1 the invoice, quote, recurring invoice and credit note (D-01) and
the bill and purchase order (E-02). One grid closes gap-01 (two UI generations, editors that
behave differently) and keeps the keyboard model identical everywhere.

## What LineGrid does (Phase 0)

| Area | Behaviour |
|---|---|
| Columns | `text`, `money` (decimal string, forgiving input via `parseMoney`) and `custom` cells (`render` gets id, accessible label, value, setter, key handler). Optional columns are chosen in the column chooser (`optional: true`); `defaultHiddenColumns` hides them initially. |
| Keyboard | Tab / Shift+Tab: next / previous cell. ↑ / ↓: same column, previous / next line. Enter: next line; on the last line, adds a line and focuses the same column. Alt+Shift+↑ / ↓ (or Alt+↑ / ↓ on the drag handle): move the line. Alt+↓ in a cell: open its list or calendar. A combobox cell with its list open keeps the arrow keys. |
| Lines | "Add a line"; delete per line (disabled at `minLines`); drag handle reorders with the mouse; every reorder is announced in a live region. |
| Totals | `total: true` money columns are summed exactly (`sumDecimals`, BigInt — never floats) and shown in the locale format in the footer row. `footer(totals)` adds document-specific content (the journal balance indicator). |
| Accessibility | Each cell control is named "‹column›, line ‹n›"; table header cells; axe-clean (Vitest). |
| i18n | No text of its own: every label (`LineGridLabels`) is passed in by the app. |

### Journal configuration — `JournalLines`

Account (`AccountPicker`) · Description · Tax code (optional, hidden) · Debit · Credit. A line holds
a debit or a credit — typing one clears the other. Minimum 2 lines. The balance indicator is a
live region: "Balanced — debits equal credits." or, per microcopy §3.5, "Debits ($1,250.00) and
credits ($1,200.00) differ by $50.00. Adjust a line so the difference is $0.00."
`journalBalance(lines, totals)` returns the same figures for the Post button (C-02 / C-04).

## What D-01 (sales) and E-02 (purchases) add on top

| Column set | Columns (in order) | Pickers / rules |
|---|---|---|
| Invoice, quote, recurring invoice, credit note (D-01) | Item · Description · Qty · Unit price · Line discount (amount or %) · Account · Tax code · Tax amount · Amount | `AccountPicker types={["revenue"]}` (other income added with C-01 sub-types); tax picker filtered to sales codes effective on the document date (G-01); Amount and Tax amount are `total` columns. |
| Bill, purchase order (E-02) | Item · Description · Qty · Unit cost · Account · Tax code · Tax amount (ITC) · Amount | `AccountPicker types={["expense", "asset"]}`; purchase tax codes only; partial ITC shown per line. |

### Document configuration — `DocumentLines` (D-01-T11)

Item (optional column) · Description · Qty · Unit price · Discount (optional; `10%` or `5.00`,
`parseLineDiscount`) · Account (`AccountPicker`) · Tax code (`TaxCodePicker`, side and date) · Tax
amount · Amount. Tax amount and Amount are read-only, calculated columns (`readOnly: true`),
shown from the `amounts` the editor gets from the DocumentCalculator (the client mirror, replaced
by the server's result) and totalled in the footer. The table has `role="grid"`.

| Key | Action |
|---|---|
| Ctrl+D | Duplicate the line under it (announced: "Line 3 duplicated"); focus stays in the column. |
| Ctrl+Backspace | Delete the line; a toast offers Undo (`onLineRemoved` → restore at the same place). The last line stays. |

**Column choice (D-01-T13).** `columnStore` keeps the hidden columns per user and grid —
`localColumnStore("numo9.lines.<user>.<grid>")` in the browser, so the choice survives sign-out
and sign-in on the device (a server store, as the directory's saved views, can replace it without
changing the grid). When a hidden column holds values, a note under the grid says so
(`labels.hiddenWithValues`) with a Show button.

**Tablets (D-01-T16).** With `stacked` (DocumentLines sets it), at ≤ 1024 px each line is a card
with its field labels (two columns, one below 768 px); the table keeps explicit grid, row and cell
roles so screen readers still hear rows and cells, and the column headers stay for them only.

## Spec parity (D-01-T18)

Every state of the document grid has a Storybook story (`Data/LineGrid`, `Forms/Pickers`); axe and
visual regression run on all of them (A-10-T18/T19), keyboard and paste flows in
`packages/ui/e2e/document-lines.spec.ts` and `due-date.spec.ts`.

| Spec item (this page, D-01 plan) | Story | Checked by |
|---|---|---|
| Columns Item · Description · Qty · Unit price · Discount · Account · Tax code · Tax amount · Amount | Document lines (D-01) | Vitest column order |
| Empty document, keyboard-only entry | Document lines — empty | Playwright: 5 lines by keyboard |
| Sales pickers: no expense accounts, no purchase codes, no ended rates (gap-07) | Document lines (D-01) | Vitest + Playwright |
| Purchase side (E-02): expense accounts, purchase codes | Document lines — purchases | axe, visual |
| "Why this tax" tooltip | Document lines (D-01) | Vitest, Playwright |
| Ctrl+D / Ctrl+Backspace with Undo toast | Document lines (D-01) | Vitest, Playwright |
| Column chooser saved per user, hidden-column note | Document lines (D-01) | Vitest, Playwright |
| Paste from a spreadsheet, flagged cells | Document lines — empty | Playwright: 20 rows |
| Server problems flagged per cell (D-01-T06) | Document lines — server problems | Vitest |
| Read-only (sent document) | Document lines — read-only | Vitest |
| Tablet line cards ≤ 1024 px | Document lines (D-01) at 768 px | Playwright screenshot |
| Totals: discount, tax per component, live total | Document totals; — tax inclusive | Vitest |
| Required due date, term chips, "due in N days" | Forms/Pickers › Due Date | Vitest, Playwright |

Design review: the stories are the reference until the Figma frames for the invoice editor
(D-03a) exist; a change to a story is reviewed in its visual-regression diff.

Planned extensions (later D-01 tasks): paste from a spreadsheet (TSV), document-level discount and the
tax-per-component totals panel, server-authoritative calculation (`DocumentCalculator`) with the
frontend mirror wiring, per-user column-chooser persistence, and the stacked line-card layout at ≤ 1024 px.

## Using it

```tsx
<LineGrid
  lines={lines}
  onChange={setLines}
  columns={[
    { id: "description", header: t("lines.description"), kind: "text" },
    { id: "amount", header: t("lines.amount"), kind: "money", total: true, width: 140 },
  ]}
  newLine={() => ({ id: crypto.randomUUID(), description: "", amount: null })}
  labels={lineGridLabels}
  locale={locale}
/>
```
