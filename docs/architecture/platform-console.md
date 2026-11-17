# Platform console (U-06)

One console for Numo9 staff: practices and organisations, subscription states, metrics, packages,
feature flags and audited sign-in as a user. Separate shell at **`/console`** with its own accent
colour, so staff never confuse it with an organisation.

## Information architecture (U-06-T01)

| Area | Path | What | Permission |
|---|---|---|---|
| Metrics (home) | `/console` | KPI tiles (MRR, active, trials, conversion, churn, founding x/1,000) with drill-down, trends | `platform.console.view` |
| Practices | `/console/practices` | practices with staff and client counts | `platform.console.view` |
| Organisations | `/console/organisations` | filters (status, package, province, created), paged; detail with subscription timeline, users, practices, audit link | `platform.console.view` |
| Packages & prices | `/console/packages` | the U-02 editor (packages, prices, promo codes, products) | `platform.catalogue.manage` |
| Trial | `/console/trial` | trial package and length (`TrialConfig`, U-05-T01) | `platform.catalogue.manage` |
| Feature flags | `/console/flags` | per organisation, practice, % rollout, everyone | `platform.flags.manage` |
| Sign in as a user | from an organisation's detail | reason, 15 min–2 h, red bar, end | `platform.impersonate` |
| Jobs | `/console/jobs` | background jobs (A-08-T08) | `platform.jobs.view` |

Founding counter and demo manager panels arrive with U-07/U-08 (U-06-T13).

Wireframes: [design/wireframes.md §27–29](../design/wireframes.md) (and §7 for the metrics home).
