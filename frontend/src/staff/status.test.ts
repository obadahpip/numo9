import { describe, expect, it } from "vitest";

import { staffStatus } from "./status";

describe("staffStatus (V-05-T09)", () => {
  it("shows dormant only for active members", () => {
    expect(staffStatus({ status: "active", dormant: false })).toBe("active");
    expect(staffStatus({ status: "active", dormant: true })).toBe("dormant");
    expect(staffStatus({ status: "suspended", dormant: true })).toBe("suspended");
    expect(staffStatus({ status: "pending", dormant: false })).toBe("pending");
  });
});
