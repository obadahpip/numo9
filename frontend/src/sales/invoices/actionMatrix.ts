/**
 * The invoice action bar's state matrix (D-03a-T14): which actions each status offers. One
 * table, so the bar, its tests and the docs agree.
 *
 * | Status            | Actions                                                        |
 * |-------------------|----------------------------------------------------------------|
 * | new               | Save draft, Approve, Preview posting                           |
 * | draft             | Save draft, Approve (or Submit for approval), Preview, Delete   |
 * | awaiting approval | Approve and post, Preview posting                              |
 * | approved, sent    | Email, PDF, Copy, Copy to quote, Void, Preview posting         |
 * | partially paid    | Email, PDF, Copy, Copy to quote, Preview posting               |
 * | paid              | Email, PDF, Copy, Copy to quote, Preview posting               |
 * | void              | PDF, Copy, Preview posting                                     |
 */
import type { InvoiceStatus } from "./api";

export type InvoiceAction =
  | "save"
  | "approve"
  | "submit"
  | "approve_waiting"
  | "delete"
  | "email"
  | "pdf"
  | "copy"
  | "copy_quote"
  | "void"
  | "preview";

export function invoiceActions(
  status: InvoiceStatus | "new",
  { needsApproval = false }: { needsApproval?: boolean } = {},
): InvoiceAction[] {
  switch (status) {
    case "new":
      return ["save", needsApproval ? "submit" : "approve", "preview"];
    case "draft":
      return ["save", needsApproval ? "submit" : "approve", "preview", "delete"];
    case "awaiting_approval":
      return ["approve_waiting", "preview"];
    case "approved":
    case "sent":
      return ["email", "pdf", "copy", "copy_quote", "void", "preview"];
    case "partially_paid":
    case "paid":
      return ["email", "pdf", "copy", "copy_quote", "preview"];
    case "void":
      return ["pdf", "copy", "preview"];
  }
}
