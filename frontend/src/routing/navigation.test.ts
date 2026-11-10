import { findOrgModule } from "./routes";
import { navEntryFor, PRIMARY_NAV, primaryNav } from "./navigation";

describe("primary navigation (A-10-T05)", () => {
  it("lists the Phase 0 modules in task order", () => {
    expect(PRIMARY_NAV.map((entry) => entry.id)).toEqual([
      "home",
      "contacts",
      "accounting",
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
    const links = primaryNav("acme", "accounting/journals");
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
    expect(primaryNav("acme").some((l) => l.current)).toBe(false);
  });
});
