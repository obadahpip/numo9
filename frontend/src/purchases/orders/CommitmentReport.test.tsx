import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { CommitmentReport } from "./CommitmentReport";
import { COMMITMENTS, ORG, serveJson } from "./fixtures";

/**
 * E-01-T14 — commitment report: rows and total from the server, grouping and dates sent as the
 * query, the export links download that same query (export = screen; the file's rows and total
 * equal the JSON's in backend/tests/test_purchase_order_api.py).
 */
afterEach(() => vi.unstubAllGlobals());

function serve() {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        const by = new URL(url, "http://x").searchParams.get("by");
        return { body: { ...COMMITMENTS, by } };
      }),
    ),
  );
  return urls;
}

it("shows the open value per group with its total, and exports the same query", async () => {
  const urls = serve();
  renderWithIntl(<CommitmentReport org={ORG} />);
  expect(await screen.findByRole("row", { name: /Cedar Supply Co\./ })).toHaveTextContent(
    "Cedar Supply Co.12$570.00",
  );
  expect(screen.getByRole("row", { name: /Total/ })).toHaveTextContent("$770.00");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Group by" }), "supplier");
  await userEvent.type(screen.getByLabelText("PO date from"), "2026-06-01");
  await waitFor(() =>
    expect(urls.at(-1)).toBe(`/api/v1/o/${ORG}/reports/commitments?by=supplier&from=2026-06-01`),
  );
  expect(await screen.findByRole("columnheader", { name: "Supplier" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    `/api/v1/o/${ORG}/reports/commitments?by=supplier&from=2026-06-01&export=csv`,
  );
  expect(screen.getByRole("link", { name: "Export Excel" })).toHaveAttribute(
    "href",
    `/api/v1/o/${ORG}/reports/commitments?by=supplier&from=2026-06-01&export=xlsx`,
  );
});

it("says when nothing is committed", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(serveJson(() => ({ body: { ...COMMITMENTS, rows: [], total: "0.00" } }))),
  );
  renderWithIntl(<CommitmentReport org={ORG} />);
  expect(await screen.findByText("Nothing is committed for these dates.")).toBeVisible();
});
