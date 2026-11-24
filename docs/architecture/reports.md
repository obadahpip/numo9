# Report engine (K-01)

One engine for every financial, tax and operational report (gap-54: never two engines).
Wireframes: sections 54–59 of [the wireframes](../design/wireframes.md).

## Definitions and the registry (K-01-T02)

A report is a `ReportDefinition` subclass in `numo9.reports`, registered with `@register`:

| Attribute / method | Meaning |
|---|---|
| `id` | Stable identifier (`trial_balance`): layouts, notes and favourites point at it |
| `slug` | The URL part (`trial-balance`) |
| `name`, `description`, `category` | The report home (K-01-T12) |
| `feature`, `permission` | The package feature (U-01) and the permission (`reports.reports.view`) it needs |
| `params` | The parameter schema: `ParamSpec(name, kind, default, choices, required)`; kinds `date`, `choice`, `bool`, `int`, `text` |
| `columns(params)` | The value columns |
| `query(organisation, params)` | The data, from the ledger |
| `rows(data, params)` | `ReportRow`s: `section`, `row`, `total` or `text`, values per column, the `drill` key of each figure |
| `totals(rows, params)` | The total rows |

`run(organisation, raw_params)` cleans the parameters (unknown names, bad dates and choices are
refused with a `reports.param.*` code), then runs `query → rows → totals` in the organisation's
context. The registry refuses a second report with the same id or slug and finds a report by
either.

Registered now: **Trial balance** (`trial_balance`) and **Account activity**
(`account_activity`). Reports read posted (and reversed) lines only — drafts and journals awaiting
approval never count.

## Parameters (K-01-T03)

`numo9.reports.parameters`:

- **Date ranges** — `resolve_range(preset, today, settings)`: this/last month, this/last quarter,
  this/last financial year, month/quarter/year to date, custom. Quarters and years follow the
  organisation's year end (`fye_month`/`fye_day`): with a 31 March year end, *last financial
  year* on 15 June 2026 is 1 April 2025 – 31 March 2026 and the first quarter is April–June.
- **Comparisons** — `comparison_ranges(base, "previous" | "prior_year", n)`: up to 12 columns.
  *Previous* steps back by whole months when the range is whole months (a month, a quarter, a
  year), otherwise by the same number of days; *prior year* is the same dates a year earlier
  (29 February → 28 February).
- **Basis** — `resolve_basis(org, override)`: the G-06 default unless the report overrides it,
  with the header label (`Basis: Cash (organisation default)` / `(this report)`).
- **Book** — `book_filter(book)`: `["both", book]`; `accounting` or `tax`.
- **Tracking** — `tracking_filter({category: [options]})`: lines whose option is one of those
  chosen, for every category chosen.

## Ledger aggregation (K-01-T04)

`numo9.reports.aggregation`:

- `period_movements(ranges, book, tracking, accounts)` → `{account_id: [net movement per range]}`
  — one grouped query with a conditional sum per range;
- `balances_at(dates, …)` → `{account_id: [balance at each date]}` (balance-sheet figures);
- posted and reversed entries only; book filter `book ∈ (both, <book>)`; tracking filter;
- lines are read by the index `(organisation, account, date, book)` on the line's own copy of
  its entry's date (`ledger_journalline.date`, filled by a database trigger on insert and kept
  equal when a draft's date changes — migration `ledger.0016`);
- `snapshot()` runs a report's queries in one **repeatable-read** read-only view of the ledger, so
  postings made while it runs never mix into it.

Performance: a 12-month aggregation of a 100,000-line organisation runs in well under 1 s
(`tests/test_report_aggregation_performance.py`; about 0.07 s on the CI database).

## Drill-down (K-01-T05)

`numo9.reports.drill.drill(org, account, date_to, date_from, book, tracking, page)` lists the
posted lines behind a figure, oldest first, 50 a page; `total` is the sum of all of them (debits −
credits) on every page and equals the figure — the same filter as the aggregation. Without
`date_from` the lines run from the start of the books (balance-sheet figures). Each line carries
its source document link: a source type registers its URL builder (`register_source`; invoices
and bank transactions now), anything else opens the journal.

API: `GET /api/v1/o/<org>/reports/<report>/drill?account=5400&from=2026-06-01&to=2026-06-30
&book=accounting&tracking=region:east&page=1` (`reports.reports.view`, gated by the report's
feature key); bad parameters → 400 with a `reports.*` code.

## Header (K-01-T06)

`numo9.reports.header.report_header(org, title, today, period | as_of, basis, book, language)`:
display name; legal name (left out when the same as the display name); period label ("1 Apr 2026
to 31 Mar 2027" or "As at 30 Jun 2026"); **"Year to date — unaudited"** when the period or the
balance date ends after today; the basis label (G-06 default or the report's override); "Accounting
book" / "Tax book".

## Legal name (K-01-T07)

The header prints the legal name, so the organisation settings refuse one that isn't a name
(`validate_organisation_legal_name`, gap-55): a number ("1001633222" →
`orgsettings.legal_name.numeric`) or fewer than two letters ("1001633222 A" →
`orgsettings.legal_name.too_few_letters`). "1001633222 Ontario Inc." and "3M Canada" are fine.
Contacts keep the plain "not only a number" rule.

## Layouts and published snapshots (K-01-T08)

`ReportLayout` (`numo9.reports.models`) keeps, per organisation and report, a named layout:
row order, labels, hidden rows, text blocks, footnotes and the parameters it runs with.
`numo9.reports.layouts`:

- `apply_layout(result, config)` — reorder, rename, hide, insert text blocks; rows the layout
  doesn't name (a new account) follow the ones it does;
- `save_draft` / `save_custom` — saved in place while not published;
- `publish(layout, user, today)` — runs the report, applies the layout and stores the result with
  its header as the **snapshot**; the layout is then frozen (`reports.layout.published`) and a
  change starts a new draft version. Later postings never change a published snapshot.

Managing layouts needs `reports.layouts.manage`.

## Cell notes (K-01-T09)

`ReportNote` keeps a note on one cell — the row's stable key (`account:5400`) and the column's key
(empty for the whole row) — for the report or for one layout. `numo9.reports.notes`: `set_note`
(an empty text removes it), `notes_for`, and `annotate(result, notes)`, which puts each note on its
row when the report runs again and lists the notes whose row isn't in this run under
`unplaced_notes` (nothing is lost when a period has no activity).

## Exports (K-01-T10)

`numo9.reports.exports` renders the **report body** — what the runner shows (`report_body`,
below): the same rows, labels, values, header and footnotes. Nothing is computed again.

| Format | What it is |
|---|---|
| PDF | Letter, 1 in margins, on the printed-document baseline (`documents/base.html`); amounts formatted like the screen (`$1,234.56`, `1 234,56 $` in French); "No activity in this period" when there are no rows |
| XLSX | Amounts as numbers (`#,##0.00`); each total is a `=SUM(…)` formula over the rows it adds up (the block above it, or every row) when they add up to it, otherwise its value; opens in Google Sheets as is |
| CSV | UTF-8 with BOM; header lines, a blank line, then the table; plain decimals |

The PDF text of the account activity report is a stored snapshot
(`tests/snapshots/report_activity_pdf.txt`).

## API (K-01-T11)

Under `/api/v1/o/<org>/`:

| Method and path | What |
|---|---|
| `GET reports` | The catalogue by category: each report's parameters, feature key, `available` (in the package), `favourite`; and the organisation's layouts as `drafts`, `published`, `custom` |
| `GET reports/<report>/run` | The report body: `header`, `columns`, `rows`, `totals`, `notes`, cell notes on their rows; the report's parameters and `preset` (this_month … custom) in the query, `layout=<id>` to apply a layout (a published one answers its snapshot) |
| `GET reports/<report>/export?file=pdf\|xlsx\|csv` | The same body as a file (`file`, because DRF keeps `format` for its renderers) |
| `GET reports/<report>/drill` | The lines behind a figure (K-01-T05) |
| `PUT`, `DELETE reports/<report>/favourite` | Star and unstar (per person) |
| `GET`, `POST reports/<report>/layouts` | The report's layouts; save a `draft` or `custom` layout |
| `GET`, `DELETE reports/layouts/<id>` | A layout with its snapshot; delete (a published layout is kept) |
| `POST reports/layouts/<id>/publish` | Publish a draft (snapshot, immutable afterwards) |
| `PUT reports/<report>/notes` | A cell note (`row`, `column`, `text`; empty removes it) |

Every endpoint needs `reports.reports.view` (layouts and notes `reports.layouts.manage`). The
views declare `@core`, and each request is gated by **the report's own feature key**
(`require_feature(report.feature)`): an accounting report needs `accounting.reports.read`, a tax
report `tax.reports.read`. A report outside the package answers **402**
`entitlement.feature_not_in_package` naming the feature and its product; the catalogue still lists
it, with `available: false`, so the report home can show the explicit gate.
