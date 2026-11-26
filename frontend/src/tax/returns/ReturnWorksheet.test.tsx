import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { RETURN_ID, taxReturn } from "./fixtures";
import { ReturnWorksheet } from "./ReturnWorksheet";

/**
 * G-03-T11 — the worksheet: GST34 lines with labels, typed lines as fields on a draft, the
 * stepper, the changed-since banner with Recalculate, and the drill-down drawer listing the
 * documents behind a line (their total = the line).
 */
afterEach(() => vi.unstubAllGlobals());

const DOCS = [
  {
    entry: "e1",
    number: "INV-0001",
    contact: "Maple Leaf Supply Ltd.",
    date: "2026-06-10",
    url: "/o/acme/sales/invoices/1",
    amount: "130.00",
  },
];

function serve(calls: string[], first = taxReturn(), after = taxReturn()) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        calls.push(`${init?.method ?? "GET"} ${url}`);
        if (url.includes("/drill")) return { body: { line: "103", documents: DOCS } };
        if (init?.method === "POST") return { body: after };
        return { body: first };
      }),
    ),
  );
}

it("lays out the lines, the stepper and the entry fields", async () => {
  serve([]);
  const { container } = renderWithIntl(<ReturnWorksheet org="acme" id={RETURN_ID} />);
  const table = await screen.findByTestId("return-lines");
  const row = table.querySelector<HTMLElement>('tr[data-line="109"]')!;
  expect(within(row).getByText("Net tax")).toBeVisible();
  expect(within(row).getByText("$66.50")).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Amount for line 110" })).toHaveValue("0.00");
  const stepper = screen.getByRole("list", { name: "Progress of the return" });
  expect(within(stepper).getByText("Prepare (current step)")).toBeVisible();
  expect(screen.getByRole("button", { name: "Mark as reviewed" })).toBeEnabled();
  await expectNoAxeViolations(container);
});

it("opens the documents behind a line in a drawer", async () => {
  const calls: string[] = [];
  serve(calls);
  renderWithIntl(<ReturnWorksheet org="acme" id={RETURN_ID} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Show the documents behind line 103" }),
  );
  const drawer = await screen.findByRole("dialog", {
    name: "Line 103: GST/HST collected or collectible",
  });
  const docs = await within(drawer).findByTestId("drill-documents");
  expect(within(docs).getByRole("link", { name: "INV-0001" })).toHaveAttribute(
    "href",
    "/o/acme/sales/invoices/1",
  );
  expect(within(docs).getAllByText("$130.00")).toHaveLength(2); // the document and the total
  expect(calls.some((c) => c.endsWith("/drill?line=103"))).toBe(true);
});

it("shows what changed in the books and recalculates", async () => {
  const calls: string[] = [];
  serve(
    calls,
    taxReturn({ changed: [{ line: "103", was: "130.00", now: "156.00" }] }),
    taxReturn(),
  );
  renderWithIntl(<ReturnWorksheet org="acme" id={RETURN_ID} />);
  const banner = await screen.findByTestId("return-changed");
  expect(within(banner).getByText("Line 103: $130.00 → $156.00")).toBeVisible();
  await userEvent.click(within(banner).getByRole("button", { name: "Recalculate" }));
  await waitFor(() => expect(screen.queryByTestId("return-changed")).toBeNull());
  expect(screen.getByRole("status")).toHaveTextContent("Return recalculated from the books.");
  expect(calls).toContain(`POST /api/v1/o/acme/tax/returns/${RETURN_ID}/recalculate`);
});

it("a reviewed return has no fields and can be sent back", async () => {
  serve([], taxReturn({ status: "reviewed", reviewed_by: { id: "u2", name: "Sam Patel" } }));
  renderWithIntl(<ReturnWorksheet org="acme" id={RETURN_ID} />);
  expect(await screen.findByText("Prepared by Dana Lee · reviewed by Sam Patel")).toBeVisible();
  expect(screen.queryByRole("textbox", { name: "Amount for line 110" })).toBeNull();
  expect(screen.getByText("Review (current step)")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Send back" }));
  expect(screen.getByRole("textbox", { name: "Why does it go back?" })).toBeVisible();
});
