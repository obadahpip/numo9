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
