import { describe, expect, it } from "vitest";

import { DEFAULT_STATE } from "./DirectoryScreen";
import { directoryQuery, stateFromSearch } from "./api";

describe("directory address (V-04-T08 drill-downs)", () => {
  it("reads the filters, search and archived flag of the address", () => {
    const state = stateFromSearch(
      "?status=trial&trial_ending=yes&mine=yes&q=maple&archived=include&nonsense=1",
      DEFAULT_STATE,
    );
    expect(state?.filters).toEqual({ status: ["trial"], trial_ending: ["yes"], mine: ["yes"] });
    expect(state?.q).toBe("maple");
    expect(state?.archived).toBe(true);
    expect(state?.columns).toEqual(DEFAULT_STATE.columns);
  });

  it("an address without filters changes nothing", () => {
    expect(stateFromSearch("", DEFAULT_STATE)).toBeNull();
    expect(stateFromSearch("?nonsense=1", DEFAULT_STATE)).toBeNull();
  });

  it("sends the drill-down filters to the API", () => {
    const query = directoryQuery({
      practice: "p1",
      filters: { bn_missing: ["yes"], lock_missing: ["yes"] },
    });
    expect(query).toContain("bn_missing=yes");
    expect(query).toContain("lock_missing=yes");
  });
});
