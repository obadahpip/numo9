# Demo seed extension contract — Phases 1–4 (U-07-T14)

Every module that adds sample data to the demo organisation follows this contract. Phase 0's
seeders (`backend/numo9/demo/phase0.py`) are the reference implementation; the framework is
`backend/numo9/demo/seeders.py` (U-07-T03), the cloner `cloning.py` (T05), reset `reset.py` (T06).

## 1. Register a seeder

```python
from numo9.demo.seeders import Seeder, register

register(
    Seeder(
        "sales_invoices",                 # unique key
        seed_sales_invoices,              # run(ctx: SeedContext) -> None
        after=("contacts", "chart"),      # seeders it needs first
        models=(                          # tables it creates rows in, parents before children
            "sales.Invoice",
            "sales.InvoiceLine",
            "sales.InvoiceRevision",
        ),
    )
)
```

Register it from the module's `AppConfig.ready()` (import of a `demo_seed` module), never from
`numo9.demo` itself: the demo app must not import later-phase modules.

## 2. Rules every seeder follows

1. **Through the services.** Create rows with the module's own services and model saves — the
   same path a user's action takes (posting through `ledger.services.post_journal`, numbers from
   the numbering sequences, validation on save). Never raw SQL or `bulk_create` in a seeder.
2. **From the seed document.** Every value comes from `ctx.seed` (`demo_seed_v<N>.json`): no
   random data, no `today()` — dates are fixed in the seed so every demo is identical and the
   pristine hash is stable.
3. **References through `ctx.refs`.** Read what earlier seeders made (`ctx.refs["contacts"]["c01"]`,
   `ctx.refs["accounts"]["1100"]`) and publish what later ones need under the module's key.
4. **List every table.** `models` must list every organisation-owned table the seeder writes,
   including rows created indirectly (numbering sequences, revision rows, sub-ledger rows). The
   cloner refuses a seed row that points at an organisation table that is not listed.
5. **User-data tables.** Tables the visitor can add rows to that are *not* seeded go to
   `numo9.demo.reset.register_reset_tables(...)`, parents first, so a reset wipes them.
6. **Ledger invariants.** After all seeders run, the trial balance of both books is zero and every
   control account agrees with its sub-ledger (AR/AP aging = statement totals, B-02-T13).
7. **No outside effects.** No email (a demo's email goes to `DemoOutbox` anyway), no Stripe, no
   provider calls, no files outside the organisation's storage prefix.
8. **Bump the version.** Any change to the seed document or a seeder bumps `SEED_VERSION` and adds
   `demo_seed_v<N+1>.json`; the template for the new version is built on first use and existing
   demos move to it at their next reset.
9. **Tests.** Each seeder ships a data-validation test like `tests/test_demo_phase0_seed.py`
   (seed complete, trial balance zero) and the clone/reset hash tests keep passing.

## 3. Required seed items per phase

| Phase | Module | Required sample data | Checks |
|---|---|---|---|
| 0 | Settings, C-01, B-01, C-02 | Company profile and BN; Canadian chart (ON); 25 contacts in 6 provinces with people and addresses; opening-balances journal | TB = 0 (done, U-07-T04) |
| 1 | D (sales) | 12 sales invoices over 3 months across ON/QC/BC/AB customers (HST, GST+QST, GST+PST), one **revised to 101-1** with the reversal and re-posting, 2 credit notes, partial and full receipts, one overdue | AR aging = statements; revision chain; TB = 0 |
| 1 | D (purchases) | 10 bills from the suppliers incl. one with 3-way match (PO, receipt, bill), 1 supplier credit, payments; one supplier statement for reconciliation | AP aging = sub-ledger |
| 1 | E (bank) | 2 bank accounts (chequing, credit card) with 60 imported transactions, bank rules, reconciled to one statement date, a negative-balance warning example | Reconciled balance = statement |
| 1 | G (sales tax) | GST/HST registration (quarterly), **two filed periods** with their returns and one open period | Return totals = ledger |
| 2 | Inventory | 15 items (tracked and untracked), opening stock, a stock adjustment | Stock valuation = inventory account |
| 2 | Fixed assets / CCA | 4 assets in classes 8, 10, 12, 50 with SL and DB methods, half-year rule example, one disposal | CCA schedule = tax book |
| 3 | Payroll | 5 employees (ON and QC), two completed pay runs with CPP/QPP, EI/QPIP, tax; remittance | Pay stubs = journals = CRA calculator fixture |
| 3 | Two books / tax | Tax-book adjustments reconciling accounting net income to net income for tax purposes; computed tax | Reconciliation ties |
| 4 | Practice & portal | Portal user for one customer, an online-paid invoice (sandbox), working papers sample | No real payment provider call |

Each later-phase row is a separate seeder (or a few), registered by its module with the
dependencies above (e.g. bank after sales and purchases so receipts and payments exist to match).
