import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { TaxSettings } from "./api";
import { firstError } from "./api";
import { taxSettingsUrl } from "./links";
import { TaxSettingsScreen } from "./TaxSettingsScreen";

/**
 * G-06-T08 — the one tax settings page: every setting read and edited in its card (basis with
 * reason and mid-year warning, default codes and rounding, quick method, restricted ITCs),
 * registrations with their filing link, the not-registered explanation.
 */
const ORG = "acme";
const API = `/api/v1/o/${ORG}/tax`;
const SETTINGS: TaxSettings = {
  basis: "accrual",
  rounding_mode: "line",
  quick_method: false,
  quick_method_from: null,
  default_codes: { sales: { revenue: "sales.ON.standard" } },
  restricted_itc_accounts: [{ id: "a-meals", code: "6400", name: "Meals", pct: "50" }],
  registered: true,
};
const RT = {
  id: "r-rt",
  type: "rt",
  type_label: "GST/HST program account (RT)",
  number: "123456782RT0001",
  display_number: "123456782 RT 0001",
  effective_from: "2026-01-01",
  effective_to: null,
  status: "active",
  status_label: "Registered",
  cra_approval_ref: "",
  files_returns: true,
  filing: {
    frequency: "quarterly",
    periods: 12,
    next_due: { start: "2026-01-01", end: "2026-03-31", due_date: "2026-04-30", attention: "" },
    overdue: 1,
  },
};

afterEach(() => vi.unstubAllGlobals());

interface Call {
  method: string;
  url: string;
  body: Record<string, unknown>;
}

function serve(
  settings: TaxSettings = SETTINGS,
  patch?: (body: Record<string, unknown>) => unknown,
) {
  const calls: Call[] = [];
  let current = settings;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        const method = init?.method ?? "GET";
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        if (method !== "GET") calls.push({ method, url, body });
        if (url === `${API}/registrations`) return { body: { results: [RT] } };
        if (url.startsWith(`${API}/settings/basis-check`)) {
          return {
            body: {
              changes: true,
              mid_year: true,
              warning: "The fiscal year started on 2026-01-01.",
            },
          };
        }
        if (url.startsWith(`${API}/settings/restricted-itc/`)) {
          const id = url.split("/").pop()!;
          const kept = current.restricted_itc_accounts.filter((a) => a.id !== id);
          const list =
            body.pct === null
              ? kept
              : [...kept, { id, code: "6500", name: "Entertainment", pct: String(body.pct) }];
          current = { ...current, restricted_itc_accounts: list };
          return { body: { restricted_itc_accounts: list } };
        }
        if (url === `${API}/settings` && method === "PATCH") {
          const refused = patch?.(body);
          if (refused) return { status: 400, body: refused };
          const change = { ...body };
          delete change.basis_reason;
          current = { ...current, ...(change as Partial<TaxSettings>) };
          return {
            body: { ...current, basis_warning: body.basis ? "Changed during the year." : "" },
          };
        }
        if (url === `${API}/settings`) return { body: current };
        if (url.startsWith(`${API}/codes`)) {
          return {
            body: {
              results: [
                { id: "c1", code: "sales.ON.standard", name: "HST 13 % (Ontario) on sales" },
                { id: "c2", code: "sales.exempt", name: "Exempt on sales" },
              ],
            },
          };
        }
        if (url.includes("/accounts")) {
          return {
            body: {
              count: 2,
              results: [
                { id: "a-meals", code: "6400", name: "Meals", type: "expense" },
                { id: "a-ent", code: "6500", name: "Entertainment", type: "expense" },
              ],
            },
          };
        }
        return { body: {} };
      }),
    ),
  );
  return calls;
}

const card = (anchor: string) => document.querySelector<HTMLElement>(`[data-card="${anchor}"]`)!;

it("shows every tax setting on one page with anchors and the filing link", async () => {
  serve();
  const { container } = renderWithIntl(<TaxSettingsScreen org={ORG} canManage />);
  expect(
    await screen.findByRole("heading", { level: 1, name: "Tax registrations and settings" }),
  ).toBeVisible();
  const nav = screen.getByRole("navigation", { name: "On this page" });
  expect(
    within(nav)
      .getAllByRole("link")
      .map((a) => a.getAttribute("href")),
  ).toEqual(["#registrations", "#tax-basis", "#default-codes", "#quick-method", "#restricted-itc"]);
  for (const anchor of [
    "registrations",
    "tax-basis",
    "default-codes",
    "quick-method",
    "restricted-itc",
  ]) {
    expect(document.getElementById(anchor)).not.toBeNull();
  }
  expect(card("tax-basis")).toHaveTextContent("Accrual");
  expect(card("default-codes")).toHaveTextContent("sales.ON.standard");
  expect(card("default-codes")).toHaveTextContent("Per line");
  expect(card("quick-method")).toHaveTextContent("Not elected (regular method)");
  expect(card("restricted-itc")).toHaveTextContent("6400 Meals");
  const filing = await screen.findByRole("link", {
    name: "Filing periods of GST/HST program account (RT)",
  });
  expect(filing).toHaveAttribute("href", `/o/${ORG}/settings/tax/registrations/r-rt/filing`);
  expect(card("registrations")).toHaveTextContent("Files quarterly");
  expect(card("registrations")).toHaveTextContent("1 return overdue");
  expect(screen.queryByText("Not registered for GST/HST?")).toBeNull();
  await expectNoAxeViolations(container);
});

it("changes the basis only with a reason, and shows the mid-year warning", async () => {
  const calls = serve(SETTINGS, (body) =>
    body.basis && !body.basis_reason
      ? { reason: ["Say why the tax basis changes (at least 10 characters)."] }
      : null,
  );
  const user = userEvent.setup();
  renderWithIntl(<TaxSettingsScreen org={ORG} canManage />);
  await user.click(await screen.findByRole("button", { name: "Edit Tax basis" }));
  await user.click(within(card("tax-basis")).getByRole("radio", { name: /^Cash/ }));
  expect(await within(card("tax-basis")).findByText(/fiscal year started/)).toBeVisible();
  await user.click(within(card("tax-basis")).getByRole("button", { name: "Save" }));
  expect(await within(card("tax-basis")).findByRole("alert")).toHaveTextContent("Say why");
  await user.type(
    within(card("tax-basis")).getByLabelText(/Why the basis changes/),
    "CRA approved cash",
  );
  await user.click(within(card("tax-basis")).getByRole("button", { name: "Save" }));
  await waitFor(() => expect(card("tax-basis")).toHaveTextContent("Cash"));
  expect(calls.at(-1)!.body).toEqual({ basis: "cash", basis_reason: "CRA approved cash" });
  expect(document.querySelector("[data-tax-status]")).toHaveTextContent("Changed during the year.");
});

it("edits the quick method, default codes with rounding, and restricted ITCs", async () => {
  const calls = serve();
  const user = userEvent.setup();
  renderWithIntl(<TaxSettingsScreen org={ORG} canManage />);
  await user.click(await screen.findByRole("button", { name: "Edit Quick method" }));
  await user.click(
    within(card("quick-method")).getByRole("switch", { name: "Quick method elected" }),
  );
  await user.type(within(card("quick-method")).getByLabelText("In effect from"), "2026-01-01");
  await user.click(within(card("quick-method")).getByRole("button", { name: "Save" }));
  await waitFor(() => expect(card("quick-method")).toHaveTextContent("Elected from 2026-01-01"));
  expect(calls.at(-1)!.body).toEqual({ quick_method: true, quick_method_from: "2026-01-01" });

  await user.click(screen.getByRole("button", { name: "Edit Default codes" }));
  expect(await within(card("default-codes")).findByLabelText("Rounding")).toBeVisible();
  await user.click(within(card("default-codes")).getByRole("button", { name: "Save" }));
  await waitFor(() => expect(card("default-codes")).not.toHaveAttribute("data-editing"));
  expect(calls.at(-1)!.body).toEqual({
    default_codes: { sales: { revenue: "sales.ON.standard" } },
    rounding_mode: "line",
  });

  await user.click(screen.getByRole("button", { name: "Edit Restricted input tax credits" }));
  await user.click(
    within(card("restricted-itc")).getByRole("button", { name: "Claim 6400 Meals in full" }),
  );
  await waitFor(() => expect(card("restricted-itc")).toHaveTextContent("No account is restricted"));
  expect(calls.at(-1)).toMatchObject({
    method: "PUT",
    url: `${API}/settings/restricted-itc/a-meals`,
    body: { pct: null },
  });
});

it("explains the small-supplier rule when not registered, and hides Edit without tax.manage", async () => {
  serve({ ...SETTINGS, registered: false });
  renderWithIntl(<TaxSettingsScreen org={ORG} />);
  expect(await screen.findByText("Not registered for GST/HST?")).toBeVisible();
  expect(screen.getByText(/small supplier/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Edit Tax basis" })).toBeNull();
});

it("helpers: first error and deep-link URLs", () => {
  expect(firstError({ reason: ["Say why."] })).toBe("Say why.");
  expect(firstError({ detail: "No." })).toBe("No.");
  expect(firstError(null)).toBeUndefined();
  expect(taxSettingsUrl("acme", "tax-basis")).toBe("/o/acme/settings/registrations#tax-basis");
  expect(taxSettingsUrl("acme")).toBe("/o/acme/settings/registrations");
});
