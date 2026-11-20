import { describe, expect, it } from "vitest";

import { offeredQuickCreates, QUICK_CREATE, quickCreateFor, shortcutOf } from "./quickCreate";

describe("quick-create registry (A-09-T06)", () => {
  it("documents the ten shortcuts N I, N B, N C, N Q, N P, N J, N S, N R, N T, N U", () => {
    expect(QUICK_CREATE.map(shortcutOf)).toEqual([
      "N I",
      "N B",
      "N C",
      "N Q",
      "N P",
      "N J",
      "N S",
      "N R",
      "N T",
      "N U",
    ]);
    expect(new Set(QUICK_CREATE.map((e) => e.key)).size).toBe(10);
    for (const entry of QUICK_CREATE) {
      expect(entry.permission).toMatch(/^[a-z_]+\.[a-z_]+\.[a-z_]+$/);
      expect(entry.feature).toBeTruthy();
    }
  });

  it("finds the entry of a key, any case", () => {
    expect(quickCreateFor("c")?.id).toBe("contact");
    expect(quickCreateFor("Z")).toBeUndefined();
  });

  it("offers what is available and permitted, locked when the package lacks it", () => {
    const all = offeredQuickCreates(null, () => null).map((o) => o.entry.id);
    expect(all).toEqual(["contact", "journal", "user"]);
    const none = offeredQuickCreates(new Set(["contacts.contacts.view"]), () => null);
    expect(none).toEqual([]);
    const locked = offeredQuickCreates(new Set(["contacts.contacts.manage"]), (f) =>
      f.startsWith("accounting.") ? "Part of Accounting" : null,
    );
    expect(locked).toEqual([{ entry: QUICK_CREATE[2], reason: "Part of Accounting" }]);
  });
});
