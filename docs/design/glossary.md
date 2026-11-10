# en-CA glossary (A-10-T15)

Canadian English terms used in every screen, email and document, enforced in CI by
`backend/tools/check_glossary.py` (gap-31 Canadian terms, gap-38 one spelling) over the
frontend and backend catalogues and the design system's stories and sample data. Source:
`backend/tools/glossary.toml` — regenerate this page with
`python backend/tools/check_glossary.py --terms`.

| Use | Meaning | Instead of |
|---|---|---|
| organisation | A business using Numo9 (the paying tenant) | organization |
| cheque | The payment instrument (cheque number, print cheques) | check (noun) |
| Province | Province or territory of an address or registration | State |
| Postal code | Canadian postal code, A1A 1A1 | ZIP, ZIP code, postcode |
| GST/HST | Goods and services tax / harmonized sales tax (QST for Québec) | VAT, sales tax (for GST/HST) |
| vacation pay | Vacation pay and vacation entitlement (payroll) | annual leave, holiday pay (for vacation) |
| Accountant | Practice role of the firm's staff | Advisor |

| Banned | Use | Gap |
|---|---|---|
| VAT | GST/HST (or QST for Québec) | gap-31 |
| State | Province (or Province/territory) | gap-31 |
| ZIP | Postal code | gap-31 |
| annual leave | vacation (vacation pay) | gap-31 |
| Organization | organisation | gap-38 |
| Check(s) | cheque (payment instrument); for the verb use 'Verify' or 'Review' | gap-31 |
| Advisor | Accountant (practice role) | gap-38 |
| Postcode | Postal code | gap-31 |
| Postal Code (title case) | Postal code | gap-31 |
| HST/GST, GST-HST | GST/HST | gap-31 |
| Checkbook | chequebook | gap-31 |
