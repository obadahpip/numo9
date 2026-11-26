import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import {
  CUSTOMER,
  ORG,
  REVENUE,
  TEMPLATE_ID,
  recurringHandler,
  serveJson,
  template,
} from "./fixtures";
import { PLACEHOLDERS, RecurringInvoiceEditor } from "./RecurringInvoiceEditor";

/**
 * D-04-T08 — the recurring invoice template editor: the invoice editor's header and shared grid,
 * the schedule panel (rule built from the choices, next dates asked of the server), the mode and
 * proration; a monthly template is a name, a customer, a line and Save; a saved template opens
 * with its schedule, mode and lines; Pause / Resume; an unknown placeholder is flagged.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof recurringHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(recurringHandler(calls, extra))));
  return calls;
}

it("creates a monthly template from a name, a customer and one line", async () => {
  const calls = serve();
  const navigate = vi.fn();
  renderWithIntl(<RecurringInvoiceEditor org={ORG} navigate={navigate} />);
  const form = await screen.findByRole("form", { name: "New recurring invoice" });
  const customer = within(form).getByRole("combobox", { name: "Customer" });
  await waitFor(() => expect(within(customer).getAllByRole("option")).toHaveLength(2));
  await userEvent.type(within(form).getByRole("textbox", { name: /^Name/ }), "Books");
  await userEvent.selectOptions(customer, CUSTOMER);
  await userEvent.type(
    screen.getByRole("textbox", { name: "Description, line 1" }),
    "BK {{{{month}}",
  );
  await userEvent.type(screen.getByRole("textbox", { name: "Unit price, line 1" }), "300");
  await userEvent.click(screen.getByRole("radio", { name: /^Approve and send/ }));
  await userEvent.click(screen.getByRole("checkbox", { name: /Prorate/ }));
  expect(await screen.findByText("Next 6 invoice dates")).toBeVisible();
  await waitFor(() => expect(form.querySelectorAll("[data-date]")).toHaveLength(6));
  await userEvent.click(within(form).getByRole("button", { name: "Save" }));
  await waitFor(() =>
    expect(navigate).toHaveBeenCalledWith(`/o/${ORG}/sales/recurring-invoices/${TEMPLATE_ID}`),
  );
  const created = calls.find((c) => c.method === "POST" && c.url.endsWith("/recurring-invoices"))!;
  expect(created.body).toMatchObject({
    name: "Books",
    customer: CUSTOMER,
    rrule: "FREQ=MONTHLY;INTERVAL=1",
    mode: "approve_send",
    prorate: true,
    end_date: null,
    lines: [{ description: "BK {{month}}", unit_price: "300.00", account: REVENUE }],
  });
  const schedule = calls.find((c) => c.url.endsWith("/recurring-invoices/schedule"))!;
  expect(schedule.body).toMatchObject({ rrule: "FREQ=MONTHLY;INTERVAL=1", count: 6 });
  expect(await screen.findByText(/Changes apply to the next invoices only/)).toBeVisible();
}, 20_000);

it("opens a saved template with its schedule, mode and lines, and pauses it", async () => {
  const calls = serve();
  renderWithIntl(<RecurringInvoiceEditor org={ORG} id={TEMPLATE_ID} />);
  expect(
    await screen.findByRole("heading", { name: "Recurring invoice Monthly bookkeeping" }),
  ).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Description, line 1" })).toHaveValue(
    "Bookkeeping — {{month}}",
  );
  expect(screen.getByRole("radio", { name: /^Save as a draft/ })).toBeChecked();
  expect(screen.getByText("Active")).toBeVisible();
  for (const token of PLACEHOLDERS) expect(screen.getByText(token)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Pause" }));
  expect(await screen.findByRole("button", { name: "Resume" })).toBeVisible();
  expect(screen.getByRole("note")).toHaveTextContent("Paused");
  expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/pause"))).toBe(true);
});

it("flags a placeholder the server doesn't know", async () => {
  serve((url, method) =>
    url.endsWith(`/recurring-invoices/${TEMPLATE_ID}`) && method === "GET"
      ? { body: template({ unknown_placeholders: ["montth"] }) }
      : undefined,
  );
  renderWithIntl(<RecurringInvoiceEditor org={ORG} id={TEMPLATE_ID} />);
  expect(await screen.findByText("Not a placeholder, left as typed: montth")).toBeVisible();
});

it("shows the server's refusal", async () => {
  serve((url, method) =>
    url.endsWith(`/recurring-invoices/${TEMPLATE_ID}`) && method === "PATCH"
      ? {
          status: 403,
          body: {
            code: "sales.recurring.mode_not_allowed",
            detail: "You can't approve or send invoices.",
          },
        }
      : undefined,
  );
  renderWithIntl(<RecurringInvoiceEditor org={ORG} id={TEMPLATE_ID} />);
  await screen.findByRole("heading", { name: "Recurring invoice Monthly bookkeeping" });
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("You can't approve or send invoices.");
});
