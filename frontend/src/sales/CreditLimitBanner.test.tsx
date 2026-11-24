import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { InvoiceCredit } from "./api";
import { CreditLimitBanner } from "./CreditLimitBanner";

/**
 * D-03a-T16 — credit-limit banners in the invoice editor: nothing within the limit; a warning in
 * warn mode; in block mode "Credit limit reached" with Request override (a reason is required),
 * then the request shows as waiting; an approved override says so.
 */
const credit = (over: Partial<InvoiceCredit>): InvoiceCredit => ({
  outcome: "within",
  mode: "warn",
  limit: "200.00",
  exposure: "113.00",
  amount: "113.00",
  projected: "226.00",
  over_by: "26.00",
  message: "",
  contact: { id: "c1", name: "ON Customer Ltd" },
  pending_override: null,
  ...over,
});

let state: InvoiceCredit;
let requests: unknown[] = [];

function serve(initial: InvoiceCredit) {
  state = initial;
  requests = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (init?.method === "POST") {
          requests.push(JSON.parse(String(init.body)));
          state = {
            ...state,
            pending_override: { id: "o1", amount: "113.00", requested_at: "2026-06-16T10:00:00Z" },
          };
          return { status: 201, body: state };
        }
        if (url.endsWith("/credit")) return { body: state };
        return { status: 404, body: {} };
      }),
    ),
  );
}

const WARNING = "This takes ON Customer Ltd to $226.00, $26.00 over its credit limit of $200.00.";
const render = () => renderWithIntl(<CreditLimitBanner org="acme" id="inv-1" />);

describe("CreditLimitBanner", () => {
  it("shows nothing within the limit", async () => {
    serve(credit({ outcome: "within" }));
    const { container } = render();
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container.querySelector("[data-credit-banner]")).toBeNull();
  });

  it("warns in warn mode without blocking", async () => {
    serve(credit({ outcome: "warn", message: WARNING }));
    render();
    expect(await screen.findByRole("heading", { name: "Over the credit limit" })).toBeVisible();
    expect(screen.getByText(WARNING)).toBeInTheDocument();
    expect(screen.getByText("You can still approve this invoice.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request override" })).toBeNull();
  });

  it("blocks and requests an override with a reason", async () => {
    serve(credit({ outcome: "block", mode: "block", message: WARNING }));
    render();
    expect(await screen.findByRole("heading", { name: "Credit limit reached" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Request override" }));
    expect(
      screen.getByText(
        "ON Customer Ltd would owe $226.00, $26.00 over the limit of $200.00. The people who approve overrides are notified.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(
      screen.getByText("Say why the sale should go ahead over the credit limit."),
    ).toBeInTheDocument();
    expect(requests).toEqual([]);
    await userEvent.type(screen.getByLabelText("Reason"), "Cheque in the mail");
    await userEvent.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() => expect(requests).toEqual([{ reason: "Cheque in the mail" }]));
    expect(await screen.findByText(/Override requested .*: waiting for approval\./)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Request override" })).toBeNull();
  });

  it("says when an approved override covers the invoice", async () => {
    serve(credit({ outcome: "override", mode: "block", message: WARNING }));
    render();
    expect(await screen.findByRole("heading", { name: "Override approved" })).toBeVisible();
  });
});
