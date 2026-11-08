import { correctTypo, editDistance, resolveRedirect, type Redirect } from "./redirects";
import { ORG_MODULES } from "./routes";

const r = (location: string, status: 301 | 307): Redirect => ({ location, status });

describe("resolveRedirect — root and canonical URLs", () => {
  it.each([
    "/",
    "/o/acme/home",
    "/o/acme/contacts",
    "/o/acme/accounting/chart-of-accounts",
    "/o/acme/settings/general",
    "/o/acme/settings/audit-log",
  ])("%s is canonical (no redirect)", (path) => {
    expect(resolveRedirect(path)).toBeNull();
  });

  it("every registry module is canonical under /o/:org", () => {
    for (const entry of ORG_MODULES) {
      expect(resolveRedirect(`/o/acme/${entry.path}`)).toBeNull();
    }
  });
});

describe("resolveRedirect — organisation-scoped", () => {
  it.each<[string, Redirect]>([
    ["/o/acme", r("/o/acme/home", 301)],
    ["/o/acme/", r("/o/acme/home", 301)],
    ["/O/ACME", r("/o/acme/home", 301)],
    ["/o/acme/home/", r("/o/acme/home", 301)],
    ["/o/acme/Home", r("/o/acme/home", 301)],
    ["/o/Acme/Contacts", r("/o/acme/contacts", 301)],
    ["/o/acme//contacts", r("/o/acme/contacts", 301)],
    ["/o/acme/dashboard", r("/o/acme/home", 301)],
    ["/o/acme/homepage", r("/o/acme/home", 301)],
    ["/o/acme/settings", r("/o/acme/settings/general", 301)],
    ["/o/acme/Settings/", r("/o/acme/settings/general", 301)],
    ["/o/acme/settings/tax", r("/o/acme/settings/registrations", 301)],
    ["/o/acme/accounting", r("/o/acme/accounting/chart-of-accounts", 301)],
    ["/o/acme/chart-of-accounts", r("/o/acme/accounting/chart-of-accounts", 301)],
    ["/o/acme/journals", r("/o/acme/accounting/journals", 301)],
    ["/o/acme/GeneralLedger/ChartOfAccounts.aspx", r("/o/acme/accounting/chart-of-accounts", 301)],
    ["/o/acme/dashbaord", r("/o/acme/home", 307)],
    ["/o/acme/setings", r("/o/acme/settings/general", 307)],
  ])("%s → %o", (path, expected) => {
    expect(resolveRedirect(path)).toEqual(expected);
  });

  it.each([
    "/o/acme/no-such-module",
    "/o/acme/home/extra",
    "/o/acme/settings/unknown",
    "/o/-bad-/home",
    "/o/ac%20me/home",
    "/o/a_b/home",
    `/o/${"a".repeat(64)}/home`,
  ])("%s does not redirect (404)", (path) => {
    expect(resolveRedirect(path)).toBeNull();
  });
});

describe("resolveRedirect — legacy-style paths without an organisation", () => {
  it.each<[string, string]>([
    ["/home", "home"],
    ["/HOME", "home"],
    ["/home/", "home"],
    ["/dashboard", "home"],
    ["/Dashboard/", "home"],
    ["/homepage", "home"],
    ["/index.html", "home"],
    ["/default.aspx", "home"],
    ["/settings", "settings/general"],
    ["/SETTINGS", "settings/general"],
    ["/settings/", "settings/general"],
    ["/settings/tax", "settings/registrations"],
    ["/settings/general", "settings/general"],
    ["/contacts", "contacts"],
    ["/customers", "contacts"],
    ["/chart-of-accounts", "accounting/chart-of-accounts"],
    ["/accounting/journals", "accounting/journals"],
    ["/Journal/Search.aspx", "accounting/journals"],
    ["/Setup/FinancialSettings.aspx", "settings/general"],
    ["/documents", "documents"],
    ["/billing", "settings/subscription"],
  ])("%s → current org's %s (307)", (path, module) => {
    expect(resolveRedirect(path, { currentOrg: "acme" })).toEqual(r(`/o/acme/${module}`, 307));
  });

  it.each(["/dashboard", "/settings", "/contacts", "/Journal/Search.aspx"])(
    "%s without a current organisation → Home / (307)",
    (path) => {
      expect(resolveRedirect(path)).toEqual(r("/", 307));
      expect(resolveRedirect(path, { currentOrg: null })).toEqual(r("/", 307));
    },
  );

  it("normalises the cookie value and ignores an invalid one", () => {
    expect(resolveRedirect("/home", { currentOrg: "ACME" })).toEqual(r("/o/acme/home", 307));
    expect(resolveRedirect("/home", { currentOrg: "../evil" })).toEqual(r("/", 307));
    expect(resolveRedirect("/home", { currentOrg: "https://evil.example" })).toEqual(r("/", 307));
  });

  it.each<[string, string]>([
    ["/dashbaord", "home"],
    ["/dashbord", "home"],
    ["/setings", "settings/general"],
    ["/settigns", "settings/general"],
    ["/contcts", "contacts"],
    ["/documnets", "documents"],
  ])("typo %s → %s (307)", (path, module) => {
    expect(resolveRedirect(path, { currentOrg: "acme" })).toEqual(r(`/o/acme/${module}`, 307));
  });

  it.each([
    "/no-such-page",
    "/xyz",
    "/invoices",
    "/login",
    "/invite/AbC123",
    "/api/healthz",
    "//evil.example",
    "//evil.example/home/x",
  ])("%s does not redirect", (path) => {
    expect(resolveRedirect(path, { currentOrg: "acme" })).toBeNull();
  });
});

describe("typo correction", () => {
  it("measures transpositions as one edit", () => {
    expect(editDistance("dashbaord", "dashboard")).toBe(1);
    expect(editDistance("kitten", "sitting")).toBe(3);
    expect(editDistance("", "abc")).toBe(3);
  });

  it("refuses short, distant or ambiguous words", () => {
    expect(correctTypo("hom")).toBeUndefined(); // shorter than 4
    expect(correctTypo("zzzzzz")).toBeUndefined();
    expect(correctTypo("home")).toBeUndefined(); // exact match is not a typo
    expect(correctTypo("dash/board")).toBeUndefined();
  });

  it("allows 1 edit below 8 letters and 2 edits from 8 letters", () => {
    expect(correctTypo("jurnal")).toBe("journal"); // 6 letters, 1 edit
    expect(correctTypo("jurnl")).toBeUndefined(); // 5 letters, 2 edits
    expect(correctTypo("dashbrd")).toBeUndefined(); // 7 letters, 2 edits
    expect(correctTypo("dashbrrd")).toBe("dashboard"); // 8 letters, 2 edits
    expect(correctTypo("dashbxxxd")).toBeUndefined(); // 9 letters, 3 edits
  });

  it("only returns aliases of a single module", () => {
    expect(correctTypo("journl")).toBe("journal");
  });
});
