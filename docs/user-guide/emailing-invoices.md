# Emailing invoices

An approved invoice is emailed from **Email invoice** (`/o/<org>/sales/invoices/<id>/email`).

## The composer

- **To** starts with the customer's people marked *Include in emails* (the primary person first).
  Add or remove addresses, separated with commas. Addresses that aren't valid are named before
  anything is sent.
- **Subject** and **Message** start in the customer's language (English or French). Change them
  as needed; the message appears above the amount due and a **View invoice** button.
- The PDF is attached — the same PDF as **Preview PDF** shows beside the form.
- A draft or an invoice waiting for approval can't be emailed: approve it first.

Each recipient gets their own email. When the invoice is first emailed, an approved invoice
becomes **Sent**.

## After sending

**Sent before** lists every send (when, to whom) and whether the customer has opened the
invoice: *Viewed* with the date of the first view, or *Not viewed yet*. A view is recorded when
the customer opens the **View invoice** link of the email; the attached PDF opened from their
email app isn't counted.

If an address bounces, the contact person's email is flagged *Bounced* on the contact and Numo9
stops emailing that address for 30 days. Fix the address on the contact and send again.

Every send and the first view are in the invoice's history (audit log: *sales.invoice.sent*,
*sales.invoice.viewed*).

## Credit limits in the invoice editor

When the customer has a credit limit, the editor shows where the invoice leaves them:

- **Over the credit limit** (warn mode): the amount they would owe and by how much it's over.
  You can still approve the invoice.
- **Credit limit reached** (block mode): the invoice can't be approved until an override is
  approved for it. **Request override** asks for a reason and notifies the people who may approve
  overrides; the banner then says the request is waiting. Someone else approves it from the
  contact — never the person who asked.
- **Override approved**: an approved override covers the invoice and is used when it's approved.

Within the limit, or with no limit, nothing is shown.
