import type { DocumentGridLine } from "@numo9/ui";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CalculateResponse } from "./api";
import {
  DEBOUNCE_MS,
  useDocumentCalculation,
  type DocumentCalculationInput,
  type MirrorTaxCode,
} from "./useDocumentCalculation";

const HST: MirrorTaxCode = {
  id: "hst",
  components: [{ key: "hst_on", name: "HST (ON) 13 %", rate: "13" }],
};

const line = (over: Partial<DocumentGridLine>): DocumentGridLine => ({
  id: "l1",
  item: "",
  description: "Design",
  quantity: "2",
  unitPrice: "50.00",
  discount: "",
  account: "acc",
  taxCode: "hst",
  ...over,
});

const input = (over: Partial<DocumentCalculationInput> = {}): DocumentCalculationInput => ({
  org: "acme",
  side: "sales",
  date: "2026-07-15",
  taxMode: "exclusive",
  discountType: "none",
  discountValue: "",
  lines: [line({}), line({ id: "l2", quantity: "1", unitPrice: "100", discount: "10%" })],
  taxCodes: [HST],
  ...over,
});

const SERVER: CalculateResponse = {
  kind: "invoice",
  tax_mode: "exclusive",
  lines: [
    {
      gross: "100.00",
      line_discount: "0.00",
      net: "100.00",
      discount_share: "0.00",
      taxable: "100.00",
      exclusive: "100.00",
      tax: "13.00",
      taxes: [],
    },
    {
      gross: "100.00",
      line_discount: "10.00",
      net: "90.00",
      discount_share: "0.00",
      taxable: "90.00",
      exclusive: "90.00",
      tax: "11.70",
      taxes: [],
    },
  ],
  subtotal: "190.00",
  discount_total: "0.00",
  tax_total: "24.70",
  total: "214.70",
  net_total: "190.00",
  tax_included: false,
  tax_by_component: [{ key: "hst_on", name: "HST (ON) 13 %", amount: "24.70" }],
  problems: [{ line: 2, field: "tax_code", code: "x", message: "m" }],
};

describe("useDocumentCalculation (D-01-T14)", () => {
  let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;
  beforeEach(() => {
    vi.useFakeTimers();
    fetchMock = vi.fn<typeof fetch>(async (url) => {
      if (String(url).includes("csrf"))
        return new Response(JSON.stringify({ csrfToken: "t" }), { status: 200 });
      return new Response(JSON.stringify(SERVER), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows the mirror at once, then the server's totals after the debounce", async () => {
    const { result } = renderHook(() => useDocumentCalculation(input()));
    expect(result.current.source).toBe("mirror");
    expect(result.current.pending).toBe(true);
    expect(result.current.totals.total).toBe("214.70");
    expect(result.current.amounts.l2).toEqual({ tax: "11.70", amount: "90.00" });
    expect(fetchMock).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    });
    expect(result.current.source).toBe("server");
    expect(result.current.totals).toEqual({
      subtotal: "190.00",
      discountTotal: "0.00",
      taxes: SERVER.tax_by_component,
      taxTotal: "24.70",
      total: "214.70",
      taxIncluded: false,
    });
    expect(result.current.problems).toHaveLength(1);
    const call = fetchMock.mock.calls.find(([url]) => String(url).includes("documents"));
    expect(String(call?.[0])).toBe("/api/v1/o/acme/documents/sales/calculate");
    const body = JSON.parse(String((call?.[1] as RequestInit).body)) as Record<string, unknown>;
    expect(body.lines).toEqual([
      expect.objectContaining({ quantity: "2", unit_price: "50.00", discount_type: "none" }),
      expect.objectContaining({ discount_type: "percent", discount_value: "10" }),
    ]);
  });

  it("typing again within the debounce sends one request, for the latest input", async () => {
    const { result, rerender } = renderHook((props) => useDocumentCalculation(props), {
      initialProps: input(),
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS / 2);
    });
    rerender(input({ discountType: "percent", discountValue: "10" }));
    // The mirror applies the document discount straight away: 10 % of 190.00.
    expect(result.current.totals.discountTotal).toBe("19.00");
    expect(result.current.source).toBe("mirror");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    });
    const calls = fetchMock.mock.calls.filter(([url]) => String(url).includes("documents"));
    expect(calls).toHaveLength(1);
    expect(result.current.source).toBe("server");
  });
});
