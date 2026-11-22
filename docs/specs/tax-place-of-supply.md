# Place-of-supply decision table (G-02-T01)

Status: draft for sign-off by the client's accountant. The resolver
(`numo9.tax.place_of_supply.resolve`, G-02-T02) implements this table exactly; the table-driven
tests in `backend/tests/test_tax_place_of_supply.py` use the rows below as their cases.

## 1. Precedence

A line's tax code is the first of these that gives one:

| # | Source | Notes |
|---|---|---|
| 1 | Line override | What the person picked on the line. Shown with a "changed from default" dot; resetting it re-runs the resolver. |
| 2 | Item tax setting | The item's sales or purchase code (H-01 — a hook until items exist). Used for exempt services and zero-rated basic groceries. |
| 3 | Contact explicit default | A code set on the contact itself (none in Phase 1; reserved). |
| 4 | Place-of-supply resolver | Sections 2–4 below. |
| 5 | Account default | The account's `default_tax_key` (G-01-T09). |

"Last used" is never read. The same inputs always give the same code.

## 2. Province of supply

1. The line's ship-to address (document ship-to, else the contact's shipping address), when it
   has a country;
2. else the contact's billing address;
3. else the organisation's home province (physical, else mailing address), with the
   `missing_province` flag so the editor can hint that the contact has no address.

Outside Canada (country ≠ CA) is an export. A US customer with a Canadian ship-to is supplied in
the ship-to province (the ship-to wins).

## 3. Sales side

R = the organisation's registrations in force on the document date (A-05-T03,
`status = active` and the date inside `effective_from`–`effective_to`).

| Province of supply | RT (GST/HST) | Provincial registration | Code | Explanation key | Warnings |
|---|---|---|---|---|---|
| ON, NS, NB, NL, PE | active or not recorded | — | `sales.<PROV>.standard` (HST) | `tax.pos.hst` | — |
| AB, NT, NU, YT | active or not recorded | — | `sales.<PROV>.standard` (GST) | `tax.pos.gst` | — |
| BC | active or not recorded | PST_BC active | `sales.BC.standard` (GST + PST) | `tax.pos.gst_pst` | — |
| BC | active or not recorded | none | `sales.BC.gst` (GST only) | `tax.pos.gst_unregistered_pst` | `tax.pos.pst_unregistered` |
| SK | active or not recorded | PST_SK active | `sales.SK.standard` | `tax.pos.gst_pst` | — |
| SK | active or not recorded | none | `sales.SK.gst` | `tax.pos.gst_unregistered_pst` | `tax.pos.pst_unregistered` |
| MB | active or not recorded | RST_MB active | `sales.MB.standard` | `tax.pos.gst_pst` | — |
| MB | active or not recorded | none | `sales.MB.gst` | `tax.pos.gst_unregistered_pst` | `tax.pos.pst_unregistered` |
| QC | active or not recorded | QST active | `sales.QC.standard` (GST + QST) | `tax.pos.gst_qst` | — |
| QC | active or not recorded | none | `sales.QC.gst` | `tax.pos.gst_unregistered_qst` | — (info only) |
| Outside Canada | any | any | `sales.zero_rated` | `tax.pos.export` | — |
| any | ended before the date (G-03b stop) | any | `sales.out_of_scope` | `tax.pos.deregistered` | `tax.pos.deregistered` |

Notes:

- "Not recorded" — an organisation that has not entered its RT number is treated as registered:
  registrations are optional data in Phase 1, and charging no GST by default would be the more
  harmful mistake. Only an RT registration that *ended* before the document date (G-03b) gives
  out-of-scope.
- The PST warning is raised only for a *taxable* line (not for zero-rated or exempt items).
- A pending registration (`status = pending`) does not count as active.

## 4. Purchase side

| Source | Code |
|---|---|
| Item purchase code (H-01) | that code |
| Account default (`default_tax_key`, purchase side) | that code — e.g. meals → `purchase.<PROV>.standard.itc50` |
| Supplier province (billing address) | `purchase.<PROV>.standard` |
| Supplier outside Canada | `purchase.out_of_scope` (imported services: self-assessment is out of scope for Phase 1) |
| Supplier with no address | `purchase.<home province>.standard` with `missing_province` |

On purchases the account default comes before the supplier's province: the account is the
better signal of what was bought (gap-45). Provincial registration does not change purchase
codes — a supplier charges PST whether or not the buyer is registered.

## 5. Documented simplifications

- Services and intangibles are supplied where the customer's address is (no "primarily
  performed in" or "used in" tests). The person overrides the line when a different province
  applies; the override is visible and audited.
- Zero-rated supplies other than exports (basic groceries, prescription drugs) come from the
  item setting, never from the resolver.
- Cross-border digital-economy rules, imported-services self-assessment and the QST on
  out-of-province suppliers are outside Phase 1.

## 6. Examples (also test cases)

| Case | Inputs | Result |
|---|---|---|
| Ontario customer | sales, ON billing | `sales.ON.standard`, HST 13 % |
| US customer | sales, US billing | `sales.zero_rated` |
| Quebec, QST registered | sales, QC, QST active | `sales.QC.standard` (GST + QST) |
| Quebec, not QST registered | sales, QC, no QST | `sales.QC.gst` + info |
| BC, no PST registration | sales, BC, taxable | `sales.BC.gst` + PST warning |
| US customer, Toronto ship-to | sales, US billing, ON ship-to | `sales.ON.standard` |
| Contact without address | sales, no address, org in AB | `sales.AB.standard` + `missing_province` |
| After deregistration | sales, RT ended 30 Jun, dated 15 Jul | `sales.out_of_scope` + warning |
| Meals bill from Ontario | purchase, meals account itc50 key, ON supplier | `purchase.ON.standard.itc50` |
| Expense account, ON supplier | purchase, account key `purchase.ON.standard` | `purchase.ON.standard` |

## Sign-off

| Role | Name | Date |
|---|---|---|
| Client's accountant | | |
| Product owner | | |
