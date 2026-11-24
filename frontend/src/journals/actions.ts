/**
 * Journal actions by state (C-04-T10): which buttons the actions bar shows. One table, used by the
 * new-journal form and the journal page, tested row by row.
 *
 * | State             | Shown                                                          |
 * |-------------------|----------------------------------------------------------------|
 * | new               | Save draft · Submit for approval · Post                         |
 * | draft             | Post · Submit for approval · Copy                               |
 * | awaiting approval | Approve · Send back (an approver, not the author) · Withdraw    |
 * |                   | (the author) · Copy                                            |
 * | posted            | Copy · Reverse                                                 |
 * | reversed          | Copy                                                           |
 *
 * Writing actions need `accounting.journals.post`; Approve / Send back come from the server's
 * `viewer.can_approve` (approve permission, not the author, within the limit). Journals posted by
 * modules (invoices, payroll…) and reversals are changed in their own module: no Copy or Reverse.
 */
import type { JournalStatus } from "./api";

export type JournalAction =
  "saveDraft" | "submit" | "post" | "approve" | "reject" | "withdraw" | "copy" | "reverse";

export interface ActionContext {
  /** `null`: a journal still being written. */
  status: JournalStatus | null;
  /** A manual journal (`type` = manual); module postings and reversals aren't. */
  manual: boolean;
  /** `accounting.journals.post`. */
  canWrite: boolean;
  /** The server's `viewer` of the journal. */
  isAuthor?: boolean;
  canApprove?: boolean;
}

export function journalActions(ctx: ActionContext): JournalAction[] {
  const write = (actions: JournalAction[]) => (ctx.canWrite ? actions : []);
  switch (ctx.status) {
    case null:
      return write(["saveDraft", "submit", "post"]);
    case "draft":
      return write(["post", "submit", ...(ctx.manual ? (["copy"] as const) : [])]);
    case "awaiting_approval":
      return [
        ...(ctx.canApprove ? (["approve", "reject"] as const) : []),
        ...(ctx.isAuthor ? write(["withdraw"]) : []),
        ...(ctx.manual ? write(["copy"]) : []),
      ];
    case "posted":
      return ctx.manual ? write(["copy", "reverse"]) : [];
    case "reversed":
      return ctx.manual ? write(["copy"]) : [];
    default:
      return [];
  }
}
