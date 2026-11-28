import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { primaryNav } from "@/routing/navigation";
import { testFormatMessage } from "@/test/intl";

import type { Summary } from "./api";
import { announceSummary, attentionCount, useAssuranceAttention } from "./badge";
import { TEARDOWN_SUMMARY } from "./fixtures";

/**
 * K-09-T24 — nav badge: the Accounting item's badge = open critical + open warning findings
 * (info and acknowledged findings don't count), hidden at 0; it follows the Assurance page.
 */
const summary = (critical: number, warning: number, info: number, acknowledged = 0): Summary => ({
  ...TEARDOWN_SUMMARY,
  open: { critical, warning, info },
  statuses: { ...TEARDOWN_SUMMARY.statuses, acknowledged },
});

afterEach(() => vi.unstubAllGlobals());

describe("assurance nav badge", () => {
  it("counts open critical + warning only", () => {
    expect(attentionCount(summary(4, 11, 2, 1))).toBe(15);
    expect(attentionCount(summary(0, 0, 9, 3))).toBe(0);
    expect(attentionCount(TEARDOWN_SUMMARY)).toBe(
      TEARDOWN_SUMMARY.open.critical + TEARDOWN_SUMMARY.open.warning,
    );
  });

  it("puts the count on the Accounting item and hides it at zero", () => {
    const badge = { count: 15, label: "15 assurance findings need attention" };
    const links = primaryNav(testFormatMessage(), "refined", "home", undefined, {
      accounting: badge,
    });
    expect(links.find((l) => l.id === "accounting")?.badge).toEqual(badge);
    expect(links.filter((l) => l.badge)).toHaveLength(1);
    const none = primaryNav(testFormatMessage(), "refined", "home", undefined, {
      accounting: { ...badge, count: 0 },
    });
    expect(none.some((l) => l.badge)).toBe(false);
  });

  it("reads the summary once and follows the summaries the Assurance page loads", async () => {
    const fetcher = vi.fn<(input: RequestInfo | URL) => Promise<Response>>(
      async () =>
        new Response(JSON.stringify(summary(4, 11, 2)), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetcher);
    const { result } = renderHook(() => useAssuranceAttention("refined", true));
    await waitFor(() => expect(result.current).toBe(15));
    expect(String(fetcher.mock.calls[0]?.[0])).toContain("/api/v1/o/refined/assurance/");
    act(() => announceSummary("refined", summary(1, 0, 5)));
    expect(result.current).toBe(1);
    act(() => announceSummary("other-org", summary(9, 9, 9)));
    expect(result.current).toBe(1);
  });

  it("shows nothing without access", async () => {
    const fetcher = vi.fn(
      async () => new Response(JSON.stringify({ detail: "Not found." }), { status: 404 }),
    );
    vi.stubGlobal("fetch", fetcher);
    const { result } = renderHook(() => useAssuranceAttention("refined", true));
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(result.current).toBeNull();
    const off = renderHook(() => useAssuranceAttention("refined", false));
    expect(off.result.current).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
