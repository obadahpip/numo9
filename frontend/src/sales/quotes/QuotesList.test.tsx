import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { QUOTE_TABS } from "./api";
import { ORG, quote, serveJson } from "./fixtures";
import { QuotesList } from "./QuotesList";
import { QUOTE_STATUSES } from "./status";

/**
 * D-02-T14 — the quotes list: tabs All / Draft / Sent / Accepted / Declined / Expired / Invoiced
 * with the server's counts (summed from the counts per QuoteStatus — the overview's numbers,
 * gap-05); a tab asks the server for its quotes; Sent covers sent and viewed.
 */
afterEach(() => vi.unstubAllGlobals());

const counts = { draft: 2, sent: 1, viewed: 3, accepted: 1, declined: 0, expired: 4, invoiced: 5 };
const tabs = { all: 16, draft: 2, sent: 4, accepted: 1, declined: 0, expired: 4, invoiced: 5 };

it("shows the tabs with their counts and loads a tab's quotes", async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        const expired = url.includes("tab=expired");
        return {
          body: {
            count: expired ? 4 : 16,
            page: 1,
            pages: 1,
            counts,
            tabs,
            results: [
              quote(
                expired
                  ? { number: "QU-0009", status: "expired", status_label: "Expired" }
                  : { status: "viewed", status_label: "Viewed" },
              ),
            ],
          },
        };
      }),
    ),
  );
  const user = userEvent.setup({ delay: null });
  renderWithIntl(<QuotesList org={ORG} />);
  expect(await screen.findByRole("link", { name: "QU-0001" })).toBeVisible();
  const names = screen.getAllByRole("tab").map((t) => t.textContent);
  expect(names).toEqual([
    "All16",
    "Draft2",
    "Sent4",
    "Accepted1",
    "Declined0",
    "Expired4",
    "Invoiced5",
  ]);
  expect(screen.getByText("Viewed")).toBeVisible();
  await user.click(screen.getByRole("tab", { name: /Expired/ }));
  expect(await screen.findByRole("link", { name: "QU-0009" })).toBeVisible();
  await waitFor(() => expect(urls.some((u) => u.includes("tab=expired"))).toBe(true));
});

it("the tabs are the QuoteStatus values (Viewed inside Sent)", () => {
  expect(QUOTE_TABS.filter((t) => t !== "all")).toEqual(
    QUOTE_STATUSES.filter((s) => s !== "viewed"),
  );
  const summed = Object.fromEntries(
    QUOTE_TABS.map((t) => [
      t,
      t === "all"
        ? Object.values(counts).reduce((a, b) => a + b, 0)
        : t === "sent"
          ? counts.sent + counts.viewed
          : counts[t],
    ]),
  );
  expect(summed).toEqual(tabs);
});
