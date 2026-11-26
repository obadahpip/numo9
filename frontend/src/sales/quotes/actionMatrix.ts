/**
 * The quote action bar's state matrix (D-02-T12): which actions each status offers. One table,
 * so the bar, its tests and the docs agree.
 *
 * | Status           | Actions                                                                |
 * |------------------|------------------------------------------------------------------------|
 * | new              | Save draft                                                             |
 * | draft            | Save draft, Email to customer, Mark as sent, PDF, Copy, Delete draft    |
 * | sent, viewed     | Email to customer, Copy link, Withdraw links, Mark accepted, Mark       |
 * |                  | declined, Revise, PDF, Copy                                            |
 * | accepted         | Convert to invoice, Revise, PDF, Copy                                  |
 * | declined, expired| Revise, PDF, Copy                                                      |
 * | invoiced         | PDF, Copy                                                              |
 */
import type { QuoteStatus } from "./status";

export type QuoteAction =
  | "save"
  | "send"
  | "mark_sent"
  | "copy_link"
  | "revoke_links"
  | "accept"
  | "decline"
  | "convert"
  | "revise"
  | "pdf"
  | "copy"
  | "delete";

export function quoteActions(status: QuoteStatus | "new"): QuoteAction[] {
  switch (status) {
    case "new":
      return ["save"];
    case "draft":
      return ["save", "send", "mark_sent", "pdf", "copy", "delete"];
    case "sent":
    case "viewed":
      return ["send", "copy_link", "revoke_links", "accept", "decline", "revise", "pdf", "copy"];
    case "accepted":
      return ["convert", "revise", "pdf", "copy"];
    case "declined":
    case "expired":
      return ["revise", "pdf", "copy"];
    case "invoiced":
      return ["pdf", "copy"];
  }
}
