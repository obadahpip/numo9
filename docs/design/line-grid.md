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

Planned extensions (D-01 tasks, not in Phase 0): `Ctrl+D` duplicate line, `Ctrl+Backspace` delete
with an Undo toast (`useToast`), paste from a spreadsheet (TSV), document-level discount and the
tax-per-component totals panel, server-authoritative calculation (`DocumentCalculator`) with the
frontend mirror, per-user column-chooser persistence, and the stacked line-card layout at ≤ 1024 px.

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
