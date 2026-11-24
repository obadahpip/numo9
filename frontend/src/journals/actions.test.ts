import { describe, expect, it } from "vitest";

import { journalActions, type ActionContext } from "./actions";

/** C-04-T10 — the state matrix of the journal actions bar, row by row. */
const base: ActionContext = { status: null, manual: true, canWrite: true };

describe("journal actions by state (C-04-T10)", () => {
  it.each<[string, Partial<ActionContext>, string[]]>([
    ["new", {}, ["saveDraft", "submit", "post"]],
    ["new, read-only person", { canWrite: false }, []],
    ["draft", { status: "draft" }, ["post", "submit", "copy"]],
    [
      "awaiting, approver",
      { status: "awaiting_approval", canApprove: true },
      ["approve", "reject", "copy"],
    ],
    [
      "awaiting, author",
      { status: "awaiting_approval", isAuthor: true, canApprove: false },
      ["withdraw", "copy"],
    ],
    [
      "awaiting, approver without write",
      { status: "awaiting_approval", canApprove: true, canWrite: false },
      ["approve", "reject"],
    ],
    ["awaiting, someone else", { status: "awaiting_approval" }, ["copy"]],
    ["posted", { status: "posted" }, ["copy", "reverse"]],
    ["posted by a module", { status: "posted", manual: false }, []],
    ["reversed", { status: "reversed" }, ["copy"]],
    ["reversed, read-only", { status: "reversed", canWrite: false }, []],
  ])("%s", (_name, over, expected) => {
    expect(journalActions({ ...base, ...over })).toEqual(expected);
  });

  it("never offers approve to the author", () => {
    for (const status of ["draft", "awaiting_approval", "posted", "reversed"] as const) {
      expect(journalActions({ ...base, status, isAuthor: true, canApprove: false })).not.toContain(
        "approve",
      );
    }
  });
});
