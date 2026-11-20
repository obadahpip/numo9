import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { GrantList, ProductGrant } from "./grants";
import { ProductGrants } from "./ProductGrants";

/**
 * U-03-T14 — platform-owner override UI: grant a product for N days with a reason, remove it.
 * (That the override is in the organisation's audit log is tested against the API:
 * backend/tests/test_entitlements_override_console.py, and end to end in Playwright.)
 */
const grant = (overrides: Partial<ProductGrant> = {}): ProductGrant => ({
  id: "g-1",
  product: "payroll",
  product_name: "Payroll",
  expires_at: "2026-12-04T15:00:00Z",
  reason: "Payroll pilot",
  granted_by: "Priya Shah",
  created_at: "2026-11-20T15:00:00Z",
  removed_at: null,
  state: "active",
  ...overrides,
});

let list: GrantList;
const calls: { url: string; method: string; body: unknown }[] = [];
let postStatus = 201;

function serve() {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url, method, body });
      const json = (payload: unknown, status = 200) =>
        new Response(status === 204 ? null : JSON.stringify(payload), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("auth/csrf")) return json({ csrfToken: "t" });
      if (method === "POST") {
        if (postStatus !== 201) return json({ detail: "no" }, postStatus);
        list = { ...list, overrides: [grant(), ...list.overrides] };
        return json(grant(), 201);
      }
      if (method === "DELETE") {
        list = { ...list, overrides: [grant({ state: "removed" })] };
        return json(null, 204);
      }
      return json(list);
    }),
  );
}

beforeEach(() => {
  resetCsrfToken();
  postStatus = 201;
  list = {
    overrides: [grant({ id: "g-0", product_name: "Tax", state: "expired", reason: "Old test" })],
    products: [
      { code: "payroll", name: "Payroll" },
      { code: "tax", name: "Tax" },
    ],
    max_days: 365,
  };
});

it("grants a product for N days with a reason", async () => {
  serve();
  const changed = vi.fn();
  const user = userEvent.setup();
  const { container } = renderWithIntl(
    <ProductGrants
      organisationId="org-1"
      canGrant
      timeZone="America/Toronto"
      onChanged={changed}
    />,
  );
  expect(await screen.findByText(/Tax until/)).toBeVisible();
  expect(screen.getByText("Ended")).toBeVisible();
  await expectNoAxeViolations(container);

  await user.click(screen.getByRole("button", { name: "Grant product" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Choose a product.");
  await user.selectOptions(screen.getByLabelText("Product"), "payroll");
  await user.clear(screen.getByLabelText("Days"));
  await user.type(screen.getByLabelText("Days"), "400");
  await user.click(screen.getByRole("button", { name: "Grant product" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Enter a number of days from 1 to 365.");
  await user.clear(screen.getByLabelText("Days"));
  await user.type(screen.getByLabelText("Days"), "14");
  await user.type(screen.getByLabelText("Reason"), "Payroll pilot");
  await user.click(screen.getByRole("button", { name: "Grant product" }));
  expect(await screen.findByText(/Payroll granted until/)).toBeInTheDocument();
  const post = calls.find((c) => c.method === "POST");
  expect(post?.url).toContain("/api/v1/platform/organisations/org-1/overrides");
  expect(post?.body).toEqual({ product: "payroll", days: 14, reason: "Payroll pilot" });
  expect(changed).toHaveBeenCalledTimes(1);
  const items = within(container.querySelector("[data-grants]") as HTMLElement).getAllByRole(
    "listitem",
  );
  expect(items[0]).toHaveTextContent("Payroll pilot (Priya Shah)");
});

it("removes an active grant", async () => {
  list.overrides = [grant()];
  serve();
  const user = userEvent.setup();
  renderWithIntl(<ProductGrants organisationId="org-1" canGrant timeZone="America/Toronto" />);
  await user.click(await screen.findByRole("button", { name: "Remove Payroll" }));
  expect(await screen.findByText("Payroll removed.")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "DELETE")?.url).toContain("/overrides/g-1");
  expect(await screen.findByText("Removed")).toBeVisible();
});

it("support sees the grants but no form", async () => {
  list.overrides = [grant()];
  serve();
  renderWithIntl(
    <ProductGrants organisationId="org-1" canGrant={false} timeZone="America/Toronto" />,
  );
  expect(await screen.findByText(/Payroll until/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Grant product" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Remove Payroll" })).toBeNull();
});

it("explains a refused grant", async () => {
  serve();
  postStatus = 403;
  const user = userEvent.setup();
  renderWithIntl(<ProductGrants organisationId="org-1" canGrant timeZone="America/Toronto" />);
  await user.selectOptions(await screen.findByLabelText("Product"), "payroll");
  await user.type(screen.getByLabelText("Reason"), "Payroll pilot");
  await user.click(screen.getByRole("button", { name: "Grant product" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Only platform owners can grant or remove products.",
  );
});
