# Expense claims

An expense claim pays an employee back for what they spent for the business: receipts and the
kilometres they drove in their own vehicle. Expense claims are part of Accounting — there is no
add-on to buy.

## Who can do what

| Person | Can |
|---|---|
| Everyone in the organisation (the **Employee** role included) | enter, submit and see **their own** claims |
| Someone with *See expense claims* (Owner, Admin, accountants, Purchasing, reviewers) | see everyone's claims |
| Someone with *Enter and submit expense claims for others* | enter a claim on someone else's behalf |
| Someone with *Approve or reject expense claims* and an expense-claim approval limit | approve or reject |

Nobody approves a claim they are the claimant of, entered or submitted — someone else must.
Someone else's claim simply doesn't exist for a person who can only see their own.

## Entering a claim (on your phone or computer)

**Purchases → Expense claims → New expense claim.** The form is one card per receipt or trip;
on a phone the cards stack and the buttons stay at the bottom of the screen.

- **Receipt** — the date, the merchant and the **amount you paid, tax included**. Pick the
  **category** from the chips: the ones you use most come first; the rest are under *More
  categories*. The tax code is your province's standard one; change it for a receipt from
  another province, or choose *No tax* for a foreign receipt. **Take a photo or choose a file**
  opens the camera on a phone (photos and PDF, up to 25 MB). If the same file was uploaded
  before you are told, so it isn't claimed twice (the approver sees the warning too).
- **Trip** — the date, where from and where to, and the kilometres. The amount at the CRA rate
  appears as you type: the per-kilometre allowance set by the Income Tax Regulations for the
  year of the trip — in 2026, 73 ¢ a km for the first 5,000 business km in the calendar year
  and 67 ¢ after (4 ¢ more in the territories). The kilometres you already claimed this year
  count, so a trip that crosses 5,000 km is split between the two rates.

**Save draft** keeps the claim to finish later. **Submit for approval** sends it: it takes its
number (`EXP-0001`) and waits for an approver. A receipt above the amount your organisation
sets for *receipts required above* needs its photo before the claim can be sent.

## Approving

Claims waiting for approval are in the approvals inbox of the people whose expense-claim limit
covers them. The claim shows each receipt with its tax and the part you can claim back (ITC),
each trip with its rate tiers, and any duplicate-receipt warning. **Reject** needs a reason; the
claimant corrects the claim and submits it again (it keeps its number).

## The reimbursement bill

Approving a claim creates and posts a **bill to the employee** at once:

- the employee's contact is found from their earlier claims or their email, or created with the
  *Employee* role;
- one line per receipt or trip, tax included; the bill's supplier invoice number is the claim
  number, so a claim is never billed twice;
- the journal: **Dr** each category (the amount before tax plus any tax that can't be claimed —
  half of the tax on meals and entertainment, all of it before a GST/HST registration), **Dr**
  GST/HST receivable (ITC) or QST receivable for the claimable tax, **Cr Unpaid expense claims**
  (2050) — not Accounts payable, so what you owe employees stays separate from suppliers.

The bill is *Awaiting payment*; pay it with a bank payment or in a payment batch. If the day of
approval is in a locked period (the AP lock date), the approval is refused and nothing changes.
