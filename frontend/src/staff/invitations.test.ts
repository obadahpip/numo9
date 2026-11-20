import { describe, expect, it } from "vitest";

import { inviteErrorText, PRACTICE_ROLES } from "./invitations";

describe("staff invitations (V-05-T03)", () => {
  it("offers the four system practice roles", () => {
    expect(PRACTICE_ROLES).toEqual([
      "accountant",
      "reviewer",
      "payroll_specialist",
      "practice_admin",
    ]);
  });

  it("reads the server's message from detail or a field error", () => {
    expect(inviteErrorText({ detail: "sam@cpa.ca is already a member." })).toBe(
      "sam@cpa.ca is already a member.",
    );
    expect(inviteErrorText({ email: ["Enter a valid email address."] })).toBe(
      "Enter a valid email address.",
    );
    expect(inviteErrorText({ role: [{ message: "Choose a role.", code: "x" }] })).toBe(
      "Choose a role.",
    );
    expect(inviteErrorText(null)).toBe("");
  });
});
