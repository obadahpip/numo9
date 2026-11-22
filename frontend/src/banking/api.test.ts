import { afterEach, describe, expect, it, vi } from "vitest";

import { AUTO_TAX_CODE, bankingApi, taxDefaultQuery } from "./api";

describe("tax default query (G-02-T09)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("drops empty values", () => {
    expect(taxDefaultQuery({ kind: "spend", date: "2026-06-15", account: "a1", contact: "" })).toBe(
      "kind=spend&date=2026-06-15&account=a1",
    );
  });

  it("calls the tax-default endpoint", async () => {
    const body = {
      code: "purchase.ON.standard",
      name: "HST 13 % (Ontario) on purchases",
      version: 1,
      source: "account",
      explanation: "tax.pos.account",
      params: {},
      province: "",
      flags: [],
      warnings: [],
      taxes: [{ role: "itc_receivable", amount: "13.00", recoverable: true }],
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    const result = await bankingApi.taxDefault("org-1", {
      kind: "spend",
      date: "2026-06-15",
      amount: "100.00",
    });
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/api/v1/o/org-1/bank-transactions/tax-default?kind=spend&date=2026-06-15&amount=100.00",
    );
    expect(result.body.code).toBe("purchase.ON.standard");
    expect(AUTO_TAX_CODE).toBe("auto");
  });
});
