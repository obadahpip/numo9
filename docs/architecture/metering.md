# Usage metering (S-06-T07)

Modules record what an organisation uses — OCR pages, emails sent, API calls — with one call:

```python
from numo9.metering.service import meter

meter(org, "documents.ocr.page", 3)
```

- **Never blocks or fails a request.** `meter` appends one entry to a Redis stream
  (`numo9:metering`, `METERING_REDIS_URL`, database 4 of `REDIS_URL` by default) with a 250 ms
  timeout. A bad key (`a.b` dotted lower-case), a non-positive quantity or a stream that's down
  drops the event, logs a warning and returns `False`.
- **Aggregated every minute** by the platform job `numo9.metering.aggregate` into `UsageDaily`
  (organisation, key, UTC day, quantity), 5,000 entries per transaction with
  `INSERT … ON CONFLICT DO UPDATE SET quantity = quantity + excluded.quantity`.
- **Exactly once.** The job reads entries after `StreamOffset.last_id` and saves the new offset in
  the same transaction as the sums; it trims the stream only after the commit. A job that stops
  between the commit and the trim reads after the saved offset next time, so nothing is counted
  twice. One aggregator at a time (beat lock and a transaction advisory lock).
- `UsageDaily` is an organisation record (`OrgOwnedModel`): an organisation's usage is read in its
  context; platform reports read across organisations with `unscoped()`.
- Tests and a dev server without Redis use an in-process stream with the same semantics
  (`METERING_REDIS_URL=""`).

Verified by `tests/test_metering.py`: 10,000 random events over 5 organisations, 3 keys and 3 days
sum to the expected 45 rows on both streams; a second run adds nothing.
