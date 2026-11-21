import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { FoundingOverview, FoundingSlotRow } from "./api";
import { FoundingScreen } from "./FoundingScreen";

/**
 * U-08-T11 — founding admin panel: list the slots, export, release with a reason. (Export count =
 * allocated is tested against the API: backend/tests/test_founding_console_api.py.)
 */
const row = (n: number, overrides: Partial<FoundingSlotRow> = {}): FoundingSlotRow => ({
  slot_no: n,
  organisation_id: `org-${n}`,
  organisation_name: `Organisation ${n}`,
  allocated_at: "2026-11-18T15:00:00Z",
  payment_ref: `in_${n}`,
  lapsed_at: null,
  released_at: null,
  release_reason: "",
  state: "active",
  ...overrides,
});

const overview = (): FoundingOverview => ({
  cap: 1000,
  allocated: 3,
  remaining: 997,
  active: 2,
  churn_rule: "keep_if_returns_within_days",
  return_window_days: 90,
  refund_release_hours: 24,
  slots: [
    row(1),
    row(2, { state: "cancelled", lapsed_at: "2026-11-19T10:00:00Z" }),
    row(3, { state: "released", released_at: "2026-11-19T10:00:00Z", release_reason: "refunded" }),
  ],
});

const calls: { url: string; method: string; body: unknown }[] = [];
let releaseStatus = 200;

function serve(data: FoundingOverview = overview()) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url, method, body });
      const json = (payload: unknown, status = 200) =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("auth/csrf")) return json({ csrfToken: "t" });
      if (url.endsWith("/release"))
        return releaseStatus === 200
          ? json(row(1, { state: "released", release_reason: "admin" }))
          : json({ detail: "no" }, releaseStatus);
      return json(data);
    }),
  );
}

beforeEach(() => {
  resetCsrfToken();
  releaseStatus = 200;
});

it("shows the counter, the rules and every slot with its status", async () => {
  serve();
  const { container } = renderWithIntl(<FoundingScreen />);
  expect(await screen.findByRole("heading", { name: "3 of 1,000 places given" })).toBeVisible();
  expect(screen.getByText(/997 left/)).toBeVisible();
  expect(screen.getByText(/returns within 90 days/)).toBeVisible();
  expect(
    screen.getByText("A first payment refunded within 24 hours releases the place."),
  ).toBeVisible();
  const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
  expect(rows.map((r) => within(r).getAllByRole("cell")[0]?.textContent)).toEqual([
    "0001",
    "0002",
    "0003",
  ]);
  expect(within(rows[1]!).getByText("Cancelled — may return")).toBeVisible();
  expect(within(rows[2]!).getByText("Released (first payment refunded)")).toBeVisible();
  expect(within(rows[2]!).queryByRole("button")).toBeNull();
  expect(screen.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    "/api/v1/platform/founding/export",
  );
  await expectNoAxeViolations(container);
});

it("releases a slot with a reason", async () => {
  serve();
  const user = userEvent.setup();
  renderWithIntl(<FoundingScreen />);
  await user.click(
    await screen.findByRole("button", { name: "Release place 0001 (Organisation 1)" }),
  );
  const dialog = await screen.findByRole("dialog", { name: "Release founding place 0001?" });
  await user.click(within(dialog).getByRole("button", { name: "Release" }));
  expect(within(dialog).getByRole("alert")).toHaveTextContent(
    "Enter a reason of at least 5 characters.",
  );
  expect(calls.some((c) => c.method === "POST")).toBe(false);
  await user.type(within(dialog).getByLabelText("Reason"), "Duplicate account");
  await user.click(within(dialog).getByRole("button", { name: "Release" }));
  expect(await screen.findByText("Place 0001 released.")).toBeInTheDocument();
  const post = calls.find((c) => c.method === "POST");
  expect(post?.url).toContain("/api/v1/platform/founding/slots/1/release");
  expect(post?.body).toEqual({ reason: "Duplicate account" });
  expect(screen.getByText("Released (released by Numo9)")).toBeVisible();
});

it("explains a refused release", async () => {
  serve();
  releaseStatus = 403;
  const user = userEvent.setup();
  renderWithIntl(<FoundingScreen />);
  await user.click(
    await screen.findByRole("button", { name: "Release place 0001 (Organisation 1)" }),
  );
  const dialog = await screen.findByRole("dialog");
  await user.type(within(dialog).getByLabelText("Reason"), "Duplicate account");
  await user.click(within(dialog).getByRole("button", { name: "Release" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent(
    "Only platform owners can release a place.",
  );
});

it("shows the empty state before the first payment", async () => {
  serve({ ...overview(), allocated: 0, remaining: 1000, active: 0, slots: [] });
  renderWithIntl(<FoundingScreen />);
  expect(await screen.findByText("No founding place given yet")).toBeVisible();
});
