import { equivalentOrgUrl, practiceDirectoryUrl } from "./routes";

describe("equivalentOrgUrl (A-01-T14: switching keeps the equivalent route)", () => {
  it.each([
    ["contacts", "/o/north/contacts"],
    ["settings/lock-dates", "/o/north/settings/lock-dates"],
    ["accounting/journals", "/o/north/accounting/journals"],
    ["/Accounting/Journals/", "/o/north/accounting/journals"],
    // A record belongs to the old organisation: land on its module.
    ["contacts/5f1d0c2e-0000-4000-8000-000000000000", "/o/north/contacts"],
    ["settings/general/history", "/o/north/settings/general"],
    // Unknown or missing path: Home.
    ["payroll", "/o/north/home"],
    [undefined, "/o/north/home"],
    ["", "/o/north/home"],
  ])("%s → %s", (path, url) => {
    expect(equivalentOrgUrl("north", path)).toBe(url);
  });
});

describe("practiceDirectoryUrl", () => {
  it("opens the practice directory", () => {
    expect(practiceDirectoryUrl("profitex")).toBe("/p/profitex/directory");
  });
});
