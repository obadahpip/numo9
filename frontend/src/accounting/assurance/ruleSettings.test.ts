import { describe, expect, it } from "vitest";

import type { RuleSetting } from "./api";
import { changesOf, defaultDraft, draftOf, parseParam, problemsOf } from "./ruleSettings";

/**
 * K-09-T23 — rule settings: parameters validated against the rule's schema as the server does
 * (whole numbers, amounts, minimum, maximum, choices, account codes) and only what changed is
 * sent; Reset to defaults restores the rule's defaults.
 */
const BACKDATED: RuleSetting = {
  code: "BACKDATED",
  name: "Backdated posting",
  description: "Posted more than N days after the document date.",
  default_severity: "warning",
  incremental: true,
  has_fix: false,
  params: [
    {
      name: "days",
      kind: "int",
      label: "Days",
      default: 7,
      minimum: 1,
      maximum: 365,
      choices: [],
    },
  ],
  enabled: true,
  severity: "warning",
  values: { days: 7 },
};

const ROUND: RuleSetting = {
  ...BACKDATED,
  code: "ROUND_AMOUNT",
  params: [
    {
      name: "threshold",
      kind: "decimal",
      label: "Threshold",
      default: "1000.00",
      minimum: "0.00",
      maximum: null,
      choices: [],
    },
    {
      name: "fix_source",
      kind: "choice",
      label: "Fix source",
      default: "auto",
      minimum: null,
      maximum: null,
      choices: ["auto", "transfer"],
    },
    {
      name: "exclude",
      kind: "codes",
      label: "Accounts",
      default: [],
      minimum: null,
      maximum: null,
      choices: [],
    },
    {
      name: "holidays",
      kind: "bool",
      label: "Holidays",
      default: false,
      minimum: null,
      maximum: null,
      choices: [],
    },
  ],
  values: { threshold: "1000.00", fix_source: "auto", exclude: ["5100"], holidays: false },
};

describe("rule settings", () => {
  it("validates numbers against the schema", () => {
    const days = BACKDATED.params[0]!;
    expect(parseParam(days, "30")).toEqual({ ok: true, value: 30 });
    expect(parseParam(days, "0")).toEqual({ ok: false, problem: { kind: "min", min: "1" } });
    expect(parseParam(days, "400")).toEqual({ ok: false, problem: { kind: "max", max: "365" } });
    expect(parseParam(days, "7.5")).toEqual({ ok: false, problem: { kind: "whole" } });
    expect(parseParam(days, "")).toEqual({ ok: false, problem: { kind: "whole" } });
    const threshold = ROUND.params[0]!;
    expect(parseParam(threshold, "2500.5")).toEqual({ ok: true, value: "2500.50" });
    expect(parseParam(threshold, "1.234")).toEqual({ ok: false, problem: { kind: "number" } });
    expect(parseParam(ROUND.params[1]!, "nope")).toEqual({
      ok: false,
      problem: { kind: "choice" },
    });
    expect(parseParam(ROUND.params[2]!, "5100, 5200 ,")).toEqual({
      ok: true,
      value: ["5100", "5200"],
    });
  });

  it("sends only what changed", () => {
    const draft = draftOf(ROUND);
    expect(draft.values).toEqual({
      threshold: "1000.00",
      fix_source: "auto",
      exclude: "5100",
      holidays: false,
    });
    expect(changesOf(ROUND, draft)).toBeNull();
    expect(changesOf(ROUND, { ...draft, values: { ...draft.values, threshold: "1000" } })).toBe(
      null,
    );
    expect(
      changesOf(ROUND, {
        ...draft,
        enabled: false,
        values: { ...draft.values, holidays: true, exclude: "5100, 6000" },
      }),
    ).toEqual({ enabled: false, params: { holidays: true, exclude: ["5100", "6000"] } });
    const changedN = { ...draftOf(BACKDATED), values: { days: "30" } };
    expect(changesOf(BACKDATED, changedN)).toEqual({ params: { days: 30 } });
    expect(problemsOf(BACKDATED, { ...changedN, values: { days: "0" } })).toEqual({
      days: { kind: "min", min: "1" },
    });
  });

  it("resets to the rule's defaults", () => {
    const saved = { ...BACKDATED, enabled: false, severity: "info" as const, values: { days: 30 } };
    expect(defaultDraft(saved)).toEqual({
      enabled: true,
      severity: "warning",
      values: { days: "7" },
    });
    expect(changesOf(saved, defaultDraft(saved))).toEqual({
      enabled: true,
      severity: "warning",
      params: { days: 7 },
    });
  });
});
