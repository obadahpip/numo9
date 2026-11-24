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
