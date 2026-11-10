import { readRecentOrgs, RECENT_ORGS_KEY, rememberOrg, writeCurrentOrgCookie } from "./recentOrgs";

beforeEach(() => localStorage.clear());

describe("recent organisations (A-01-T14)", () => {
  it("keeps the last 5, most recent first, without duplicates", () => {
    for (const org of ["a1", "b2", "c3", "d4", "e5", "f6"]) rememberOrg(org);
    expect(rememberOrg("c3")).toEqual(["c3", "f6", "e5", "d4", "b2"]);
    expect(readRecentOrgs()).toEqual(["c3", "f6", "e5", "d4", "b2"]);
  });

  it("ignores invalid ids and corrupt storage", () => {
    expect(rememberOrg("../evil")).toEqual([]);
    localStorage.setItem(RECENT_ORGS_KEY, "{not json");
    expect(readRecentOrgs()).toEqual([]);
    localStorage.setItem(RECENT_ORGS_KEY, JSON.stringify(["ok1", 7, "Bad Id"]));
    expect(readRecentOrgs()).toEqual(["ok1"]);
  });

  it("survives storage that throws", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    } as unknown as Storage;
    expect(readRecentOrgs(broken)).toEqual([]);
    expect(rememberOrg("a1", broken)).toEqual(["a1"]);
  });

  it("writes the current-organisation cookie for valid ids only", () => {
    const doc = { cookie: "", location: { protocol: "https:" } } as unknown as Document;
    writeCurrentOrgCookie("maple-leaf", doc);
    expect(doc.cookie).toBe("numo9_org=maple-leaf; Path=/; Max-Age=31536000; SameSite=Lax; Secure");
    const other = { cookie: "" } as unknown as Document;
    writeCurrentOrgCookie("bad id;", other);
    expect(other.cookie).toBe("");
  });
});
