import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { BulkJob } from "./api";
import { BulkProgressDrawer, POLL_MS } from "./BulkProgressDrawer";

/**
 * V-03-T10 — progress drawer + results table. Acceptance: the counters update live (polling)
 * until the job ends; then the results by outcome, with the reason, and the CSV link.
 */

function job(overrides: Partial<BulkJob> = {}): BulkJob {
  return {
    id: "job-1",
    action: "settings",
    action_label: "Change settings",
    params: {},
    status: "running",
    total: 200,
    done: 0,
    percent: 0,
    counts: { pending: 200, succeeded: 0, skipped: 0, failed: 0, cancelled: 0 },
    created_by: { id: "u", name: "Sam Patel" },
    created_at: "2026-11-18T15:00:00Z",
    started_at: "2026-11-18T15:00:01Z",
    finished_at: null,
    cancel_requested: false,
    export_ready: false,
    ...overrides,
  };
}

const states = [
  job({
    done: 60,
    percent: 30,
    counts: { pending: 140, succeeded: 58, skipped: 1, failed: 1, cancelled: 0 },
  }),
  job({
    done: 140,
    percent: 70,
    counts: { pending: 60, succeeded: 136, skipped: 3, failed: 1, cancelled: 0 },
  }),
  job({
    status: "completed",
    done: 200,
    percent: 100,
    finished_at: "2026-11-18T15:02:00Z",
    counts: { pending: 0, succeeded: 195, skipped: 4, failed: 1, cancelled: 0 },
  }),
];
const ROWS = [
  {
    organisation: { id: "o1", name: "Pine Dental PC" },
    outcome: "failed",
    reason: "error",
    message: "Something went wrong with this organisation. Nothing was changed.",
    before: {},
    after: {},
    processed_at: "2026-11-18T15:01:00Z",
  },
];
const calls: string[] = [];

beforeEach(() => {
  resetCsrfToken();
  calls.length = 0;
  let poll = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(`${init?.method ?? "GET"} ${url}`);
      const json = (data: unknown) =>
        new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
      if (url.includes("auth/csrf")) return json({ csrfToken: "t" });
      if (url.endsWith("/cancel")) return json(job({ cancel_requested: true }));
      if (url.includes("/rows"))
        return json({
          count: 1,
          page: 1,
          pages: 1,
          results: url.includes("outcome=succeeded") ? [] : ROWS,
        });
      const state = states[Math.min(poll, states.length - 1)];
      poll += 1;
      return json(state);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const counter = (key: string) => document.querySelector(`[data-counter="${key}"] dd`)?.textContent;

it("updates the counters live, then shows the results by outcome", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const onFinished = vi.fn();
  renderWithIntl(<BulkProgressDrawer job={job()} onClose={() => {}} onFinished={onFinished} />);
  const drawer = await screen.findByRole("dialog", { name: "Change settings" });
  expect(counter("pending")).toBe("200");
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(counter("succeeded")).toBe("58");
  expect(within(drawer).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "60");
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(counter("succeeded")).toBe("136");
  expect(counter("pending")).toBe("60");
  await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
  expect(counter("succeeded")).toBe("195");
  expect(onFinished).toHaveBeenCalledTimes(1);
  const results = await within(drawer).findByRole("table");
  expect(results).toHaveTextContent("Pine Dental PC");
  expect(results).toHaveTextContent("Nothing was changed.");
  expect(within(drawer).getByRole("link", { name: "Download the results (CSV)" })).toHaveAttribute(
    "href",
    "/api/v1/practice/bulk/job-1/results.csv",
  );
  vi.useRealTimers();
  await userEvent.click(within(drawer).getByRole("button", { name: "Succeeded" }));
  expect(await within(drawer).findByText("No organisation with this outcome.")).toBeVisible();
  expect(calls.some((c) => c.includes("/rows?page=1&outcome=succeeded"))).toBe(true);
  await expectNoAxeViolations(document.body);
});

it("cancels the rest", async () => {
  renderWithIntl(<BulkProgressDrawer job={job()} onClose={() => {}} />);
  await userEvent.click(await screen.findByRole("button", { name: "Cancel the rest" }));
  expect(await screen.findByText("Stopping before the next organisation…")).toBeVisible();
  expect(calls.some((c) => c.startsWith("POST") && c.endsWith("/job-1/cancel"))).toBe(true);
});
