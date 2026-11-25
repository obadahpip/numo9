import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { BillScreen } from "./BillScreen";
import { bill, billHandler, BILL_ID, ORG, PREVIEW, serveJson } from "./fixtures";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

/**
 * E-02-T12 — inline supplier-invoice-number check with a link to the bill that has it, and the
 * duplicate warning panel after a save.
 */
const OTHER = "b2b2b2b2-0000-4000-8000-000000000002";

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());

it("a used number shows inline with a link to its bill", async () => {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson(
        billHandler(calls, (url) =>
          url.includes("/check-number") && url.includes("number=CS-0042")
            ? {
                body: {
                  number: "CS-0042",
                  available: false,
                  conflict: {
                    id: OTHER,
                    number: "BILL-0042",
                    status: "awaiting_payment",
                    date: "2026-09-12",
                    url: `/o/${ORG}/purchases/bills/${OTHER}`,
                    message: "Already used on BILL-0042 (12 Sep 2026)",
                  },
                },
              }
            : undefined,
        ),
      ),
    ),
  );
  renderWithIntl(<BillScreen org={ORG} id={BILL_ID} />);
  const field = await screen.findByRole("textbox", { name: "Supplier invoice number" });
  await userEvent.clear(field);
  await userEvent.type(field, "CS-0042");
  const message = await screen.findByText("Already used on BILL-0042 (12 Sep 2026)");
  expect(field).toHaveAttribute("aria-invalid", "true");
  expect(within(message.parentElement!).getByRole("link", { name: "Open it" })).toHaveAttribute(
    "href",
    `/o/${ORG}/purchases/bills/${OTHER}`,
  );
  expect(calls.some((c) => c.url.includes(`exclude=${BILL_ID}`))).toBe(true);
});

it("shows the duplicate warning panel", async () => {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson(
        billHandler(calls, (url) =>
          url.endsWith("/preview")
            ? {
                body: {
                  ...PREVIEW,
                  duplicates: [
                    {
                      id: OTHER,
                      number: "",
                      supplier_invoice_no: "CS-0999",
                      date: "2026-06-20",
                      total: "508.00",
                      status: "draft",
                      days_apart: 5,
                      message: "",
                    },
                  ],
                },
              }
            : undefined,
        ),
      ),
    ),
  );
  renderWithIntl(<BillScreen org={ORG} id={BILL_ID} />);
  const panel = await screen.findByRole("region", {
    name: "This bill looks like one already entered",
  });
  expect(within(panel).getByRole("link", { name: "Open CS-0999" })).toHaveAttribute(
    "href",
    `/o/${ORG}/purchases/bills/${OTHER}`,
  );
  expect(within(panel).getByText("20 Jun 2026 · $508.00")).toBeVisible();
});

it("explains the routing and lets an approver approve a bill waiting for it (E-02-T14)", async () => {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson(
        billHandler(calls, (url, method) => {
          if (url.endsWith("/preview"))
            return {
              body: {
                ...PREVIEW,
                routing: {
                  rule: "r1",
                  role: "f1",
                  role_name: "Finance",
                  explanation: "Routed to Finance approvers (amount over $2,000.00)",
                },
              },
            };
          if (url.endsWith(`/bills/${BILL_ID}`) && method === "GET")
            return {
              body: bill({ status: "awaiting_approval", status_label: "Awaiting approval" }),
            };
          return undefined;
        }),
      ),
    ),
  );
  renderWithIntl(<BillScreen org={ORG} id={BILL_ID} />);
  const panel = await screen.findByRole("region", { name: "Approval" });
  expect(
    within(panel).getByText("Routed to Finance approvers (amount over $2,000.00)"),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Approve" }));
  expect(await screen.findByText("BILL-0001 is approved and awaiting payment.")).toBeVisible();
  expect(calls.some((c) => c.method === "PATCH")).toBe(false); // nothing to save: just approve
});
