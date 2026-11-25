/**
 * Quote statuses (D-02-T01, gap-05): the backend's `QuoteStatus` enum, in its order — the one
 * vocabulary of the overview card, the list tabs and the filters. Kept equal to the backend by
 * backend/tests/test_quote_models.py.
 */
export const QUOTE_STATUSES = [
  "draft",
  "sent",
  "viewed",
  "accepted",
  "declined",
  "expired",
  "invoiced",
] as const;

export type QuoteStatus = (typeof QUOTE_STATUSES)[number];
