# Demo dataset specification — seed v1 (U-07-T01)

The sample data every demo organisation opens with. It is a **fictional** Ontario retail company;
every name, address, phone number, email and Business Number below is invented (emails use the
reserved `example` domain, BNs only pass the check digit). The machine-readable source is
`backend/numo9/demo/seed/demo_seed_v1.json`; the seeders (U-07-T04) build it through the services,
so every ledger invariant holds (trial balance = 0 is checked in CI).

Status: **awaiting client sign-off** — see the sign-off record at the end.

## Company

| Field | Value |
|---|---|
| Display name | Maple & Pine Supply Co. |
| Legal name | Maple & Pine Supply Co. Ltd. |
| Industry | Building supplies retail |
| Structure | Corporation |
| Address | 77 Front St E, Toronto, ON M5E 1B8 |
| Phone / email / website | 416-555-0123 · hello@mapleandpine.example · https://mapleandpine.example |
| Fiscal year end | 31 December |
| Business Number | 680342474 (GST/HST RT0001) |
| Time zone | America/Toronto |

## Chart of accounts

The standard Canadian template `ca_v1` (C-01) for home province ON — the same chart
a new organisation in Ontario gets, so the demo shows exactly what a real one will.

## Contacts — 25 across 6 provinces

Customers in ON, QC, BC, AB, NS and MB; suppliers in each of those provinces; one contact is both
(customer and supplier). Each contact has a billing address and a primary person.

| Key | Name | Roles | City | BN |
|---|---|---|---|---|
| c01 | Lakeshore Hardware Ltd. | customer | Toronto, ON | 151743408 |
| c02 | Rideau Home & Garden Inc. | customer | Ottawa, ON | 483975686 |
| c03 | Niagara Patio Supply Co. | customer | St. Catharines, ON | — |
| c04 | Huron Builders Co-operative | customer | London, ON | — |
| c05 | Sudbury Paint & Décor | customer | Sudbury, ON | — |
| c06 | Quincaillerie Saint-Denis inc. | customer | Montréal, QC | 293183893 |
| c07 | Les Entreprises Beauport ltée | customer | Québec, QC | — |
| c08 | Gatineau Rénovation | customer | Gatineau, QC | — |
| c09 | Coastal Timber Homes Ltd. | customer | Vancouver, BC | 720800283 |
| c10 | Okanagan Outdoor Living | customer | Kelowna, BC | — |
| c11 | Island Cedar Works | customer | Victoria, BC | — |
| c12 | Prairie Fence & Deck Inc. | customer | Calgary, AB | 596440735 |
| c13 | Edmonton Builders Supply | customer | Edmonton, AB | — |
| c14 | Harbourview Contracting Ltd. | customer | Halifax, NS | 229230750 |
| c15 | Annapolis Valley Gardens | customer | Kentville, NS | — |
| c16 | Red River Renovations | customer | Winnipeg, MB | — |
| c17 | Great Lakes Lumber Ltd. | supplier | Hamilton, ON | 708260286 |
| c18 | Canadian Fastener Distributors Inc. | supplier | Mississauga, ON | 903706422 |
| c19 | Laurentian Paint Co. | supplier | Laval, QC | 768769663 |
| c20 | Pacific Tool Imports Ltd. | supplier | Richmond, BC | 917370314 |
| c21 | Prairie Freight Lines | supplier | Red Deer, AB | — |
| c22 | Maritime Garden Wholesale | supplier | Dartmouth, NS | 125712232 |
| c23 | Manitoba Hydro-Style Lighting | supplier | Brandon, MB | — |
| c24 | Toronto Hydro Services (sample) | supplier | Toronto, ON | — |
| c25 | Northern Insurance Brokers Inc. | supplier, customer | Barrie, ON | 789984531 |

## Opening trial balance — 2026-01-01

One journal, "Opening balances at 1 January 2026", posted in both books. Receivable and payable
lines name their contact, so the AR and AP sub-ledgers agree with the control accounts.

| Account | Debit | Credit | Contact |
|---|---:|---:|---|
| 1010 | 48250.00 |  |  |
| 1100 | 8640.00 |  | c01 |
| 1100 | 6200.00 |  | c06 |
| 1100 | 3800.00 |  | c12 |
| 1200 | 62300.00 |  |  |
| 1300 | 2400.00 |  |  |
| 1620 | 15000.00 |  |  |
| 1621 |  | 3000.00 |  |
| 1630 | 6800.00 |  |  |
| 1631 |  | 2720.00 |  |
| 2000 |  | 7480.00 | c17 |
| 2000 |  | 5000.00 | c19 |
| 2100 |  | 3215.00 |  |
| 2700 |  | 40000.00 |  |
| 3000 |  | 100.00 |  |
| 3200 |  | 91875.00 |  |
| **Total** | **153,390.00** | **153,390.00** | |

## Later phases

Phases 1–4 extend the seed (invoices including a revision 101-1, bills, bank transactions, payroll
employees, assets, two filed GST/HST periods, both books): see `docs/specs/demo-seed-contract.md`
(U-07-T14). Each extension bumps the seed version; demo templates rebuild on the new version.

## Sign-off record

| Date | Client representative | Decision | Notes |
|---|---|---|---|
| — | — | Pending | Dataset sent for review with this document (client input, Phase 0 day 5). |
