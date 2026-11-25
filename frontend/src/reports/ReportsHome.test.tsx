import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { CATALOGUE, ORG, serveJson } from "./fixtures";
import { matchesReport, ReportsHome } from "./ReportsHome";

/**
 * K-01-T12 — report home: search (name, description, category), categories with Favourites,
 * tabs Standard/Drafts/Published/Custom, description toggle, ★ favourites; a report outside the
 * package is listed with its product named.
 */
afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

function serve(catalogue = CATALOGUE) {
  const calls: { url: string; method: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        calls.push({ url, method: init?.method ?? "GET" });
        return url.endsWith("/favourite") ? { status: 204, body: null } : { body: catalogue };
      }),
    ),
  );
  return calls;
}

it("search 'tax' finds the tax reports", async () => {
  serve();
  renderWithIntl(<ReportsHome org={ORG} />);
  const search = await screen.findByRole("searchbox", { name: "Search reports" });
  await userEvent.type(search, "tax");
  const list = screen.getByRole("list", { name: "Reports" });
  expect(within(list).getAllByRole("listitem")).toHaveLength(1);
  expect(within(list).getByRole("link", { name: "GST/HST summary" })).toHaveAttribute(
    "href",
    `/o/${ORG}/reports/gst-hst-summary`,
  );
  await userEvent.clear(search);
  await userEvent.type(search, "nothing like this");
  expect(screen.getByRole("status")).toHaveTextContent("No report matches “nothing like this”.");
});

it("matches words in the name, description and category label", () => {
  const [financial, tax] = CATALOGUE.categories;
  const tb = financial!.reports[0]!;
  expect(matchesReport(tb, "debit balance")).toBe(true);
  expect(matchesReport(tb, "TRIAL")).toBe(true);
  expect(matchesReport(tax!.reports[0]!, "tax", "Tax")).toBe(true);
  expect(matchesReport(tb, "payroll")).toBe(false);
});

it("names the product of a report outside the package and keeps it listed", async () => {
  serve();
  const { container } = renderWithIntl(<ReportsHome org={ORG} />);
  const gated = (await screen.findByRole("link", { name: "GST/HST summary" })).closest("li")!;
  expect(within(gated).getByText("Part of Tax — not in this organisation's package")).toBeVisible();
  await expectNoAxeViolations(container);
});

it("stars a report: PUT, then it shows under Favourites first", async () => {
  const calls = serve();
  renderWithIntl(<ReportsHome org={ORG} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Add Account activity to favourites" }),
  );
  expect(calls).toContainEqual({
    url: `/api/v1/o/${ORG}/reports/account-activity/favourite`,
    method: "PUT",
  });
  expect(
    screen.getByRole("button", { name: "Remove Account activity from favourites" }),
  ).toHaveAttribute("aria-pressed", "true");
  const items = within(screen.getByRole("list", { name: "Reports" })).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("Account activity");
  await userEvent.click(screen.getByRole("button", { name: "Favourites" }));
  expect(
    within(screen.getByRole("list", { name: "Reports" })).getAllByRole("listitem"),
  ).toHaveLength(1);
});

it("hides descriptions when toggled and remembers it", async () => {
  serve();
  const { unmount } = renderWithIntl(<ReportsHome org={ORG} />);
  expect(await screen.findByText(/Every account's debit or credit balance/)).toBeVisible();
  await userEvent.click(screen.getByRole("switch", { name: "Show descriptions" }));
  expect(screen.queryByText(/Every account's debit or credit balance/)).toBeNull();
  unmount();
  renderWithIntl(<ReportsHome org={ORG} />);
  await screen.findByRole("link", { name: "Trial balance" });
  expect(screen.queryByText(/Every account's debit or credit balance/)).toBeNull();
});

it("lists saved layouts in the Drafts, Published and Custom tabs", async () => {
  const layout = {
    id: "0b9f3c2e-6a41-4d6f-9a5c-0d1e2f3a4b5c",
    report: "trial_balance",
    name: "Board pack",
    status: "published" as const,
    version: 2,
    params: {},
    config: {},
    notes: "",
    practice: null,
    published_at: "2026-07-01T12:00:00Z",
    updated_at: "2026-07-01T12:00:00Z",
  };
  serve({ ...CATALOGUE, published: [layout] });
  renderWithIntl(<ReportsHome org={ORG} />);
  await userEvent.click(await screen.findByRole("tab", { name: /Published/ }));
  expect(screen.getByRole("link", { name: "Board pack" })).toHaveAttribute(
    "href",
    `/o/${ORG}/reports/trial-balance?layout=${layout.id}`,
  );
  expect(screen.getByText("Trial balance · version 2")).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: /Drafts/ }));
  expect(screen.getByText(/No saved layouts here yet/)).toBeVisible();
});
