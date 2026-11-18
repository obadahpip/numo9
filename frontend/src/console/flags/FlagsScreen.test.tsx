import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { FeatureFlag } from "./api";
import { FlagsScreen } from "./FlagsScreen";

/**
 * U-06-T12 — feature flags admin: create, switch on/off/by rule, organisations and practices,
 * percentage, delete. (That the toggles reflect in `/me/flags` is tested against the API:
 * backend/tests/test_platform_flags.py.)
 */

const flag = (overrides: Partial<FeatureFlag> = {}): FeatureFlag => ({
  name: "payroll.t4_screen",
  note: "New T4 screen",
  mode: "off",
  percent: null,
  organisations: [],
  practices: [],
  users: [],
  updated_at: "2026-11-18T15:00:00Z",
  ...overrides,
});

const calls: { url: string; method: string; body: unknown }[] = [];
let stored = flag();

function serve() {
  calls.length = 0;
  stored = flag();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url, method, body });
      const json = (data: unknown, status = 200) =>
        new Response(status === 204 ? null : JSON.stringify(data), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("auth/csrf")) return json({ csrfToken: "t" });
      if (url.includes("/platform/organisations"))
        return json({ results: [{ id: "org-1", name: "Maple Leaf Supply" }] });
      if (method === "PATCH") {
        stored = {
          ...stored,
          ...(body.mode ? { mode: body.mode } : {}),
          ...("percent" in body ? { percent: body.percent } : {}),
          ...(body.organisations
            ? {
                organisations: body.organisations.map((id: string) => ({
                  id,
                  name: "Maple Leaf Supply",
                })),
              }
            : {}),
        };
        return json(stored);
      }
      if (method === "POST") return json(flag({ name: body.name, note: body.note }), 201);
      if (method === "DELETE") return json(null, 204);
      return json({ flags: [stored] });
    }),
  );
}

beforeEach(() => {
  resetCsrfToken();
  serve();
});
afterEach(() => vi.unstubAllGlobals());

it("switches a flag on, then by rule with an organisation and a percentage", async () => {
  const { container } = renderWithIntl(<FlagsScreen />);
  await screen.findByText("payroll.t4_screen");
  const item = container.querySelector('[data-flag="payroll.t4_screen"]') as HTMLElement;
  expect(within(item).getByRole("button", { name: "Off for everyone" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await userEvent.click(within(item).getByRole("button", { name: "On for everyone" }));
  expect(calls.at(-1)).toMatchObject({ method: "PATCH", body: { mode: "on" } });
  expect(
    await within(item).findByRole("button", { name: "On for everyone", pressed: true }),
  ).toBeVisible();

  await userEvent.click(within(item).getByRole("button", { name: "By rule" }));
  await userEvent.type(await within(item).findByLabelText("Add an organisation"), "Maple");
  await userEvent.click(await within(item).findByRole("button", { name: "Add Maple Leaf Supply" }));
  expect(calls.at(-1)).toMatchObject({ method: "PATCH", body: { organisations: ["org-1"] } });
  expect(
    await within(item).findByRole("button", { name: "Remove Maple Leaf Supply" }),
  ).toBeVisible();

  await userEvent.type(within(item).getByLabelText("Percentage of organisations"), "25");
  await userEvent.click(within(item).getByRole("button", { name: "Save percentage" }));
  expect(calls.at(-1)).toMatchObject({ method: "PATCH", body: { percent: "25" } });
  await expectNoAxeViolations(container);
});

it("creates and deletes a flag", async () => {
  renderWithIntl(<FlagsScreen />);
  await screen.findByText("payroll.t4_screen");
  await userEvent.type(screen.getByLabelText("Name"), "beta.reports");
  await userEvent.click(screen.getByRole("button", { name: "Create flag" }));
  expect(await screen.findByText("beta.reports")).toBeVisible();
  expect(calls.find((c) => c.method === "POST" && c.url.endsWith("/platform/flags"))?.body).toEqual(
    {
      name: "beta.reports",
      note: "",
    },
  );
  const item = document.querySelector('[data-flag="beta.reports"]') as HTMLElement;
  await userEvent.click(within(item).getByRole("button", { name: "Delete flag" }));
  const dialog = await screen.findByRole("dialog", { name: "Delete beta.reports?" });
  await userEvent.click(within(dialog).getByRole("button", { name: "Delete flag" }));
  expect(calls.at(-1)).toMatchObject({ method: "DELETE" });
  await vi.waitFor(() => expect(screen.queryByText("beta.reports")).toBeNull());
});
