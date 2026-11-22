import { testFormatMessage } from "@/test/intl";

import { findOrgModule } from "./routes";
import { navEntryFor, practiceNav, PRIMARY_NAV, primaryNav } from "./navigation";

describe("primary navigation (A-10-T05)", () => {
  it("lists the modules in task order (Banking from F-01)", () => {
    expect(PRIMARY_NAV.map((entry) => entry.id)).toEqual([
      "home",
      "contacts",
      "accounting",
      "banking",
      "documents",
      "settings",
    ]);
  });

  it("every item opens a module that exists in the route registry", () => {
    for (const entry of PRIMARY_NAV) {
      expect(findOrgModule(entry.modulePath), entry.id).toBeDefined();
    }
  });

  it("builds organisation URLs and marks the item that owns the current module", () => {
    const links = primaryNav(testFormatMessage(), "acme", "accounting/journals");
    expect(links.find((l) => l.id === "accounting")).toEqual({
      id: "accounting",
      label: "Accounting",
      href: "/o/acme/accounting/chart-of-accounts",
      current: true,
    });
    expect(links.filter((l) => l.current)).toHaveLength(1);
  });

  it("maps every settings section to Settings and leaves unknown paths unmarked", () => {
    expect(navEntryFor("settings/lock-dates")?.id).toBe("settings");
    expect(navEntryFor("settingsx")).toBeUndefined();
    expect(primaryNav(testFormatMessage(), "acme").some((l) => l.current)).toBe(false);
  });

  it("locks the items whose module is gated, with the product in the tooltip (U-03-T11)", () => {
    const links = primaryNav(testFormatMessage(), "acme", "home", (feature) =>
      feature.startsWith("accounting.chart_of_accounts")
        ? { feature, state: "gated", product: "accounting", productName: "Accounting" }
        : { feature, state: "allowed" },
    );
    expect(links.find((l) => l.id === "accounting")?.locked).toEqual({
      label: "Accounting isn't in this organisation's package",
    });
    // Still in the navigation, same URL (never hidden, never redirected).
    expect(links.find((l) => l.id === "accounting")?.href).toBe(
      "/o/acme/accounting/chart-of-accounts",
    );
    expect(links.filter((l) => l.locked)).toHaveLength(1);
    // CORE modules are never asked.
    const asked: string[] = [];
    primaryNav(testFormatMessage(), "acme", "home", (feature) => {
      asked.push(feature);
      return { feature, state: "gated" };
    });
    expect(asked).not.toContain("@core");
    expect(
      primaryNav(testFormatMessage(), "acme", "home", (feature) => ({ feature, state: "gated" }))
        .filter((l) => l.locked)
        .map((l) => [l.id, l.locked?.label]),
    ).toEqual([
      ["contacts", "Not in this organisation's package"],
      ["accounting", "Not in this organisation's package"],
      ["banking", "Not in this organisation's package"],
      ["documents", "Not in this organisation's package"],
    ]);
  });
});

describe("practiceNav (V-04)", () => {
  const fm = testFormatMessage();

  it("links the practice pages and marks the current one", () => {
    const links = practiceNav(fm, "firm", "/p/firm/staff/u1");
    expect(links.map((l) => [l.label, l.href, l.current])).toEqual([
      ["Dashboard", "/p/firm", false],
      ["Directory", "/p/firm/directory", false],
      ["Groups & tags", "/p/firm/groups", false],
      ["Staff", "/p/firm/staff", true],
    ]);
    expect(practiceNav(fm, "firm", "/p/firm").find((l) => l.current)?.label).toBe("Dashboard");
  });
});
