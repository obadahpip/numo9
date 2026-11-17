import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { BulkPreview } from "./api";
import { BulkActionDialog } from "./BulkActionDialog";

/**
 * V-03-T09 — preview diff UI + confirm. Acceptance: the diff rows are the API's lines (field,
 * current → new; skipped with the reason); nothing is applied before *Apply*; *Apply* confirms.
 */

const PREVIEW: BulkPreview = {
  total: 120,
  counts: { change: 117, no_change: 2, skipped: 1 },
  lines: [
    {
      organisation: { id: "o1", name: "Maple Leaf Supply Ltd." },
      status: "change",
      reason: "",
      message: "",
      before: { sales_terms: { type: "days_after_document", days: 30 } },
      after: { sales_terms: { type: "days_after_document", days: 15 } },
    },
    {
      organisation: { id: "o2", name: "Cedar Roofing Co." },
      status: "skipped",
      reason: "no_access",
      message: "You don't have access to this organisation.",
      before: {},
      after: {},
    },
  ],
};
const JOB = {
  id: "job-1",
  action: "settings",
  action_label: "Change settings",
  params: {},
  status: "preview",
  total: 120,
  done: 0,
  percent: 0,
  counts: { pending: 0, succeeded: 0, skipped: 0, failed: 0, cancelled: 0 },
  created_by: { id: "u", name: "Sam" },
  created_at: "2026-11-18T15:00:00Z",
  started_at: null,
  finished_at: null,
  cancel_requested: false,
  export_ready: false,
};

const calls: { url: string; method: string; body: unknown }[] = [];

beforeEach(() => {
  resetCsrfToken();
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const json = (data: unknown, status = 200) =>
        new Response(JSON.stringify(data), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("auth/csrf")) return json({ csrfToken: "t" });
      if (url.endsWith("/confirm")) return json({ ...JOB, status: "queued" }, 202);
      if (url.endsWith("/practice/bulk")) return json({ job: JOB, preview: PREVIEW }, 201);
      return json({}, 404);
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());

it("previews the API's diff lines, then applies", async () => {
  const onStarted = vi.fn();
  renderWithIntl(
    <BulkActionDialog
      practice="p-1"
      action="settings"
      selection={{ mode: "all", query: { q: "", filters: {}, archived: false }, count: 120 }}
      onClose={() => {}}
      onStarted={onStarted}
    />,
  );
  const dialog = await screen.findByRole("dialog", { name: "Settings — 120 organisations" });
  await userEvent.clear(within(dialog).getByLabelText("Days or day"));
  await userEvent.type(within(dialog).getByLabelText("Days or day"), "15");
  await userEvent.click(within(dialog).getByRole("button", { name: "Preview changes" }));
  const create = calls.find((c) => c.url.endsWith("/practice/bulk"));
  expect(create?.body).toEqual({
    practice: "p-1",
    action: "settings",
    params: { settings: { sales_terms: { type: "days_after_document", days: "15" } } },
    selection: { query: {} },
  });
  expect(
    await within(dialog).findByText("Nothing has changed yet. Review the changes, then apply."),
  ).toBeVisible();
  expect(within(dialog).getByText("117 will change")).toBeVisible();
  expect(within(dialog).getByText("1 skipped")).toBeVisible();
  const rows = dialog.querySelectorAll("tbody tr");
  expect(rows).toHaveLength(2);
  expect(rows[0]).toHaveTextContent("Maple Leaf Supply Ltd.");
  expect(rows[0]).toHaveTextContent("type: days_after_document · days: 30");
  expect(rows[0]).toHaveTextContent("days: 15");
  expect(rows[1]).toHaveTextContent("You don't have access to this organisation.");
  expect(within(dialog).getByText(/Showing 2 of 120/)).toBeVisible();
  expect(calls.some((c) => c.url.endsWith("/confirm"))).toBe(false);
  await expectNoAxeViolations(document.body);
  await userEvent.click(within(dialog).getByRole("button", { name: "Apply to 117 organisations" }));
  expect(calls.at(-1)?.url).toMatch(/\/practice\/bulk\/job-1\/confirm$/);
  expect(onStarted).toHaveBeenCalledWith(expect.objectContaining({ status: "queued" }));
});

it("shows a refusal from the preview", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      String(input).includes("csrf")
        ? new Response(JSON.stringify({ csrfToken: "t" }), {
            headers: { "Content-Type": "application/json" },
          })
        : new Response(
            JSON.stringify({
              code: "bulk.bad_action",
              detail: "Write a subject of up to 150 characters.",
            }),
            { status: 400, headers: { "Content-Type": "application/json" } },
          ),
    ),
  );
  renderWithIntl(
    <BulkActionDialog
      practice="p-1"
      action="message"
      selection={{ mode: "ids", ids: new Set(["o1"]) }}
      onClose={() => {}}
      onStarted={() => {}}
    />,
  );
  await userEvent.click(await screen.findByRole("button", { name: "Preview changes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Write a subject of up to 150");
});
