import { normaliseForSearch, recentOrganisations, searchOrganisations } from "./search";
import { manyOrganisations, sampleOrganisations } from "./fixtures";

describe("org switcher search (A-01-T14)", () => {
  it("normalises case and accents", () => {
    expect(normaliseForSearch("  Érable QUÉBEC ")).toBe("erable quebec");
  });

  it("matches every word, accent-insensitive, prefix matches first", () => {
    expect(searchOrganisations(sampleOrganisations, "quebec").map((o) => o.id)).toEqual([
      "org-erable",
    ]);
    expect(searchOrganisations(sampleOrganisations, "ltd maple").map((o) => o.id)).toEqual([
      "org-maple",
    ]);
    // "ba": Bakery (contains) and Bay Street (starts with) → Bay Street first.
    expect(searchOrganisations(sampleOrganisations, "ba").map((o) => o.id)).toEqual([
      "org-bay",
      "org-north",
    ]);
  });

  it("returns nothing for an empty or blank query", () => {
    expect(searchOrganisations(sampleOrganisations, "")).toEqual([]);
    expect(searchOrganisations(sampleOrganisations, "   ")).toEqual([]);
  });

  it("searches 2,000 organisations quickly", () => {
    const orgs = manyOrganisations(2000);
    const start = performance.now();
    const hits = searchOrganisations(orgs, "harbour dental");
    expect(performance.now() - start).toBeLessThan(100);
    expect(hits.length).toBeGreaterThan(0);
    expect(hits.every((o) => /Harbour Dental/.test(o.name))).toBe(true);
  });

  it("lists at most 5 recent organisations in recent order, skipping inaccessible ids", () => {
    const recent = recentOrganisations(sampleOrganisations, [
      "org-bay",
      "gone",
      "org-maple",
      "org-bay",
      "org-north",
      "org-rocky",
      "org-prairie",
      "org-harbour",
    ]);
    expect(recent.map((o) => o.id)).toEqual([
      "org-bay",
      "org-maple",
      "org-north",
      "org-rocky",
      "org-prairie",
    ]);
  });
});
