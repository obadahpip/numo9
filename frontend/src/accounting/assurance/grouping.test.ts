import { describe, expect, it } from "vitest";

import { finding, TEARDOWN_FINDINGS } from "./fixtures";
import { groupFindings, scoreTone } from "./grouping";

/** K-09-T21 — findings grouped by rule, most severe first; the score's tone. */
describe("groupFindings", () => {
  it("groups the teardown findings by rule, critical first", () => {
    const groups = groupFindings(TEARDOWN_FINDINGS);
    expect(groups.length).toBeGreaterThanOrEqual(7);
    expect(groups.slice(0, 3).map((g) => g.severity)).toEqual(["critical", "critical", "critical"]);
    expect(groups[0]?.name).toBe("Conversion balances incomplete or unbalanced");
    const toCash = groups.find((g) => g.rule === "JOURNAL_TO_CASH");
    expect(toCash?.findings.map((f) => f.amount)).toEqual(["576.95", "417.22"]);
  });

  it("takes the most severe severity of a group's findings", () => {
    const groups = groupFindings([
      finding("X", "Rule X", "info", "a"),
      finding("X", "Rule X", "critical", "b"),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0]?.severity).toBe("critical");
  });
});

describe("scoreTone", () => {
  it("bands the score", () => {
    expect(scoreTone(100)).toBe("success");
    expect(scoreTone(80)).toBe("success");
    expect(scoreTone(79)).toBe("warning");
    expect(scoreTone(50)).toBe("warning");
    expect(scoreTone(49)).toBe("danger");
  });
});
