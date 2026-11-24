# Invoice fixtures (D-03a-T18)

`numo9.sales.fixtures` builds a fixed set of invoices for tests, QA and demos.

- **50 invoices** over one customer per province and territory (13), billed there, so each gets its
  own tax: HST (ON, NB, NL, NS, PE), GST + PST (BC, MB, SK), GST + QST (QC), GST alone (AB, NT, NU,
  YT).
- Lines: the province's standard rate on every invoice; a zero-rated line (basic groceries) on
  every fourth and an exempt line on every fifth; a 10 % line discount on every sixth.
- Status: every seventh invoice stays a **draft**; the rest are approved (posted), and every tenth
  approved invoice is then **voided** — 39 approved, 7 drafts, 4 void.
- Amounts follow the invoice's position, so every run gives the same totals:
  `backend/tests/snapshots/invoice_fixtures.txt` pins number, province, status, subtotal, tax and
  total of each (`UPDATE_SNAPSHOTS=1` rewrites it after a deliberate change).
- The builder adds the PST and QST control accounts the chart lacks (an Ontario chart has
  neither).

**PDF fixtures** — `render_pdf_fixtures(invoices, directory)` writes one PDF per province (its first
approved invoice), for comparing with the client's own invoice samples.

```
python manage.py seed_invoice_fixtures <organisation public id> [--user EMAIL] [--pdf-dir DIR]
```

Tests: `backend/tests/test_invoice_fixtures.py`.
