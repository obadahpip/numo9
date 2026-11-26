# Preparing and filing your GST/HST return

Numo9 prepares the GST/HST return (the CRA's GST34) for each filing period from the posted
documents and journals. The lines follow the CRA's layout, every figure that comes from the
books opens the documents behind it, and a filed return locks its period for tax.

Open **Tax → GST/HST returns** (`/o/<organisation>/tax/returns`). The page is part of every
package that includes Tax; without Tax it shows which packages include it.

| To… | You need |
|---|---|
| See returns, their lines and documents | *See GST/HST returns, their lines and documents* (`tax.returns.view`) |
| Prepare and recalculate a return | *Prepare and recalculate GST/HST returns* (`tax.returns.prepare`) |
| Review, mark as filed and amend | *Review, file and amend GST/HST returns* (`tax.returns.file`) |

## 1. Prepare

The list shows the registration's filing periods, newest first, with the status of each return.
Choose **Prepare return** on a period: Numo9 calculates the lines and opens the worksheet. The
return uses the organisation's tax basis (accrual or cash, **Settings → Tax**) and, from the date
you elected it, the quick method.

| Line | What Numo9 puts there |
|---|---|
| 101 | Taxable and zero-rated sales (net) |
| 103 | GST and HST collected or collectible (credit notes and reversals reduce it) |
| 104 / 107 | Late adjustments carried in from a filed period, plus what you type |
| 106 | The input tax credits you can claim (restricted ITCs, such as 50 % of meals, are reduced) |
| 105, 108, 109, 112, 113A, 113C | The CRA's totals |
| 110, 111, 113B | What you type: instalments, rebates, other debits |
| 114 / 115 | The refund claimed, or the payment enclosed |

Select an amount on lines 101, 103, 104, 106 or 107 to see **the documents behind it** in a side
panel: their amounts add up to the line. Type amounts on lines 104, 107, 110, 111 and 113B, then
**Save amounts**.

If documents in the period change after the return was calculated, a banner lists the lines that
moved (*Line 103: $130.00 → $156.00*). Choose **Recalculate** to take the new figures.

## 2. Review

Someone other than the person who prepared the return chooses **Mark as reviewed** — the
preparer can't review their own return. A reviewer who finds a problem chooses **Send back** and
says why; the return goes back to draft.

## 3. Mark as filed

File the return with the CRA (My Business Account, NETFILE or your representative's account), then
choose **Mark as filed** and enter the **confirmation number** the CRA gave you and the day you
filed. From then on:

- the period shows a lock in the returns list and on the filing timeline;
- the **Tax lock** moves to the period's end: a change that touches the period's sales tax is
  refused, unless it is posted as a *late adjustment* — its tax is then reported on the next open
  period's line 104 (more tax) or 107 (less tax) and listed on that return.

## Amending a filed return

Choose **Amend** on a filed return and say why. Version 2 starts as a draft with the filed figures;
recalculate it, have it reviewed and mark it as filed with its own confirmation number. The filed
version stays as it was and is marked *Amended*. A late adjustment already reported on a later
return is not counted again on the amendment.

## Exports

**PDF** prints the worksheet (Letter, 1-inch margins) with the business number, the period, the
method and, once filed, the confirmation number. **CSV** lists the lines, labels and amounts to key
into the CRA's forms. Both show exactly the lines on the screen; in French they use the CRA's
French line labels.
