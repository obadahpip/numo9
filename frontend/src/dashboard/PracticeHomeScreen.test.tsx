import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { Dashboard, DashboardWidget } from "./api";
import { PracticeHomeScreen } from "./PracticeHomeScreen";

/**
 * V-04-T08 — practice home cards: large number, label, drill link to the pre-filtered directory;
 * zero renders "0"; a failing widget shows its own error with retry (the rest loads).
 */
const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const widget = (over: Partial<DashboardWidget>): DashboardWidget => ({
  key: "x",
  title: "X",
  description: "",
  kind: "count",
  status: "ok",
  count: 0,
  filters: null,
  href: "",
  items: [],
  ...over,
});

const dashboard = (over: Partial<Dashboard> = {}): Dashboard => ({
  practice: { id: PRACTICE, name: "Abuodeh CPA" },
  scope: "all",
  scopes: ["mine", "all"],
  widgets: [
    widget({
      key: "trials_ending",
      title: "Trials ending in 7 days",
      count: 3,
      filters: { status: ["trial"], trial_ending: ["yes"] },
    }),
    widget({
      key: "read_only",
      title: "Read-only organisations",
      count: 0,
      filters: { status: ["read_only"] },
    }),
    widget({
      key: "missing_bn",
      title: "Organisations without a BN",
      status: "error",
      count: null,
    }),
    widget({
      key: "dormant_staff",
      title: "Dormant staff",
      count: 1,
      href: `/p/${PRACTICE}/staff`,
    }),
    widget({ key: "deadlines", title: "Deadlines in the next 30 days", kind: "list", count: 0 }),
    widget({
      key: "workload",
      title: "Workload",
      kind: "workload",
      count: 2,
      items: [
        { id: "u1", name: "Sam Patel", role: "accountant", organisations: 3, open_tasks: 0 },
        { id: "u2", name: "Ada Admin", role: "practice_admin", organisations: 0, open_tasks: 0 },
      ],
    }),
  ],
  ...over,
});

let answers: Dashboard[] = [];
const urls: string[] = [];

function serve(...bodies: Dashboard[]) {
  answers = bodies;
  urls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      urls.push(String(input));
      const body = answers.length > 1 ? answers.shift() : answers[0];
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

it("shows each card with its number and a drill link; zero renders 0", async () => {
  serve(dashboard());
  const { container } = renderWithIntl(<PracticeHomeScreen practice={PRACTICE} />);
  const trials = await screen.findByRole("region", { name: "Trials ending in 7 days" });
  expect(within(trials).getByText("3")).toBeVisible();
  expect(
    within(trials).getByRole("link", { name: "Open in directory: Trials ending in 7 days" }),
  ).toHaveAttribute("href", `/p/${PRACTICE}/directory?status=trial&trial_ending=yes`);
  const readOnly = screen.getByRole("region", { name: "Read-only organisations" });
  expect(within(readOnly).getByText("0")).toBeVisible();
  const dormant = screen.getByRole("region", { name: "Dormant staff" });
  expect(within(dormant).getByRole("link", { name: "Open staff: Dormant staff" })).toHaveAttribute(
    "href",
    `/p/${PRACTICE}/staff`,
  );
  expect(screen.getByText("No deadline in the next 30 days.")).toBeVisible();
  expect(screen.getByText("3 organisations · 0 open tasks")).toBeVisible();
  await expectNoAxeViolations(container);
});

it("a failing widget shows its error and retries alone", async () => {
  const fixed = dashboard();
  fixed.widgets = fixed.widgets.map((w) =>
    w.key === "missing_bn"
      ? { ...w, status: "ok", count: 2, filters: { bn_missing: ["yes"] } }
      : w.key === "trials_ending"
        ? { ...w, count: 99 } // the retry only takes the failed card's answer
        : w,
  );
  serve(dashboard(), fixed);
  const user = userEvent.setup();
  renderWithIntl(<PracticeHomeScreen practice={PRACTICE} />);
  const failed = await screen.findByRole("region", { name: "Organisations without a BN" });
  expect(within(failed).getByText("Couldn't load this figure.")).toBeVisible();
  expect(screen.getByRole("region", { name: "Trials ending in 7 days" })).toHaveTextContent("3");
  await user.click(
    within(failed).getByRole("button", { name: "Try again: Organisations without a BN" }),
  );
  const healed = await screen.findByRole("link", {
    name: "Open in directory: Organisations without a BN",
  });
  expect(healed).toHaveAttribute("href", `/p/${PRACTICE}/directory?bn_missing=yes`);
  expect(screen.getByRole("region", { name: "Trials ending in 7 days" })).toHaveTextContent("3");
});

it("switches between my organisations and the whole practice", async () => {
  serve(dashboard(), dashboard({ scope: "mine" }));
  const user = userEvent.setup();
  renderWithIntl(<PracticeHomeScreen practice={PRACTICE} />);
  const all = await screen.findByRole("button", { name: "All practice" });
  expect(all).toHaveAttribute("aria-pressed", "true");
  await user.click(screen.getByRole("button", { name: "My organisations" }));
  expect(await screen.findByRole("button", { name: "My organisations" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(urls.at(-1)).toContain("scope=mine");
});

it("staff with one scope see no switch", async () => {
  serve(dashboard({ scope: "mine", scopes: ["mine"] }));
  renderWithIntl(<PracticeHomeScreen practice={PRACTICE} />);
  await screen.findByRole("region", { name: "Trials ending in 7 days" });
  expect(screen.queryByRole("button", { name: "All practice" })).toBeNull();
});
