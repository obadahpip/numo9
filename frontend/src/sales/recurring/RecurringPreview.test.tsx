import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { ORG, PREVIEW, TEMPLATE_ID, previewInvoice, recurringHandler, serveJson } from "./fixtures";
import { RecurringPreview } from "./RecurringPreview";

/**
 * D-04-T09 — "Preview next invoice": the server's invoice for the next date (placeholders
 * resolved, due date, period, totals), another of the next dates on request, the proration and a
 * date that would be skipped.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof recurringHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(recurringHandler(calls, extra))));
  return calls;
}

it("shows the next invoice with its placeholders resolved", async () => {
  const calls = serve();
  renderWithIntl(<RecurringPreview org={ORG} id={TEMPLATE_ID} />);
  expect(await screen.findByRole("heading", { name: "Preview next invoice" })).toBeVisible();
  expect(await screen.findByText("Bookkeeping July 2026")).toBeVisible();
  expect(screen.getByText("Bookkeeping — July")).toBeVisible();
  expect(screen.getByText("For 15 Jul 2026 to 14 Aug 2026")).toBeVisible();
  expect(screen.getByText("$339.00")).toBeVisible();
  expect(screen.queryByText(/Prorated/)).toBeNull();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "For" }), "2026-09-15");
  await waitFor(() =>
    expect(calls.some((c) => c.url.endsWith("/preview?date=2026-09-15"))).toBe(true),
  );
});

it("shows the proration and a date that would be skipped", async () => {
  serve((url) =>
    url.includes("/preview")
      ? {
          body: {
            ...PREVIEW,
            invoice: previewInvoice({
              proration: { covered: 15, days: 31, full: false },
              skip: { code: "lock.violation", message: "The AR lock date is 31 Jul 2026." },
            }),
          },
        }
      : undefined,
  );
  renderWithIntl(<RecurringPreview org={ORG} id={TEMPLATE_ID} />);
  expect(await screen.findByText("Prorated: 15 of 31 days")).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "This date will be skipped: The AR lock date is 31 Jul 2026.",
  );
});

it("says when the schedule has ended", async () => {
  serve((url) =>
    url.includes("/preview") ? { body: { invoice: null, dates: [], status: "ended" } } : undefined,
  );
  renderWithIntl(<RecurringPreview org={ORG} id={TEMPLATE_ID} />);
  expect(await screen.findByText("The schedule has ended: there's no next invoice.")).toBeVisible();
});
