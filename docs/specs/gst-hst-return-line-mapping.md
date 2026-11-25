# GST/HST return — line mapping (G-03-T01)

Status: draft for sign-off by the client's accountant. The return calculator (G-03-T03, regular
method) and the quick-method calculator (G-03-T04) implement this mapping exactly; the
compliance fixtures (G-03-T14) use the worked examples below as their cases.

The return is the CRA **GST34** (Goods and Services Tax/Harmonized Sales Tax Return for
Registrants) for one **filing period** of one GST/HST registration (RT program account), the
periods coming from the filing-cycle engine (G-03a). Quebec's QST is filed on Revenu Québec's
return and provincial PST/RST with each province: neither feeds the GST34.

## 1. What is read

| Input | Where it comes from | Rule |
|---|---|---|
| Posted tax lines | `ledger_journalline` lines on the GST/HST payable and GST/HST receivable (ITC) control accounts, and the net lines of the same journals | Posted (and reversed) journals only; drafts never count |
| Tax-point date | The document date (invoice, bill, spend/receive money, credit note); for a revision (D-03b) the revision's date | A line belongs to the period that contains its tax-point date (`period_for`, G-03a-T14) |
| Basis | Tax settings (G-06): accrual or cash | Accrual: the document date. Cash: the payment or receipt date, in proportion to what was paid in the period |
| Component kind | The tax component of each line (G-01): `gst`, `hst`, `pst`, `qst` | Only `gst` and `hst` feed lines 103 and 106; `pst` and `qst` never do |
| Tax code type | `taxable`, `zero_rated`, `exempt`, `out_of_scope` | Decides line 101 (below) |
| Instalments | G-09 instalment payments (Phase 4); until then a manual entry on the return | Line 110 |
| Rebates | Manual entry on the return (Schedule A/B rebates) | Line 111 |
| Late adjustments | Documents dated inside a **filed** period and posted with `late_adjustment` (G-03-T08) | Their tax delta goes to the next open period: increase → 104, decrease → 107 |

## 2. Regular method — lines 101 to 115

| Line | CRA label (EN / FR) | Calculation | Source in Numo9 |
|---|---|---|---|
| 101 | Sales and other revenue / Ventes et autres recettes | Σ net amount (before tax, after discounts) of **sales** lines whose tax code type is `taxable` or `zero_rated`, minus the same on sales credit notes. Exempt and out-of-scope supplies are **excluded**. GST/HST itself is excluded. Rounded to whole dollars on the CRA form (Numo9 keeps cents and rounds on export only) | Sales documents' lines by tax code type |
| 103 | GST/HST collected or collectible / TPS/TVH perçue ou à percevoir | Σ GST + HST components of sales lines, minus those of sales credit notes = net **credits** to GST/HST payable from sales-side journals | GST/HST payable control account, sales journals |
| 104 | Adjustments to be added to the net tax / Redressements à ajouter à la taxe nette | Late-adjustment increases (G-03-T08) + manual adjustments entered on the return (e.g. recaptured ITCs, bad debt recovered) | Late-adjustment register + return entries |
| 105 | Total GST/HST and adjustments for period / Total de la TPS/TVH et des redressements | **103 + 104**. Equals the G-05 tax report's "collected" total for the period (deliverable acceptance) | Calculated |
| 106 | Input tax credits (ITCs) / Crédits de taxe sur les intrants (CTI) | Σ **claimable** GST + HST of purchase lines (bills, spend money, expense claims), minus supplier credits = net **debits** to GST/HST receivable (ITC). The claimable share follows G-01-T05 (account restriction — 50 % meals and entertainment —, tax code restriction, component); nothing before the RT registration's start (E-02-T04) | GST/HST receivable (ITC) control account, purchase journals |
| 107 | Adjustments to be deducted / Redressements à déduire | Late-adjustment decreases (G-03-T08) + manual adjustments (e.g. bad debts written off, volume discounts given) | Late-adjustment register + return entries |
| 108 | Total ITCs and adjustments / Total des CTI et des redressements | **106 + 107** | Calculated |
| 109 | Net tax / Taxe nette | **105 − 108** (negative = refund position) | Calculated |
| 110 | Instalments and other annual filer payments / Acomptes provisionnels et autres paiements | Instalments paid for the period's fiscal year (annual filers, G-03a-T09) | G-09 (manual until Phase 4) |
| 111 | Rebates / Remboursements | Rebates claimed with this return | Manual entry |
| 112 | Total other credits / Total des autres crédits | **110 + 111** | Calculated |
| 113 A | Balance (line 109 minus line 112) / Solde | **109 − 112** | Calculated |
| 113 B | Other debits (from Schedule A) / Autres débits | Schedule A amounts (builders' self-assessment, real property); 0 in Phase 1, manual entry | Manual entry |
| 113 C | Balance (line 113 A plus line 113 B) / Solde | **113 A + 113 B** | Calculated |
| 114 | Refund claimed / Remboursement demandé | **−113 C** when 113 C < 0, else 0 | Calculated |
| 115 | Payment enclosed / Paiement joint | **113 C** when 113 C > 0, else 0 | Calculated |

Lines 102 (not used since 2014), 205 and 405 (real property — Schedule A) are not produced in
Phase 1; a nil return has every line at 0.00 and is filed like any other.

## 3. Quick method (G-03-T04)

When the registration elects the quick method (tax settings, G-06):

| Line | Calculation |
|---|---|
| 101 | Σ sales **including** GST/HST of `taxable` supplies (zero-rated and exempt supplies, sales of capital property excluded) |
| 103 | Σ (eligible supplies incl. tax × the **remittance rate** for the supply's province and the registrant's type — service or goods), less the **1 % credit** on the first $30,000 of eligible supplies (incl. tax) of the fiscal year; rates are effective-dated data, never code |
| 106 | ITCs on **capital** purchases only (accounts flagged capital asset); operating expenses give no ITC under the quick method |
| other lines | As the regular method |

## 4. Worked examples (the fixtures of G-03-T14)

Ontario registrant, monthly filer, period 1–30 June 2026, accrual basis:

| Document | Amount | Tax code | Feeds |
|---|---|---|---|
| Invoice INV-0001 | 1,000.00 + HST 130.00 | `sales.ON.standard` | 101 += 1,000.00; 103 += 130.00 |
| Invoice INV-0002 | 200.00 (basic groceries) | `sales.zero_rated` | 101 += 200.00 |
| Invoice INV-0003 | 50.00 (exempt service) | `sales.exempt` | — |
| Bill BILL-0001 | 400.00 + HST 52.00 | `purchase.ON.standard` | 106 += 52.00 |
| Bill BILL-0002 (meals) | 100.00 + HST 13.00, 50 % restricted | `purchase.ON.standard` on Meals | 106 += 6.50 (6.50 is a cost) |
| BC bill | 100.00 + GST 5.00 + PST 7.00 | `purchase.BC.standard` | 106 += 5.00 (PST never) |

Result: 101 = 1,200.00 · 103 = 130.00 · 104 = 0.00 · 105 = 130.00 · 106 = 63.50 · 107 = 0.00 ·
108 = 63.50 · 109 = 66.50 · 110 = 0.00 · 111 = 0.00 · 112 = 0.00 · 113 A = 66.50 · 113 B = 0.00 ·
113 C = 66.50 · 114 = 0.00 · **115 = 66.50**.

Refund case: the same period without INV-0001 → 103 = 0.00, 109 = −63.50, **114 = 63.50**.

Late adjustment: after June is filed, a 100.00 + HST 13.00 invoice dated 20 June is posted
with the late-adjustment flag → it is not in the filed June return; July's line 104 shows 13.00
and lists the invoice.

## 5. Rounding and signs

- Every amount is a decimal with two places; lines are sums of already-rounded line taxes (the
  document calculator rounds per line, D-01), so line 103 equals the sum of the documents' tax.
- Credit notes and supplier credits reduce the lines they mirror (never a negative line 106 from
  a sale).
- The CSV export (G-03-T13) gives cents; the PDF shows cents; CRA's form rounds to dollars for
  line 101 only.

## Sign-off

| Role | Name | Date |
|---|---|---|
| Client's accountant | | |
| Product owner | | |
